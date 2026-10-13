"""FUT-19: durable archive jobs, scoped resumable download grants and audit.

An archive is produced by a **durable server-managed job**, never inside an HTTP
request: the build runs in a separate process (``build_archive_job`` management
command) that writes one immutable artifact plus a verification manifest, so a
multi-GiB confidential archive is never serialized in API memory. Bytes are
streamed to a client through a short-lived, artifact-scoped bearer token whose
digest alone is stored; the raw token is revealed once and never logged.
"""
import hashlib
import json
import os
import secrets
import stat
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .catalog_ids import new_public_id, uuid7
from .models import ArchiveAccessEvent, ArchiveGrant, ArchiveJob
from .native_archive_verifier import VerificationError, verify

KINDS = frozenset({"native", "full_recovery"})
REASON_INVALID_KIND = "invalid_kind"
REASON_BUILD_FAILED = "build_failed"
REASON_VERIFY_FAILED = "verification_failed"
REASON_STORAGE_UNAVAILABLE = "storage_unavailable"
DEFAULT_TTL = 3600


class ArchiveJobError(ValueError):
    pass


class GrantDenied(RuntimeError):
    """Fail-closed: the download grant is not usable in its current state."""


def _ident(prefix):
    return new_public_id(prefix) + "-" + uuid7().hex[-12:]


def store_root():
    root = Path(settings.ARCHIVE_STORE_ROOT)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def _audit(*, actor, job, action, detail=None):
    """Append-only attribution event; never records a token or confidential bytes."""
    return ArchiveAccessEvent.objects.create(
        actor=actor, job=job, action=action, detail=detail or {})


# --- job lifecycle ----------------------------------------------------------

def request_job(*, actor, kind):
    """Create a queued durable job. Creation is separate from download rights."""
    if kind not in KINDS:
        raise ArchiveJobError("Unsupported archive kind")
    job = ArchiveJob.objects.create(public_id=_ident("agr"), kind=kind,
                                    state="queued", requested_by=actor)
    _audit(actor=actor, job=job, action="requested", detail={"kind": kind})
    return job


def run_job(*, job):
    """Build one immutable artifact in a transient child process, then verify it.

    The management command is invoked with only the job's public id, exits
    nonzero on any failure and touches no arbitrary path; all output lands inside
    the private archive store. A crash leaves a ``failed`` job with a
    machine-readable reason and no published artifact.
    """
    job.state = "running"
    job.started_at = timezone.now()
    job.save(update_fields=["state", "started_at"])
    completed = subprocess.run(
        ["python", "manage.py", "build_archive_job", job.public_id],
        cwd="/app", capture_output=True, text=True, timeout=settings.ARCHIVE_JOB_TIMEOUT,
    )
    if completed.returncode != 0:
        # stderr is a fixed reason token from the command; never echo raw output.
        job.state = "failed"
        job.reason = (completed.stderr.strip().splitlines() or [REASON_BUILD_FAILED])[-1][:120]
        job.completed_at = timezone.now()
        job.save(update_fields=["state", "reason", "completed_at"])
        _audit(actor=None, job=job, action="failed", detail={"reason": job.reason})
    # The child process published the artifact and updated the row; reload so the
    # caller (and the HTTP response) reflects the real terminal state.
    job.refresh_from_db()
    return job


def record_artifact(*, job, path):
    """Called by the build command: verify, then publish the immutable artifact.

    Publication is a hard link from a fully written temp file (atomic, never
    overwrites), so a partially written archive can never appear complete.
    """
    try:
        result = verify(path)
    except (VerificationError, OSError) as error:
        raise ArchiveJobError(REASON_VERIFY_FAILED) from error
    digest = result["archive_sha256"]
    final = store_root() / f"{job.public_id}-{digest}.zip"
    if not final.exists():
        try:
            os.link(path, final, follow_symlinks=False)
        except FileExistsError:
            pass
    job.state = "complete"
    job.reason = ""
    job.size_bytes = final.stat().st_size
    job.sha256 = digest
    job.artifact_path = str(final)
    job.manifest = {"format": result["format"], "version": result["version"],
                    "records": result["records"], "models": result["models"],
                    "original_evidence_blobs": result["original_evidence_blobs"],
                    "verified": True}
    job.completed_at = timezone.now()
    job.save(update_fields=["state", "reason", "size_bytes", "sha256",
                            "artifact_path", "manifest", "completed_at"])
    _audit(actor=None, job=job, action="built",
           detail={"size_bytes": job.size_bytes, "sha256": digest})
    return job


def serialize_job(job):
    return {
        "public_id": job.public_id, "kind": job.kind, "state": job.state,
        "reason": job.reason or None, "size_bytes": job.size_bytes,
        "sha256": job.sha256 or None, "manifest": job.manifest,
        "requested_at": job.requested_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


# --- download grants --------------------------------------------------------

def _digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def issue_grant(*, actor, job, ttl_seconds=DEFAULT_TTL):
    """Mint a random bearer token; return (grant, raw_token). Raw token is returned
    exactly once and only its digest is persisted."""
    if job.state != "complete" or not job.artifact_path:
        raise GrantDenied("Only a complete archive can be granted")
    ttl = max(60, min(int(ttl_seconds), 24 * 3600))
    token = secrets.token_urlsafe(48)
    grant = ArchiveGrant.objects.create(
        public_id=_ident("agr"), job=job, token_digest=_digest(token),
        issued_to=actor, scope="download",
        expires_at=timezone.now() + timedelta(seconds=ttl),
    )
    _audit(actor=actor, job=job, action="grant_issued",
           detail={"grant": grant.public_id, "ttl_seconds": ttl})
    return grant, token


def revoke_grant(*, actor, grant):
    if grant.revoked_at is None:
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])
        _audit(actor=actor, job=grant.job, action="grant_revoked",
               detail={"grant": grant.public_id})
    return grant


def resolve_grant(token, *, job_public_id):
    """Fail-closed resolution: the token must match the bound artifact, be
    unexpired and unrevoked. Every rejection is the same opaque error."""
    if not token or not isinstance(token, str) or len(token) > 200:
        raise GrantDenied("Invalid or unusable download grant")
    digest = _digest(token)
    grant = (ArchiveGrant.objects.select_related("job")
             .filter(token_digest=digest).first())
    if grant is None or grant.job.public_id != job_public_id:
        raise GrantDenied("Invalid or unusable download grant")
    if grant.revoked_at is not None or grant.expires_at <= timezone.now():
        raise GrantDenied("Invalid or unusable download grant")
    if grant.job.state != "complete" or not grant.job.artifact_path:
        raise GrantDenied("Invalid or unusable download grant")
    return grant


def serialize_grant(grant):
    return {
        "public_id": grant.public_id, "job": grant.job.public_id,
        "scope": grant.scope, "expires_at": grant.expires_at.isoformat(),
        "revoked": grant.revoked_at is not None,
    }


# --- streaming --------------------------------------------------------------

def open_artifact(job):
    """Open the immutable artifact for streaming, refusing a symlink/non-regular
    file and anything outside the private archive store."""
    path = Path(job.artifact_path)
    root = Path(settings.ARCHIVE_STORE_ROOT).resolve()
    if not path.is_absolute() or root not in path.resolve().parents:
        raise GrantDenied("Artifact is not in the private store")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise GrantDenied("Artifact bytes are unavailable") from error
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        os.close(descriptor)
        raise GrantDenied("Artifact is not a regular file")
    return os.fdopen(descriptor, "rb"), info.st_size


def parse_range(header, size):
    """A single byte range only; anything malformed or out of bounds is refused,
    so a resume request can never return the wrong bytes."""
    if not header:
        return None
    header = header.strip()
    if not header.startswith("bytes=") or "," in header:
        raise GrantDenied("Unsupported or invalid range")
    spec = header[len("bytes="):]
    start_text, _, end_text = spec.partition("-")
    if not start_text.isdigit():
        raise GrantDenied("Unsupported or invalid range")
    start = int(start_text)
    if end_text:
        if not end_text.isdigit():
            raise GrantDenied("Unsupported or invalid range")
        end = int(end_text)
    else:
        end = size - 1
    if start > end or start >= size or end >= size:
        raise GrantDenied("Range is outside the artifact")
    return start, end


def touch_grant(grant):
    grant.last_used_at = timezone.now()
    grant.save(update_fields=["last_used_at"])
