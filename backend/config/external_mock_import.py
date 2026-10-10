"""PLAT-33: deterministic mock-only Model import with real append-only persistence.

A *contract rehearsal*, never a source of real business data. The adapter is
disabled outside a deliberately disposable staging Server. A real-source
adapter still requires an approved source contract, origin and field mapping.
"""
import hashlib
import json
import re

from django.conf import settings
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction

from .catalog_schemas import InvalidModel, validate_model
from .catalog_services import (
    create_model, model_schema, revise_model, RevisionConflict, SchemaWriteBlocked,
)
from .evidence_store import attach, verify_bytes, BrokenEvidence
from .models import (
    ExternalImportBinding, ExternalImportBatch, ExternalImportEvent,
)

SOURCE = "mock-model-catalog-v1"
SALT = "ai-compass-plat-33-mock-preview-v1"
MAX_ROWS = 50
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
LOCK_KEY = 3330012026


class ImportInputError(ValueError):
    pass


class ImportConflict(ImportInputError):
    pass


def mock_enabled():
    return bool(getattr(settings, "EXTERNAL_MOCK_IMPORT_ENABLED", False))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def parse(payload):
    if not isinstance(payload, dict) or set(payload) != {"source_id", "rows"}:
        raise ImportInputError("Expected only source_id and rows")
    if payload["source_id"] != SOURCE:
        raise ImportInputError("Only mock-model-catalog-v1 is supported (not Demo/native)")
    rows = payload["rows"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ImportInputError("A mock source must contain 1..50 rows")
    keys = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"source_key", "name", "properties"}:
            raise ImportInputError("Row %d requires source_key, name and properties" % index)
        key = row["source_key"]
        if not isinstance(key, str) or not KEY_RE.fullmatch(key):
            raise ImportInputError("Invalid stable source key at row %d" % index)
        if key in keys:
            raise ImportInputError("Duplicate stable source key " + key)
        keys.add(key)
    try:
        digest = hashlib.sha256(canonical(payload)).hexdigest()
    except (ValueError, TypeError, OverflowError) as error:
        raise ImportInputError("Non-JSON source values are forbidden") from error
    return rows, digest


def plan(payload):
    """Entirely read-only, including validation failures and conflicts."""
    rows, digest = parse(payload)
    schema = model_schema()
    if schema is None:
        raise ImportInputError("No active Model schema available")
    bindings = {b.source_key: b for b in
                ExternalImportBinding.objects.filter(
                    source_system=SOURCE, source_key__in=[r["source_key"] for r in rows]
                ).select_related("item__current_revision", "last_import_revision")}
    known = set(schema.json_schema.get("properties", {}))
    results = []
    for row in rows:
        key = row["source_key"]
        binding = bindings.get(key)
        invalid = None
        try:
            name = validate_model(row["name"], row["properties"], schema.json_schema)
        except (InvalidModel, ValueError, TypeError) as error:
            invalid = str(error)
        revision = binding.item.current_revision if binding else None
        if invalid:
            action = "invalid"
        elif binding and (binding.item.type_slug != "model" or
                          revision is None or
                          revision.id != binding.last_import_revision_id):
            action = "conflict"
        elif not binding:
            action = "created"
        elif name == revision.display_name and row["properties"] == revision.properties:
            action = "unchanged"
        else:
            action = "revised"
        properties = row.get("properties", {})
        results.append({
            "source_key": key, "action": action,
            "model_id": binding.item.public_id if binding else None,
            "expected_revision": str(revision.pk) if revision else None,
            "unknown_fields": sorted(set(properties) - known) if isinstance(properties, dict) else [],
            "changed_fields": (
                sorted(set(properties) ^ set(revision.properties) |
                       {k for k in set(properties) & set(revision.properties)
                        if properties[k] != revision.properties[k]})
                if binding and revision and isinstance(properties, dict)
                and isinstance(revision.properties, dict) else []
            ),
            "name_changed": bool(revision and isinstance(row["name"], str)
                                 and row["name"].strip() != revision.display_name),
            "error": invalid or ("Existing Model diverged from the last source import"
                                 if action == "conflict" else None),
            "row_sha256": hashlib.sha256(canonical(row)).hexdigest(),
        })
    old_batch = ExternalImportBatch.objects.filter(input_sha256=digest).first()
    if old_batch is not None:
        events = {e.source_key: e for e in old_batch.events.select_related(
            "item__current_revision", "evidence__blob")}
        for output in results:
            prior = events.get(output["source_key"])
            if (prior is None or prior.row_sha256 != output["row_sha256"] or
                    prior.item.current_revision_id != prior.revision_id):
                output.update(action="conflict",
                              error="Previously applied batch no longer matches current data")
                continue
            if prior.evidence_id:
                try:
                    verify_bytes(prior.evidence.blob_id, size=prior.evidence.blob.size)
                except BrokenEvidence:
                    output.update(action="conflict",
                                  error="Original imported mock bytes failed integrity check")
        if len(events) != len(rows):
            raise ImportConflict("Stored batch journal is incomplete")
    blocked = any(r["action"] in ("invalid", "conflict") for r in results)
    # Store no source row values in preview or journal.
    counts = {s: sum(x["action"] == s for x in results)
              for s in ("created", "revised", "unchanged", "invalid", "conflict")}
    return {
        "source_id": SOURCE, "input_sha256": digest,
        "records": results, "counts": counts,
        "valid": not blocked, "already_imported": bool(old_batch and not blocked),
        "existing_batch_id": str(old_batch.pk) if old_batch else None,
        "target": "model", "mode": "mock-staging-only",
    }


def signed_preview(result, actor):
    if not result["valid"]:
        return None
    return signing.dumps(
        {"actor_id": actor.pk, "digest": result["input_sha256"],
         "plan": [(r["source_key"], r["action"], r["expected_revision"],
                   r["row_sha256"]) for r in result["records"]],
         "existing_batch_id": result["existing_batch_id"]},
        salt=SALT,
    )


def _verify_token(preview_token, result, actor):
    if not isinstance(preview_token, str) or len(preview_token) > 8000:
        raise ImportInputError("Preview token is required")
    try:
        expected = signing.loads(preview_token, salt=SALT, max_age=900)
    except (signing.BadSignature, signing.SignatureExpired):
        raise ImportConflict("Preview expired or was tampered with; preview again")
    actual = {
        "actor_id": actor.pk, "digest": result["input_sha256"],
        "plan": [(r["source_key"], r["action"], r["expected_revision"],
                  r["row_sha256"]) for r in result["records"]],
        "existing_batch_id": result["existing_batch_id"],
    }
    # Signing serializes tuples to JSON arrays.
    if canonical(expected) != canonical(actual):
        raise ImportConflict("Source or target changed since preview; preview again")
    if not result["valid"]:
        raise ImportConflict("Review conflicts and invalid rows before importing")


def receipt(batch, replay=False):
    return {
        "batch_id": str(batch.pk), "source_id": batch.source_system,
        "input_sha256": batch.input_sha256,
        "row_count": batch.row_count, "operator": batch.actor.get_username(),
        "created_at": batch.created_at.isoformat(),
        "already_imported": replay,
        "results": [
            {"source_key": x.source_key, "action": x.action,
             "item_id": x.item.public_id, "revision": f"r{x.revision.number:03d}",
             "revision_id": str(x.revision_id),
             "row_sha256": x.row_sha256,
             "evidence_sha256": x.evidence.blob_id if x.evidence_id else None}
            for x in batch.events.select_related(
                "item", "revision", "evidence").order_by("source_key")
        ],
    }


@transaction.atomic
def apply(payload, *, preview_token, actor):
    if not mock_enabled():
        raise ImportInputError("Mock import is disabled outside isolated staging")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])
    current = plan(payload)
    _verify_token(preview_token, current, actor)
    existing = ExternalImportBatch.objects.filter(input_sha256=current["input_sha256"]).first()
    if existing is not None:
        return receipt(existing, replay=True)
    batch = ExternalImportBatch.objects.create(
        source_system=SOURCE, input_sha256=current["input_sha256"],
        row_count=len(payload["rows"]), actor=actor,
    )
    for source, row_plan in zip(payload["rows"], current["records"]):
        key, action = row_plan["source_key"], row_plan["action"]
        if action == "created":
            item = create_model(actor=actor, name=source["name"], properties=source["properties"])
            binding = ExternalImportBinding.objects.create(
                source_system=SOURCE, source_key=key,
                item=item, last_import_revision=item.current_revision,
            )
        else:
            binding = ExternalImportBinding.objects.select_for_update().get(
                source_system=SOURCE, source_key=key
            )
            item = binding.item
            if action == "revised":
                item = revise_model(
                    item=item, actor=actor,
                    expected_revision=f"r{item.current_revision.number:03d}",
                    name=source["name"], properties=source["properties"],
                )
                binding.last_import_revision = item.current_revision
                binding.save(update_fields=["last_import_revision"])
        evidence = None
        if action in ("created", "revised"):
            # These are the exact canonical *mock row* bytes, NOT a real
            # external original. Existing evidence-store integrity applies.
            raw = canonical(source)
            evidence = attach(
                item=item, revision=item.current_revision,
                file=SimpleUploadedFile("mock-import-row.json", raw,
                                        content_type="application/json"),
                actor=actor, source="mock://model-catalog-v1/" + key,
                provenance={"kind": "mock-external-source", "batch_sha256": batch.input_sha256,
                            "source_key": key, "row_sha256": row_plan["row_sha256"]},
            )
        ExternalImportEvent.objects.create(
            batch=batch, binding=binding, item=item, revision=item.current_revision,
            evidence=evidence, source_key=key,
            row_sha256=row_plan["row_sha256"], action=action,
        )
    return receipt(batch)
