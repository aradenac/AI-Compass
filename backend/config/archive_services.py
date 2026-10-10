"""PLAT-30: portable, consistent and independently verifiable native export.

This is a logical history/evidence archive, not a replacement for the coordinated
physical recovery point. No migrations or catalog data are modified.
"""
import hashlib
import json
import os
import stat
import tempfile
import zipfile

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

from .evidence_store import blob_path, store_root
from .models import EvidenceBlob

FORMAT = "ai-compass-native"
VERSION = 1
MAX_RECORDS = 200000
MAX_UNCOMPRESSED_BYTES = 2 * 1024 ** 3


class ArchiveError(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       cls=DjangoJSONEncoder, allow_nan=False) + "\n").encode("utf-8")


def _model_spec(model):
    relations = []
    for field in model._meta.concrete_fields:
        if field.is_relation and (field.many_to_one or field.one_to_one):
            target = field.remote_field.model._meta.label_lower
            if target != "auth.user" and not target.startswith("config."):
                raise ArchiveError("Unsupported external relation in archive schema")
            relations.append({"field": field.name, "target": target,
                              "uses_pk": bool(field.primary_key)})
    return {"model": model._meta.label_lower,
            "path": "records/" + model._meta.label_lower + ".ndjson",
            "relations": relations}


def _zipinfo(name):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


class _Member:
    def __init__(self, archive, manifest_files, name, budget):
        self.archive = archive
        self.files = manifest_files
        self.name = name
        self.budget = budget
        self.digest = hashlib.sha256()
        self.size = 0

    def __enter__(self):
        self.handle = self.archive.open(_zipinfo(self.name), "w", force_zip64=True)
        return self

    def write(self, data):
        self.size += len(data)
        self.budget[0] += len(data)
        if self.budget[0] > MAX_UNCOMPRESSED_BYTES:
            raise ArchiveError("Export exceeds configured uncompressed size limit")
        self.handle.write(data)
        self.digest.update(data)

    def __exit__(self, typ, value, traceback):
        self.handle.close()
        if typ is None:
            self.files[self.name] = {"sha256": self.digest.hexdigest(), "size": self.size}


def _add(archive, files, path, value, budget):
    with _Member(archive, files, path, budget) as entry:
        entry.write(canonical(value))


def _users():
    records = []
    for user in get_user_model().objects.prefetch_related("groups").order_by("pk").iterator(chunk_size=200):
        records.append({"id": str(user.pk), "username": user.get_username(),
                        "is_active": user.is_active,
                        "roles": sorted(group.name for group in user.groups.all())})
        if len(records) > MAX_RECORDS:
            raise ArchiveError("Too many authentication identities for bounded export")
    return records


def _original_bytes(archive, files, budget):
    if not EvidenceBlob.objects.exists():
        return 0
    # Refuse an absent or symlinked evidence mount even if metadata is present.
    store_root()
    count = 0
    for blob in EvidenceBlob.objects.order_by("sha256").iterator(chunk_size=200):
        digest = blob.sha256
        path = blob_path(digest)
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ArchiveError("Evidence is not a regular file")
                path_in_zip = "evidence/blobs/" + digest
                with _Member(archive, files, path_in_zip, budget) as target:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        target.write(block)
                    if target.digest.hexdigest() != digest or target.size != blob.size:
                        raise ArchiveError("Evidence hash or length mismatch; export aborted")
        except (OSError, ValueError) as exc:
            raise ArchiveError("Missing, unsafe or corrupt original evidence; export aborted") from exc
        count += 1
    return count


def _snapshot_boundary():
    """Require a dedicated read-only repeatable-read transaction in production."""
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SELECT transaction_timestamp()")
        return cursor.fetchone()[0].isoformat()


def build_native_export():
    """Return seekable temporary file; caller owns it. Never return partial output."""
    output = tempfile.TemporaryFile(mode="w+b")
    try:
        with transaction.atomic():
            # Must be the first SQL operation in this transaction.
            boundary = _snapshot_boundary()
            models = sorted(apps.get_app_config("config").get_models(),
                            key=lambda model: model._meta.label_lower)
            files, total, budget = {}, 0, [0]
            schema = {"format": FORMAT, "version": VERSION, "models": []}
            with zipfile.ZipFile(output, "w", allowZip64=True) as archive:
                users = _users()
                _add(archive, files, "subjects.json", {"users": users,
                     "note": "Identity references only; passwords, credentials, emails, "
                             "sessions and permission grants are excluded."}, budget)
                for model in models:
                    spec = _model_spec(model)
                    count = 0
                    with _Member(archive, files, spec["path"], budget) as target:
                        for instance in model._default_manager.order_by("pk").iterator(chunk_size=200):
                            # Django's serializer retains original JSONField values and all
                            # scalar/FK fields, including UUIDs and explicit nulls.
                            value = json.loads(serializers.serialize("json", [instance]))[0]
                            target.write(canonical(value))
                            count += 1
                            total += 1
                            if total > MAX_RECORDS:
                                raise ArchiveError("Export exceeds configured record limit")
                    spec["count"] = count
                    schema["models"].append(spec)
                _add(archive, files, "schema.json", schema, budget)
                original_count = _original_bytes(archive, files, budget)
                if len(files) + 1 > 10000:
                    raise ArchiveError("Export exceeds offline verifier ZIP member limit")
                manifest = {
                    "format": FORMAT, "version": VERSION, "complete": True,
                    "snapshot": {"isolation": "repeatable_read", "boundary": boundary},
                    "record_count": total, "evidence_blob_count": original_count,
                    "subjects": len(users), "files": files,
                    "included": "All config ORM rows, typed schemas, revisions, "
                                "relations, migration/audit history, and original evidence bytes",
                    "excluded": "Passwords, password hashes, sessions, credentials, "
                                "emails, permission secrets, Demo/localStorage, unreferenced disk orphans",
                }
                archive.writestr(_zipinfo("manifest.json"), canonical(manifest))
        output.seek(0)
        return output
    except Exception:
        output.close()
        raise
