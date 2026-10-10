"""PLAT-31 native v1 restore: preview, clean disposable apply and exact replay.

No arbitrary SQL, archive code, schema mutation, credential import or production
restore. All relational inserts are one atomic transaction; immutable evidence
bytes are finalized before the transaction commits.
"""
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone

from config.archive_services import _model_spec
from config.evidence_store import (
    _private_dir, _sync_dir, blob_path, store_root, verify_bytes,
)
from config.models import ObjectTypeVersion
from config.native_archive_verifier import verify, VerificationError
from restore_tracking.models import NativeRestore, NativeRestoreEvent

CANDIDATE = re.compile(r"^[0-9a-f]{16}$")
BATCH = 100
MAX_ARCHIVE_ROWS = 200000


class RestoreError(ValueError):
    pass


def require_disposable():
    """Multiple independent fixed checks, not a user-supplied target URL."""
    if (os.environ.get("AI_COMPASS_STAGING") != "1"
        or os.environ.get("AI_COMPASS_NATIVE_RESTORE_TEST") != "1"
        or not CANDIDATE.fullmatch(os.environ.get("AI_COMPASS_STAGING_CANDIDATE", ""))
        or os.environ.get("DB_NAME") != "ai_compass_restore_verify"
        or os.environ.get("DB_USER") != "ai_compass_restore"
        or os.environ.get("DB_HOST") != "db"):
        raise RestoreError("Native apply/preview requires a dedicated disposable staging Server")


def _operator(name):
    User = get_user_model()
    try:
        actor = User.objects.get(username=name, is_active=True)
    except User.DoesNotExist as exc:
        raise RestoreError("Active named operator account required") from exc
    if not (actor.has_perm("auth.platform_manage")
            or actor.has_perm("auth.maintenance_triage")):
        raise RestoreError("Operator lacks platform-management or maintenance authority")
    return actor


def _records(path, expected_models):
    """Verifier ran first; still explicitly reject unsupported field/schema drift."""
    with zipfile.ZipFile(path) as source:
        schema = json.loads(source.read("schema.json"))
        subjects = json.loads(source.read("subjects.json"))["users"]
        records = {}
        for spec in schema["models"]:
            name = spec["model"]
            if name not in expected_models:
                raise RestoreError("Unsupported model requires reviewed adapter: " + name)
            model = expected_models[name]
            if spec["relations"] != _model_spec(model)["relations"]:
                raise RestoreError("Foreign-key contract changed: " + name)
            expected_fields = {f.name for f in model._meta.concrete_fields if not f.primary_key
                               and f.serialize}
            rows = []
            with source.open(spec["path"]) as stream:
                for line in stream:
                    entry = json.loads(line)
                    if set(entry) != {"model", "pk", "fields"}:
                        raise RestoreError("Unexpected serialized record contract: " + name)
                    if set(entry["fields"]) != expected_fields:
                        raise RestoreError("Unsupported field layout: " + name)
                    rows.append(entry)
            records[name] = rows
    if sum(len(x) for x in records.values()) > MAX_ARCHIVE_ROWS:
        raise RestoreError("Archive row limit exceeded")
    # Catalog identities and history must be unambiguous before any mutation.
    objects = records.get("config.catalogitem", [])
    names = [r["fields"]["public_id"] for r in objects]
    if len(names) != len(set(names)):
        raise RestoreError("Duplicate permanent public IDs")
    for row in objects:
        if row["fields"]["type_slug"] not in {
            "model", "provider", "harness", "framework", "setup_guide", "research_source",
            "watch_entry", "forecast", "evaluation", "recommendation",
            "discussion_thread", "discussion_message", "task", "test_case", "campaign",
            "measured_solution"
        }:
            # Unknown *registered* types can be exported; fail rather than guess an adapter.
            if row["fields"]["type_slug"] not in {
                r["fields"]["type_slug"] for r in records.get("config.objecttypeversion", [])
            }:
                raise RestoreError("Unsupported catalog identity type")
    return records, subjects


def _schema_mapping(records):
    """Immutable schema identity mapping only for identical registered definitions."""
    mapping = {}
    local = {(r.type_slug, r.version): r for r in ObjectTypeVersion.objects.all()}
    for row in records.get("config.objecttypeversion", []):
        fields = row["fields"]
        key = (fields["type_slug"], fields["version"])
        target = local.get(key)
        if target is None or target.json_schema != fields["json_schema"]:
            raise RestoreError("Unknown/changed schema needs explicit reviewed adapter: %s@%s" % key)
        mapping[str(row["pk"])] = str(target.pk)
    if len(mapping) != len(records.get("config.objecttypeversion", [])):
        raise RestoreError("Ambiguous schema registry mapping")
    return mapping


def _is_clean(models):
    return (not NativeRestore.objects.filter(state="committed").exists()
            and not any(model.objects.exists() for label, model in models.items()
                        if label != "config.objecttypeversion"))


def _dependency_order(records, models):
    """Topological table inserts; break only CatalogItem's revision pointer cycle."""
    dependencies = {}
    for name in records:
        spec = _model_spec(models[name])
        dependencies[name] = {
            relation["target"] for relation in spec["relations"]
            if relation["target"] in records and relation["target"] != name
            and not (name == "config.catalogitem"
                     and relation["field"] == "current_revision")
        }
    remaining, result = set(dependencies), []
    while remaining:
        ready = sorted(m for m in remaining if not (dependencies[m] & remaining))
        if not ready:
            raise RestoreError("Circular schema dependency requires reviewed adapter")
        result.extend(ready)
        remaining.difference_update(ready)
    return result


def _value(field, value):
    if value is None:
        return None
    if field.is_relation:
        return field.target_field.to_python(value)
    return field.to_python(value)


def _insert_model(model, rows, users, schemas):
    if not rows:
        return
    fields = [f for f in model._meta.concrete_fields]
    columns = ", ".join(connection.ops.quote_name(f.column) for f in fields)
    marks = ", ".join(["%s"] * len(fields))
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (
        connection.ops.quote_name(model._meta.db_table), columns, marks)
    values = []
    for row in rows:
        args = []
        for field in fields:
            raw = row["pk"] if field.primary_key else row["fields"][field.name]
            if field.is_relation and raw is not None:
                label = field.remote_field.model._meta.label_lower
                if label == "auth.user":
                    try:
                        raw = users[str(raw)]
                    except KeyError as exc:
                        raise RestoreError("Unmapped attribution identity") from exc
                elif label == "config.objecttypeversion":
                    try:
                        raw = schemas[str(raw)]
                    except KeyError as exc:
                        raise RestoreError("Unsupported schema reference") from exc
            if model._meta.label_lower == "config.catalogitem" and field.name == "current_revision":
                raw = None  # Set after exact historical revisions have been inserted.
            typed = _value(field, raw)
            args.append(field.get_db_prep_save(typed, connection))
        values.append(tuple(args))
        if len(values) >= BATCH:
            with connection.cursor() as cursor:
                cursor.executemany(sql, values)
            values.clear()
    if values:
        with connection.cursor() as cursor:
            cursor.executemany(sql, values)


def _restore_current(records):
    rows = records.get("config.catalogitem", [])
    with connection.cursor() as cursor:
        for row in rows:
            revision = row["fields"]["current_revision"]
            if revision is not None:
                cursor.execute(
                    "UPDATE config_catalogitem SET current_revision_id=%s WHERE id=%s",
                    [revision, row["pk"]],
                )


def _reset_sequences(models, records):
    """Preserve integer PKs without causing next-created auto PK collisions."""
    with connection.cursor() as cursor:
        for label, rows in records.items():
            if not rows:
                continue
            model = models[label]
            pk = model._meta.pk
            if pk.get_internal_type() not in {"AutoField", "BigAutoField", "SmallAutoField"}:
                continue
            table, col = model._meta.db_table, pk.column
            cursor.execute("SELECT pg_get_serial_sequence(%s, %s)", [table, col])
            sequence = cursor.fetchone()[0]
            if sequence:
                cursor.execute("SELECT setval(%s, %s, true)",
                               [sequence, max(int(row["pk"]) for row in rows)])


def _publish_originals(path, records):
    blobs = records.get("config.evidenceblob", [])
    if not blobs:
        return 0
    root = store_root()
    base = _private_dir(root, "blobs")
    with zipfile.ZipFile(path) as archive:
        for row in blobs:
            digest = str(row["pk"])
            size = row["fields"]["size"]
            directory = _private_dir(_private_dir(base, digest[:2]), digest[2:4])
            destination = blob_path(digest)
            if destination.exists() or destination.is_symlink():
                verify_bytes(digest, size=size)
                continue
            fd, temp = tempfile.mkstemp(prefix="restore-", suffix=".part", dir=directory)
            checksum, length = hashlib.sha256(), 0
            try:
                with os.fdopen(fd, "wb") as out, archive.open("evidence/blobs/" + digest) as stream:
                    os.fchmod(out.fileno(), 0o600)
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        checksum.update(block)
                        length += len(block)
                        out.write(block)
                    out.flush()
                    os.fsync(out.fileno())
                if checksum.hexdigest() != digest or length != size:
                    raise RestoreError("Original evidence hash/length mismatch")
                try:
                    os.link(temp, destination, follow_symlinks=False)
                    _sync_dir(directory)
                except FileExistsError:
                    verify_bytes(digest, size=size)
            finally:
                os.unlink(temp)
    return len(blobs)


def _subject_mapping(subjects, digest):
    """Create disabled attribution-only accounts; never import access privileges."""
    User = get_user_model()
    mapping = {}
    usernames = set()
    for subject in subjects:
        name = subject["username"]
        if not isinstance(name, str) or not name or len(name) > 150 or name in usernames:
            raise RestoreError("Invalid or duplicate source username")
        usernames.add(name)
        if User.objects.filter(username=name).exists():
            raise RestoreError("Existing username collision needs reviewed mapping: " + name)
        account = User(username=name, is_active=False, is_staff=False, is_superuser=False)
        account.set_unusable_password()
        account.save()
        mapping[str(subject["id"])] = account.pk
    return mapping


def _check_replay(records, mapping, schemas):
    """Refuse a false idempotent success if imported histories were modified."""
    from django.core import serializers
    for label, rows in records.items():
        if label == "config.objecttypeversion":
            continue
        model = apps.get_model(label)
        if model.objects.count() != len(rows):
            raise RestoreError("Target diverged since archive restoration: " + label)
        for row in rows:
            try:
                obj = model.objects.get(pk=row["pk"])
            except model.DoesNotExist as exc:
                raise RestoreError("Restored identity missing: " + label) from exc
            live = json.loads(serializers.serialize("json", [obj]))[0]
            expected = json.loads(json.dumps(row))
            for f in model._meta.concrete_fields:
                if not f.is_relation:
                    continue
                target = f.remote_field.model._meta.label_lower
                old = expected["pk"] if f.primary_key else expected["fields"][f.name]
                if old is None:
                    continue
                replacement = mapping[str(old)] if target == "auth.user" else (
                    schemas[str(old)] if target == "config.objecttypeversion" else None)
                if replacement is not None:
                    if f.primary_key:
                        expected["pk"] = replacement
                    else:
                        expected["fields"][f.name] = replacement
            if json.dumps(live, sort_keys=True) != json.dumps(expected, sort_keys=True):
                raise RestoreError("Restored history differs from archive: " + label)
    for row in records.get("config.evidenceblob", []):
        verify_bytes(str(row["pk"]), size=row["fields"]["size"])


def inspect(path, operator, *, apply=False):
    """Preview never writes. Apply is limited to clean disposable Server stacks."""
    require_disposable()
    actor = _operator(operator)
    path = Path(path)
    try:
        report = verify(path)
    except (VerificationError, OSError) as exc:
        raise RestoreError("Invalid native archive: " + str(exc)) from exc
    digest = report["archive_sha256"]
    models = {m._meta.label_lower: m for m in apps.get_app_config("config").get_models()}
    rows, subjects = _records(path, models)
    schema_map = _schema_mapping(rows)
    order = _dependency_order(rows, models)
    previous = NativeRestore.objects.filter(archive_sha256=digest).first()
    if previous and previous.state == "committed":
        _check_replay(rows, previous.subject_map, previous.schema_map)
        return {"status": "already_imported", "sha256": digest,
                "records": report["records"], "blobs": report["original_evidence_blobs"]}
    if not _is_clean(models):
        raise RestoreError("Nonempty target or conflicting native archive; no merge/overwrite permitted")
    summary = {"status": "preview", "sha256": digest, "records": report["records"],
               "blobs": report["original_evidence_blobs"], "models": report["models"],
               "schema_mapping": schema_map, "subjects_to_disable": len(subjects),
               "target": "disposable-staging-only", "source_retained": True}
    # The preview stays read-only, even for journal tables.
    if not apply:
        return summary
    receipt, _ = NativeRestore.objects.get_or_create(
        archive_sha256=digest, defaults={"state": "prepared", "counts": report["models"]})
    NativeRestoreEvent.objects.create(
        restore=receipt, action="started", operator=actor.get_username(),
        detail={"rows": report["records"], "blobs": report["original_evidence_blobs"]})
    try:
        # No DB rows or receipt completion survive a failed batch. A retry
        # rechecks the immutable source, rewrites no objects, and restarts.
        with transaction.atomic():
            mapping = _subject_mapping(subjects, digest)
            for label in order:
                if label == "config.objecttypeversion":
                    continue  # already registered, exact schema definitions matched
                _insert_model(models[label], rows[label], mapping, schema_map)
                if label == "config.catalogrevision":
                    _restore_current(rows)
            _reset_sequences(models, rows)
            _publish_originals(path, rows)
            receipt.subject_map = {str(k): v for k, v in mapping.items()}
            receipt.schema_map = schema_map
            receipt.state = "committed"
            receipt.completed_at = timezone.now()
            receipt.save(update_fields=["subject_map", "schema_map", "state", "completed_at"])
            NativeRestoreEvent.objects.create(
                restore=receipt, action="committed", operator=actor.get_username(),
                detail={"rows": report["records"], "blobs": report["original_evidence_blobs"]})
    except Exception as exc:
        NativeRestoreEvent.objects.create(
            restore=receipt, action="failed", operator=actor.get_username(),
            detail={"type": type(exc).__name__, "reason": str(exc)[:300]})
        raise
    return dict(summary, status="imported")
