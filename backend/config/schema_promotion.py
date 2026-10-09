"""PLAT-26: registered, signed, per-batch production schema promotion.

No browser API may execute data migrations. A signed host-side approval proof
is valid only for one named, verified recovery snapshot, one staging-accepted
artifact, one operator and the exact production input fingerprint.
"""
import hashlib
import hmac
import json
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import connection, transaction

from .activity_services import record_catalog_event
from .catalog_schemas import InvalidModel, validate_model
from .models import (
    CatalogItem, CatalogRevision, ObjectTypeVersion, ProductionMigrationReceipt,
)

MIGRATION_KEY = "model-v1-to-v2@1"
BATCH_SIZE = 100
PROOF_FIELDS = frozenset({
    "candidate_id", "migration", "migration_sha256", "app_commit",
    "recovery_id", "recovery_manifest_sha256", "approved_report_sha256",
    "source_item_count", "source_revision_count", "source_revision_digest",
    "source_hrid_digest", "source_audit_count", "source_schema_hashes",
    "source_schema_versions", "source_evidence_db_references", "operator",
})
LOCK = 2626001


def _payload_bytes(proof):
    return json.dumps(proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign(proof, secret):
    return hmac.new(secret.encode("utf-8"), _payload_bytes(proof), hashlib.sha256).hexdigest()


def validate_proof(envelope):
    if not isinstance(envelope, dict) or set(envelope) != {"proof", "signature"}:
        raise CommandError("Missing immutable promotion approval envelope")
    proof, signature = envelope["proof"], envelope["signature"]
    if not isinstance(proof, dict) or set(proof) != PROOF_FIELDS:
        raise CommandError("Unrecognized or incomplete approval proof")
    if not isinstance(signature, str) or not hmac.compare_digest(
        sign(proof, settings.SECRET_KEY), signature
    ):
        raise CommandError("Production promotion approval signature does not verify")
    for key, pattern in (
        ("candidate_id", r"[0-9a-f]{16}"),
        ("migration_sha256", r"[0-9a-f]{64}"),
        ("recovery_manifest_sha256", r"[0-9a-f]{64}"),
        ("approved_report_sha256", r"[0-9a-f]{64}"),
        ("app_commit", r"[0-9a-f]{40}"),
    ):
        if not isinstance(proof[key], str) or not re.fullmatch(pattern, proof[key]):
            raise CommandError("Invalid approval field: " + key)
    if proof["migration"] != MIGRATION_KEY:
        raise CommandError("Unregistered promotion migration")
    if not isinstance(proof["operator"], str) or not proof["operator"]:
        raise CommandError("Missing operator attribution")
    if not isinstance(proof["recovery_id"], str) or not re.fullmatch(r"[0-9A-Za-z-]{8,80}", proof["recovery_id"]):
        raise CommandError("Invalid protected recovery point")
    for key in ("source_item_count", "source_revision_count", "source_audit_count"):
        if type(proof[key]) is not int or proof[key] < 0:
            raise CommandError("Invalid backup inventory")
    return proof


def operator(proof):
    User = get_user_model()
    try:
        user = User.objects.get(username=proof["operator"], is_active=True)
    except User.DoesNotExist as error:
        raise CommandError("Approving migration operator is missing/inactive") from error
    if user.is_superuser or not user.has_perm("auth.maintenance_triage"):
        raise CommandError("Operator must hold maintenance_triage explicitly")
    return user


def _source_inventory(candidate_id=None):
    """Compute *pre-promotion* inventory; exclude receipts from this candidate.

    This lets a crashed 100-row batch resume while detecting unrelated writes
    after the recovery point was captured.
    """
    clause = """
      WHERE NOT EXISTS(
        SELECT 1 FROM config_productionmigrationreceipt mr
        WHERE mr.target_revision_id=r.id AND mr.candidate_id=%s
      )
    """ if candidate_id else ""
    values = [candidate_id] if candidate_id else []
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM config_catalogitem")
        items = cursor.fetchone()[0]
        cursor.execute("SELECT md5(coalesce(string_agg(public_id, '|' ORDER BY public_id), '')) FROM config_catalogitem")
        hrids = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*), md5(coalesce(string_agg(
                r.id::text || ':' || r.number::text || ':' || r.schema_version_id::text ||
                ':' || r.display_name || ':' || r.properties::text,
                '|' ORDER BY r.id::text), ''))
            FROM config_catalogrevision r
        """ + clause, values)
        revisions, digest = cursor.fetchone()
        cursor.execute("""
            SELECT COUNT(*) FROM config_catalogauditevent e
            WHERE NOT EXISTS(
                SELECT 1 FROM config_productionmigrationreceipt mr
                WHERE mr.target_revision_id=e.revision_id AND mr.candidate_id=%s
            )
        """ if candidate_id else "SELECT COUNT(*) FROM config_catalogauditevent",
        [candidate_id] if candidate_id else [])
        audits = cursor.fetchone()[0]
    return items, revisions, digest, hrids, audits


def _validate_backup(proof):
    actual = _source_inventory(proof["candidate_id"])
    expected = (proof["source_item_count"], proof["source_revision_count"],
                proof["source_revision_digest"], proof["source_hrid_digest"],
                proof["source_audit_count"])
    if actual != expected:
        raise CommandError("Production source differs from the freshly verified recovery point")
    # Prevent unnoticed schema / evidence changes: source snapshot includes these.
    import hashlib as _hashlib
    schemas = list(ObjectTypeVersion.objects.order_by("type_slug", "version"))
    present_versions = [f"{s.type_slug}:{s.version}" for s in schemas]
    present_hashes = [
        {"type":s.type_slug, "version":s.version,
         "sha256":_hashlib.sha256(json.dumps(s.json_schema, sort_keys=True,
                     ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()}
        for s in schemas
    ]
    if (present_versions != proof["source_schema_versions"] or
            present_hashes != proof["source_schema_hashes"]):
        raise CommandError("Object-type registry changed since backup")
    from .models import EvidenceBlob, EvidenceLink
    refs = {"blob_count":EvidenceBlob.objects.count(),
            "link_count":EvidenceLink.objects.count(),
            "sha256":list(EvidenceBlob.objects.order_by("sha256").values_list("sha256", flat=True))}
    if refs != proof["source_evidence_db_references"]:
        raise CommandError("Evidence metadata changed since backup")


def dry_run():
    """Read-only candidate preview. Never creates a receipt or revision."""
    target = ObjectTypeVersion.objects.get(type_slug="model", version=2)
    rows = CatalogItem.objects.filter(type_slug="model").select_related(
        "current_revision__schema_version"
    ).order_by("public_id")
    pending = []
    blocked = []
    for item in rows.iterator():
        old = item.current_revision
        if old is None or old.schema_version.type_slug != "model":
            blocked.append({"id":item.public_id,"error":"missing_or_wrong_revision"})
        elif old.schema_version.version == 1:
            try:
                validate_model(old.display_name, old.properties, target.json_schema)
            except InvalidModel as error:
                blocked.append({"id":item.public_id, "error":str(error)})
            else:
                pending.append({"id":item.public_id, "revision":f"r{old.number:03d}"})
    return {"migration":MIGRATION_KEY, "pending":pending, "blocked":blocked,
            "pending_count":len(pending), "blocked_count":len(blocked)}


def apply_batch(envelope, *, expected_migration_sha):
    proof = validate_proof(envelope)
    if proof["migration_sha256"] != expected_migration_sha:
        raise CommandError("Executable migration checksum changed after frontend acceptance")
    actor = operator(proof)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK])
        _validate_backup(proof)
        target = ObjectTypeVersion.objects.get(type_slug="model", version=2)
        rows = list(CatalogItem.objects.select_for_update().filter(type_slug="model")
                    .select_related("current_revision__schema_version").order_by("pk"))
        pending = []
        for item in rows:
            old = item.current_revision
            if old is None or old.schema_version.type_slug != "model":
                raise CommandError("Broken model current revision: " + item.public_id)
            if old.schema_version.version == 1:
                try:
                    validate_model(old.display_name, old.properties, target.json_schema)
                except InvalidModel as error:
                    raise CommandError("Ambiguous incompatible v1 record: " + item.public_id + " " + str(error)) from error
                pending.append(item)
        changed = []
        for item in pending[:BATCH_SIZE]:
            old = item.current_revision
            revision = CatalogRevision.objects.create(
                item=item, number=old.number + 1, schema_version=target,
                display_name=old.display_name, properties=old.properties, created_by=actor,
            )
            item.current_revision = revision
            item.save(update_fields=["current_revision"])
            record_catalog_event(item=item, revision=revision, actor=actor, action="schema_migrated")
            ProductionMigrationReceipt.objects.create(
                item=item, source_revision=old, target_revision=revision, actor=actor,
                candidate_id=proof["candidate_id"], migration_key=MIGRATION_KEY,
                migration_sha256=proof["migration_sha256"], app_commit=proof["app_commit"],
                recovery_id=proof["recovery_id"],
                recovery_manifest_sha256=proof["recovery_manifest_sha256"],
                approved_report_sha256=proof["approved_report_sha256"],
            )
            changed.append(item.public_id)
        return {"migration":MIGRATION_KEY, "changed":len(changed), "public_ids":changed,
                "remaining":len(pending) - len(changed), "candidate_id":proof["candidate_id"]}
