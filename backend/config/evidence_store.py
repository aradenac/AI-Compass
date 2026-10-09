"""Private content-addressed immutable evidence bytes, no public/static URLs.

Invariant: disk finalize BEFORE metadata transaction. A crash may leave an
orphan disk file, but can never commit a pointer to an incomplete temp file.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from django.conf import settings
from django.db import transaction

from .models import CatalogAuditEvent, EvidenceBlob, EvidenceLink

DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
EXTENSIONS = {
    ".pdf": ("application/pdf", lambda b: b.startswith(b"%PDF-")),
    ".png": ("image/png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    ".webp": ("image/webp", lambda b: b.startswith(b"RIFF") and b[8:12] == b"WEBP"),
    ".zip": ("application/zip", lambda b: b.startswith((b"PK\x03\x04", b"PK\x05\x06"))),
    ".txt": ("text/plain", None),
    ".md": ("text/markdown", None),
    ".csv": ("text/csv", None),
    ".json": ("application/json", None),
}


class EvidenceError(ValueError):
    pass


class BrokenEvidence(EvidenceError):
    pass


def store_root():
    root = Path(settings.EVIDENCE_STORE_ROOT)
    if not root.is_absolute() or root.is_symlink():
        raise EvidenceError("Evidence store must be an absolute, non-symlink private directory")
    if not root.is_dir():
        raise EvidenceError("Private evidence volume is not mounted")
    return root


def _private_dir(parent, name):
    directory = parent / name
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise EvidenceError("Invalid private evidence directory")
    return directory


def _sync_dir(directory):
    fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def blob_path(digest, root=None):
    if not DIGEST_RE.fullmatch(digest):
        raise EvidenceError("Invalid SHA-256 identifier")
    base = root if root is not None else store_root()
    return base / "blobs" / digest[:2] / digest[2:4] / digest


def clean_filename(name):
    if not isinstance(name, str):
        raise EvidenceError("Filename is mandatory")
    name = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if (not name or len(name) > 180 or name in (".", "..") or
            any(ord(ch) < 32 or ord(ch) == 127 for ch in name)):
        raise EvidenceError("Invalid filename")
    return name


def validate_signature(filename, head, stream_path):
    extension = Path(filename).suffix.lower()
    config = EXTENSIONS.get(extension)
    if not config:
        raise EvidenceError("Unsupported file type")
    media_type, checker = config
    if checker is not None and not checker(head):
        raise EvidenceError("File contents do not match extension")
    if checker is None:
        try:
            data = stream_path.read_bytes()
            decoded = data.decode("utf-8")
            if "\x00" in decoded:
                raise EvidenceError("Text document contains NUL bytes")
            if extension == ".json":
                json.loads(decoded)
        except (UnicodeError, ValueError) as error:
            raise EvidenceError("Invalid UTF-8 or JSON document") from error
    return media_type


def stream_and_finalize(upload):
    root = store_root()
    incoming = _private_dir(root, ".incoming")
    filename = clean_filename(upload.name)
    extension = Path(filename).suffix.lower()
    if extension not in EXTENSIONS:
        raise EvidenceError("Unsupported evidence file extension")
    if upload.size is not None and (upload.size < 1 or upload.size > settings.EVIDENCE_MAX_BYTES):
        raise EvidenceError("Evidence file must be nonempty and at most 16 MiB")

    descriptor, temporary = tempfile.mkstemp(prefix="upload-", suffix=".part", dir=incoming)
    temp_path = Path(temporary)
    digest = hashlib.sha256()
    size = 0
    header = b""
    try:
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            for chunk in upload.chunks(chunk_size=64 * 1024):
                size += len(chunk)
                if size > settings.EVIDENCE_MAX_BYTES:
                    raise EvidenceError("Evidence exceeds the configured size limit")
                if len(header) < 16:
                    header += chunk[:16 - len(header)]
                digest.update(chunk)
                output.write(chunk)
            if not size:
                raise EvidenceError("Empty evidence file")
            output.flush()
            os.fsync(output.fileno())
        media_type = validate_signature(filename, header, temp_path)
        checksum = digest.hexdigest()
        first = _private_dir(root, "blobs")
        second = _private_dir(first, checksum[:2])
        third = _private_dir(second, checksum[2:4])
        final = third / checksum
        try:
            os.link(temp_path, final, follow_symlinks=False)  # exclusive atomic publish, never overwrite
            _sync_dir(third)
        except FileExistsError:
            verify_bytes(checksum, size=size)  # never bless corrupted preexisting payload
        return checksum, size, media_type, filename
    finally:
        temp_path.unlink(missing_ok=True)


def verify_bytes(checksum, *, size=None):
    """Always verify on read, fail closed for missing, corrupt or unsafe links."""
    path = blob_path(checksum)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise BrokenEvidence("Evidence payload is not a regular file")
            hasher = hashlib.sha256()
            total = 0
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                total += len(block)
                hasher.update(block)
        if hasher.hexdigest() != checksum or (size is not None and total != size):
            raise BrokenEvidence("Stored evidence checksum or size mismatch")
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError) as error:
        raise BrokenEvidence("Evidence payload is missing or inaccessible") from error
    return path


def attach(*, item, revision, file, actor, source="", provenance=None):
    if not item.current_revision_id:
        raise EvidenceError("Only initialized catalog items can receive evidence")
    if revision is not None and revision.item_id != item.pk:
        raise EvidenceError("Evidence revision does not belong to the target item")
    checksum, size, media_type, filename = stream_and_finalize(file)
    # Disk bytes are complete before this transaction. A rollback only leaves
    # an orphaned file detectable by reconcile_evidence, never a broken pointer.
    with transaction.atomic():
        blob, _ = EvidenceBlob.objects.get_or_create(
            sha256=checksum, defaults={"size": size, "media_type": media_type},
        )
        if blob.size != size:
            raise BrokenEvidence("Conflicting existing metadata for SHA-256")
        link = EvidenceLink.objects.create(
            blob=blob, item=item, revision=revision,
            original_filename=filename, source=source,
            provenance=provenance if provenance is not None else {}, uploaded_by=actor,
        )
        CatalogAuditEvent.objects.create(
            item=item, revision=revision or item.current_revision,
            actor=actor, action="evidence_attached",
        )
    return link


def serialize(link):
    return {
        "id": str(link.pk), "sha256": link.blob_id, "size": link.blob.size,
        "media_type": link.blob.media_type, "filename": link.original_filename,
        "source": link.source, "provenance": link.provenance,
        "item_id": link.item.public_id,
        "revision": f"r{link.revision.number:03d}" if link.revision_id else None,
        "revision_uuid": str(link.revision_id) if link.revision_id else None,
        "uploaded_by": link.uploaded_by.get_username(),
        "created_at": link.created_at.isoformat(),
        "download": "/api/v1/evidence/" + str(link.pk) + "/download",
    }
