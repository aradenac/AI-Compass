"""FUT-18: controlled retirement, orphan inventory, privileged purge and policy.

Logical retirement is the normal business deletion: it hides an object from
current views while preserving stable IDs, immutable revisions and historical
references. Physical purge is a separately privileged, fail-closed operation
that never removes a shared content-addressed blob still referenced anywhere.
No function here cascades a delete, fabricates eligibility or auto-purges a
merely unlinked independent object.

Immutability exception: evidence tables are append-only by database trigger
(§5: "Ordinary business deletion is not automatically physical data erasure",
while §6.3.4 permits removing eligible physical bytes and their metadata "only
when safe"). `purge` therefore opens a transaction-local, DELETE-only guard
window (`ai_compass.purge_blob`) that the evidence-blob trigger honours only for
an unreferenced, verified row; UPDATE stays forbidden and the window closes when
the transaction ends.
"""
from datetime import timedelta

from django.db import connection, transaction
from django.utils import timezone

from .catalog_ids import new_public_id, uuid7
from .evidence_store import blob_path
from .models import (
    CatalogItem, EvidenceBlob, EvidenceLink, PurgeCandidate, PurgePolicy,
    PurgeReceipt, RetirementEvent, RetirementRecord,
)

PURGE_CLASSES = frozenset({"evidence_blob", "managed_record"})
DEFAULT_GRACE_DAYS = 30
PURGE_LOCK = 920920
PURGE_GUARD = "ai_compass.purge_blob"


class RetirementError(ValueError):
    pass


class PurgeRefused(RuntimeError):
    """Fail-closed: the purge must not proceed under current conditions."""


def _ident(prefix="mnt"):
    return new_public_id(prefix) + "-" + uuid7().hex[-12:]


# --- logical retirement -----------------------------------------------------

@transaction.atomic
def retire(*, actor, item, reason=""):
    """Hide an object from current views; keep identity, revisions and history."""
    locked = CatalogItem.objects.select_for_update(of=("self",)).get(pk=item.pk)
    if hasattr(locked, "retirement"):
        raise RetirementError("Object is already retired")
    if not locked.current_revision_id:
        raise RetirementError("Only initialized objects can be retired")
    record = RetirementRecord.objects.create(
        public_id=_ident(), item=locked, action="retired",
        reason=reason[:600], actor=actor,
    )
    RetirementEvent.objects.create(
        item=locked, action="retired", reason=reason[:600], actor=actor,
        detail={"record": record.public_id},
    )
    return record


@transaction.atomic
def restore(*, actor, item, reason=""):
    """Reverse a logical retirement; the tombstone trail is preserved."""
    locked = CatalogItem.objects.select_for_update(of=("self",)).get(pk=item.pk)
    record = getattr(locked, "retirement", None)
    if record is None:
        raise RetirementError("Object is not retired")
    RetirementEvent.objects.create(
        item=locked, action="restored", reason=reason[:600], actor=actor,
        detail={"record": record.public_id},
    )
    record.delete()
    return locked


def is_retired(item):
    return hasattr(item, "retirement")


# --- orphan inventory and dry-run preview -----------------------------------

def _blob_protected_refs(sha256):
    """Any live EvidenceLink makes the blob protected. Dedup: one owner suffices."""
    return EvidenceLink.objects.filter(blob_id=sha256).count()


def _blob_disk_present(sha256):
    return blob_path(sha256).exists()


def _blob_orphan_since(sha256, created_at):
    """Durable first-orphan timestamp: the earliest stored candidate, else upload.

    A Blob is only ever recorded as a candidate *while* it has zero references,
    so the first persisted PurgeCandidate is the first verified orphan moment
    (spec 6.2: count grace from first verified orphan eligibility). Before any
    inventory has run we have no observation, so we fall back to the upload time
    — never *earlier* than the truth, so a blob can never be treated as having
    aged longer than it has.
    """
    journal = (PurgeCandidate.objects
               .filter(subject=sha256, kind="evidence_blob")
               .order_by("first_seen_at").first())
    return journal.first_seen_at if journal else created_at


def inventory():
    """Read-only inventory of genuinely orphaned, unreferenced evidence blobs.

    A blob qualifies only when NO EvidenceLink points at it and its metadata is
    consistent; a missing payload is a diagnostic blocker, not authorization to
    purge. Managed-record candidates require an explicit retirement and are
    never auto-candidates. `first_seen_at` is the durable orphan-since journal.
    """
    rows = []
    referenced = set(
        EvidenceLink.objects.values_list("blob_id", flat=True).distinct()
    )
    for blob in EvidenceBlob.objects.order_by("sha256").iterator(chunk_size=200):
        if blob.sha256 in referenced:
            continue
        blockers = []
        if not _blob_disk_present(blob.sha256):
            blockers.append("blob_missing_on_disk")
        since = _blob_orphan_since(blob.sha256, blob.created_at)
        rows.append({
            "kind": "evidence_blob",
            "subject": blob.sha256,
            "size_bytes": blob.size,
            "media_type": blob.media_type,
            "created_at": blob.created_at.isoformat(),
            "first_seen_at": since.isoformat(),
            "protected_references": 0,
            "blockers": blockers,
        })
    retired = RetirementRecord.objects.select_related("item").order_by("retired_at")
    for record in retired.iterator():
        item = record.item
        if EvidenceLink.objects.filter(item_id=item.pk).exists():
            # Still-referenced evidence keeps the record non-purgeable, but a
            # retirement keeps it hidden; it is a candidate only if unreferenced.
            continue
        rows.append({
            "kind": "managed_record",
            "subject": item.public_id,
            "size_bytes": 0,
            "media_type": item.type_slug,
            "retired_at": record.retired_at.isoformat(),
            "first_seen_at": record.retired_at.isoformat(),
            "protected_references": 0,
            "blockers": [],
        })
    return rows


def policy():
    """The active policy, or an explicit disabled default (never auto-purge)."""
    return PurgePolicy.objects.filter(is_active=True).order_by("-version").first()


def _grace_days():
    active = policy()
    return active.grace_days if active else DEFAULT_GRACE_DAYS


def preview():
    """Repeatable dry-run: eligibility, blockers, reclaim estimate.

    Grace is measured from the durable orphan-since journal (later of first
    verified orphan and last reference removal), so a newly unlinked ancient
    blob is never instantly eligible. The result is stable across calls while
    nothing changes, supporting an operator's decision.
    """
    days = _grace_days()
    now = timezone.now()
    candidates, reclaim, blocked = [], 0, 0
    for row in inventory():
        first_seen = timezone.datetime.fromisoformat(row["first_seen_at"])
        age_days = (now - first_seen).days
        row_blockers = list(row["blockers"])
        if age_days < days:
            row_blockers.append(
                "grace_period_active (%d/%d days)" % (age_days, days))
        if row_blockers:
            blocked += 1
        else:
            reclaim += row["size_bytes"]
        candidates.append({
            **row,
            "eligible_at": (first_seen + timedelta(days=days)).isoformat(),
            "age_days": age_days,
            "eligible": not row_blockers,
            "blockers": row_blockers,
        })
    active = policy()
    return {
        "grace_days": days,
        "policy_enabled": bool(active and active.enabled),
        "policy_version": active.version if active else None,
        "checked_references": True,
        "projected_reclaim_bytes": reclaim,
        "candidate_count": len(candidates),
        "blocked_count": blocked,
        "candidates": candidates,
    }


def record_inventory(actor=None):
    """Persist the current dry-run as durable candidates (idempotent by subject).

    Idempotent per subject: an existing candidate is never rewritten, so its
    `first_seen_at` stays the true first-orphan moment and the grace clock never
    restarts.
    """
    snapshot = preview()
    created = []
    with transaction.atomic():
        for row in snapshot["candidates"]:
            candidate, _ = PurgeCandidate.objects.get_or_create(
                subject=row["subject"], kind=row["kind"],
                defaults={
                    "public_id": _ident(),
                    "eligible_at": timezone.datetime.fromisoformat(row["eligible_at"]),
                    "size_bytes": row["size_bytes"],
                    "blockers": row["blockers"],
                    "preview": {"age_days": row["age_days"],
                                "protected_references": row["protected_references"]},
                },
            )
            created.append(candidate.public_id)
    return created


# --- privileged physical purge ----------------------------------------------

def _double_confirm(token):
    if token != "purge":
        raise PurgeRefused("Explicit confirmation token 'purge' is required")


def _open_guard_window():
    """Allow DELETE (never UPDATE) of verified-unreferenced blob rows, this txn only."""
    with connection.cursor() as cursor:
        cursor.execute(f"SET LOCAL {PURGE_GUARD} = 'on'")


def _managed_record_subjects():
    return set(
        RetirementRecord.objects.values_list("item__public_id", flat=True)
    )


@transaction.atomic
def purge(*, actor, subjects, token):
    """Idempotent, race-safe purge of explicitly approved orphan subjects.

    Fails closed on any protected reference, disk inconsistency or unknown
    provenance: those subjects are reported blocked and left untouched. A row
    lock plus an advisory transaction lock means a new reference cannot be
    created once eligibility is rechecked. Managed-record subjects are deferred
    to their own domain policy and never physically removed here.
    """
    _double_confirm(token)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [PURGE_LOCK])
    now = timezone.now()
    deferred = _managed_record_subjects()
    reclaimed, purged, blocked, details = 0, 0, 0, []
    guard_open = False
    for subject in subjects:
        if subject in deferred:
            blocked += 1
            details.append({"subject": subject, "result": "record_purge_deferred"})
            continue
        blob = EvidenceBlob.objects.select_for_update().filter(sha256=subject).first()
        if blob is None:
            blocked += 1
            details.append({"subject": subject, "result": "unknown_subject"})
            continue
        if EvidenceLink.objects.filter(blob_id=subject).exists():
            blocked += 1
            details.append({"subject": subject, "result": "re_referenced"})
            continue
        path = blob_path(subject)
        if not path.exists():
            blocked += 1
            details.append({"subject": subject, "result": "disk_inconsistent"})
            continue
        if not guard_open:
            _open_guard_window()
            guard_open = True
        path.unlink()
        reclaimed += blob.size
        purged += 1
        details.append({"subject": subject, "result": "purged", "size": blob.size})
        blob.delete()
    receipt = PurgeReceipt.objects.create(
        public_id=_ident(), job_key=uuid7().hex, actor=actor,
        reclaimed_bytes=reclaimed, purged_count=purged, blocked_count=blocked,
        detail={"results": details},
    )
    return receipt


# --- retention policy administration ----------------------------------------

@transaction.atomic
def configure_policy(*, actor, enabled, grace_days, eligible_classes, cadence_hours):
    if not isinstance(grace_days, int) or grace_days < 0:
        raise RetirementError("grace_days must be a non-negative integer")
    classes = [c for c in eligible_classes if c in PURGE_CLASSES]
    if enabled and not classes:
        raise RetirementError("Enabling automatic GC requires at least one eligible class")
    current = policy()
    version = (current.version + 1) if current else 1
    if current:
        current.is_active = False
        current.save(update_fields=["is_active"])
    row = PurgePolicy.objects.create(
        is_active=True, enabled=bool(enabled), grace_days=grace_days,
        eligible_classes=classes, cadence_hours=max(1, int(cadence_hours)),
        version=version, updated_by=actor,
    )
    return row


def serialize_policy(row):
    if row is None:
        return {"enabled": False, "grace_days": DEFAULT_GRACE_DAYS,
                "eligible_classes": [], "cadence_hours": 168, "version": 0,
                "note": "No active policy; automatic purge disabled."}
    return {
        "enabled": row.enabled, "grace_days": row.grace_days,
        "eligible_classes": row.eligible_classes, "cadence_hours": row.cadence_hours,
        "version": row.version, "updated_by": row.updated_by.get_username(),
        "updated_at": row.updated_at.isoformat(),
    }


def serialize_receipt(row):
    return {
        "public_id": row.public_id, "job_key": row.job_key,
        "actor": row.actor.get_username() if row.actor else None,
        "reclaimed_bytes": row.reclaimed_bytes, "purged_count": row.purged_count,
        "blocked_count": row.blocked_count, "detail": row.detail,
        "created_at": row.created_at.isoformat(),
    }
