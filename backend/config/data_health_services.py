"""PLAT-27: read-only diagnostics + append-only, deduplicated maintenance triage.

The scanner never repairs business records, mutates evidence files or executes
a migration. All health scans are serialized and committed atomically.
"""
import hashlib

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from .catalog_compat import compatibility_for_revision, registry_for_types
from .catalog_ids import new_public_id, uuid7
from .evidence_store import BrokenEvidence, EvidenceError, verify_bytes
from .models import (
    CatalogItem, DataHealthEvent, DataHealthIssue, EvidenceBlob,
    EvidenceLink, ProductionMigrationReceipt, TaskNode,
)

CHECK_VERSION = "data-health@1"
_UNSET = object()
LOCK = 270027
SEVERITIES = {"schema_invalid":"high", "schema_missing":"high", "schema_obsolete":"medium",
              "relation_invalid":"critical", "blob_missing":"critical",
              "migration_inconsistent":"critical"}
CATEGORIES = frozenset(SEVERITIES)
STATUSES = frozenset({"open", "resolved", "exception"})


class HealthScanInProgress(RuntimeError):
    pass


def _finding(category, subject_type, subject_ref, summary):
    assert category in CATEGORIES
    return (category, subject_type, str(subject_ref), summary)


def inspect_findings():
    """Collect defects, no row writes; never expose evidence names or bytes."""
    findings = {}
    items = CatalogItem.objects.select_related(
        "current_revision__schema_version", "current_revision__created_by"
    ).order_by("public_id")
    registry = registry_for_types(set(items.values_list("type_slug", flat=True)))
    for item in items.iterator():
        revision = item.current_revision
        public = item.public_id
        if revision is None or revision.item_id != item.pk:
            finding = _finding("relation_invalid","catalog",public,"Catalog current revision is missing or unrelated")
            findings[finding[:3]] = finding
            continue
        state = compatibility_for_revision(item, revision, registry=registry.get(item.type_slug, {}))
        if state["status"] in ("unsupported","invalid","needs_review"):
            finding = _finding("schema_invalid","catalog",public,
                "Catalog record requires schema or data compatibility review")
            findings[finding[:3]] = finding
        source_schema = registry.get(item.type_slug, {}).get(revision.schema_version.version, {})
        required = source_schema.get("required", []) if isinstance(source_schema, dict) else []
        if isinstance(required, list) and isinstance(revision.properties, dict):
            missing = [field for field in required if isinstance(field,str) and field not in revision.properties]
            if missing:
                finding = _finding("schema_missing","catalog",public,
                    "Current revision is missing required schema fields")
                findings[finding[:3]] = finding
        if state["status"] in ("migration_available", "outdated"):
            finding = _finding("schema_obsolete","catalog",public,
                "Current revision uses an older supported schema")
            findings[finding[:3]] = finding
    # Structural safety: DB FKs already reject many failures, but historical
    # import/corruption and missing current structure are still diagnosed.
    for node in TaskNode.objects.select_related("item__current_revision","parent").iterator():
        revision = node.item.current_revision
        if not revision or node.item.type_slug != "task":
            finding = _finding("relation_invalid","task",node.item.public_id,
                               "Task identity or current revision is invalid")
            findings[finding[:3]] = finding
            continue
        structure = getattr(revision, "task_structure", None)
        if (structure is None or structure.task_id != node.item_id
                or structure.parent_id != node.parent_id or structure.position != node.position):
            finding = _finding("relation_invalid","task",node.item.public_id,
                               "Current task placement differs from its last immutable revision")
            findings[finding[:3]] = finding
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT l.id::text FROM config_evidencelink l
            LEFT JOIN config_evidenceblob b ON b.sha256 = l.blob_id
            LEFT JOIN config_catalogitem i ON i.id = l.item_id
            LEFT JOIN config_catalogrevision r ON r.id = l.revision_id
            WHERE b.sha256 IS NULL OR i.id IS NULL OR
                  (l.revision_id IS NOT NULL AND
                    (r.id IS NULL OR r.item_id <> l.item_id))
            ORDER BY l.id
        """)
        for (identifier,) in cursor.fetchall():
            finding = _finding("relation_invalid","evidence-link",identifier,
                               "Evidence attachment references inconsistent record identities")
            findings[finding[:3]] = finding
    for blob in EvidenceBlob.objects.order_by("sha256").iterator():
        try:
            verify_bytes(blob.sha256, size=blob.size)
        except (EvidenceError, BrokenEvidence):
            finding = _finding("blob_missing","evidence-blob",blob.sha256,
                               "Evidence blob is missing, inaccessible or checksum-invalid")
            findings[finding[:3]] = finding
    for receipt in ProductionMigrationReceipt.objects.select_related(
            "item","source_revision__schema_version","target_revision__schema_version").iterator():
        source, target = receipt.source_revision, receipt.target_revision
        if (source.item_id != receipt.item_id or target.item_id != receipt.item_id
                or target.number != source.number + 1
                or source.schema_version.type_slug != "model" or source.schema_version.version != 1
                or target.schema_version.type_slug != "model" or target.schema_version.version != 2):
            finding = _finding("migration_inconsistent", "migration-receipt", receipt.id,
                               "Migration receipt refers to inconsistent original/target revisions")
            findings[finding[:3]] = finding
    return findings


def _key(category, subject_type, subject_ref):
    return hashlib.sha256((category + "|" + subject_type + "|" + subject_ref).encode("utf-8")).hexdigest()


def scan(*, actor=None):
    """Serialized idempotent scan; an incomplete/failed scan never resolves issues."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [LOCK])
            if not cursor.fetchone()[0]:
                raise HealthScanInProgress("Another health scan is already running")
        findings = inspect_findings()
        run = uuid7()
        now = timezone.now()
        counts = {"new":0,"reopened":0,"resolved":0,"observed":0,"exceptions":0}
        for (category, subject_type, subject_ref), (_,_,_,summary) in findings.items():
            key = _key(category, subject_type, subject_ref)
            row = DataHealthIssue.objects.select_for_update().filter(dedupe_key=key).first()
            if row is None:
                row = DataHealthIssue.objects.create(
                    public_id=new_public_id("mnt"), dedupe_key=key,
                    category=category, severity=SEVERITIES[category],
                    subject_type=subject_type, subject_ref=subject_ref,
                    summary=summary, last_scan_id=run, last_detected_at=now,
                    check_version=CHECK_VERSION,
                )
                DataHealthEvent.objects.create(
                    issue=row, actor=actor, action="detected",
                    detail={"check":CHECK_VERSION, "scan":str(run)})
                counts["new"] += 1
            else:
                was = row.status
                row.last_scan_id = run
                row.last_detected_at = now
                row.detection_count += 1
                row.summary = summary
                if (was == "resolved" or (was == "exception" and row.review_after is not None
                        and row.review_after <= now.date())):
                    row.status = "open"
                    row.exception_rationale = ""
                    row.review_after = None
                    DataHealthEvent.objects.create(
                        issue=row, actor=actor, action="reopened",
                        detail={"from":was,"to":"open","check":CHECK_VERSION,"scan":str(run)})
                    counts["reopened"] += 1
                elif was == "exception":
                    counts["exceptions"] += 1
                else:
                    counts["observed"] += 1
                row.save(update_fields=["last_scan_id","last_detected_at",
                                         "detection_count","summary","status",
                                         "exception_rationale","review_after","updated_at"])
        for row in DataHealthIssue.objects.select_for_update().filter(
                status="open", check_version=CHECK_VERSION,
                category__in=CATEGORIES).exclude(last_scan_id=run):
            row.status = "resolved"
            row.save(update_fields=["status","updated_at"])
            DataHealthEvent.objects.create(
                issue=row, actor=actor, action="auto_resolved",
                detail={"check":CHECK_VERSION,"scan":str(run), "reason":"defect_not_detected"})
            counts["resolved"] += 1
        return {"scan_id":str(run), "check":CHECK_VERSION,
                "findings":len(findings), **counts}


def triage(issue, *, actor, status=None, assignee=_UNSET, rationale=None, review_after=None):
    with transaction.atomic():
        row = DataHealthIssue.objects.select_for_update().get(pk=issue.pk)
        changes = {}
        if status is not None and status != row.status:
            changes["status"] = {"from":row.status,"to":status}
            row.status = status
        new_assignee_id = (assignee.pk if assignee is not None else None) if assignee is not _UNSET else row.assigned_to_id
        if assignee is not _UNSET and new_assignee_id != row.assigned_to_id:
            changes["assignee"] = {"from":row.assigned_to_id,"to":new_assignee_id}
            row.assigned_to_id = new_assignee_id
        if status == "exception":
            if not rationale or not review_after:
                raise ValueError("Exceptions require a rationale and review date")
            if row.exception_rationale != rationale:
                changes["exception_rationale"] = {"from":row.exception_rationale,"to":rationale}
                row.exception_rationale = rationale
            if row.review_after != review_after:
                changes["review_after"] = {"from":str(row.review_after) if row.review_after else None,
                                            "to":str(review_after)}
                row.review_after = review_after
        elif status in ("open","resolved"):
            if row.exception_rationale or row.review_after:
                changes["exception_closed"] = True
                row.exception_rationale = ""
                row.review_after = None
        if changes:
            row.save()
            DataHealthEvent.objects.create(issue=row, actor=actor,
                   action="triaged", detail=changes)
        return row, bool(changes)
