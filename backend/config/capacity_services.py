"""FUT-20: bounded, versioned capacity policy, health/headroom and login throttle.

A small versioned policy store administered only by ``platform_manage``; every
change is audited with who/when/old/new. Physical technical hard limits (free
disk, DB integrity, upload parser, archive decompression guards) are detected and
explained, never administrable. Policy applies prospectively: it warns about the
current state and never rewrites pinned historical data. No generic rule engine.
"""
import hashlib
import shutil
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .evidence_store import store_root
from .models import (AccessThrottle, ArchiveJob, CapacityPolicy,
                     CapacityPolicyEvent, EvidenceBlob)

# Incoming evidence is bounded by format/verifier support, not a business knob.
HARD_UPLOAD_BYTES = 16 * 1024 * 1024
HARD_MAX_RECORDS = 200000
HARD_ARCHIVE_BYTES = 2 * 1024 ** 3
DEFAULT_THRESHOLDS = {
    "evidence_warn_bytes": 8 * 1024 ** 3,
    "disk_warn_percent": 80,
    "archive_concurrency_warn": 4,
    "upload_quota_warn_bytes": 2 * 1024 ** 3,
}
# Conservative hard bounds keep an administrator from disabling integrity guards.
BOUNDS = {
    "evidence_warn_bytes": (0, 1 << 50),
    "disk_warn_percent": (1, 99),
    "archive_concurrency_warn": (0, 64),
    "upload_quota_warn_bytes": (0, 1 << 50),
}


class CapacityError(ValueError):
    pass


# --- policy administration --------------------------------------------------

def policy():
    return CapacityPolicy.objects.filter(is_active=True).order_by("-version").first()


def serialize_policy(row):
    if row is None:
        return {"version": 0, "active": False, **DEFAULT_THRESHOLDS,
                "note": "No active policy; built-in defaults and hard limits apply."}
    return {"version": row.version, "active": True,
            "evidence_warn_bytes": row.evidence_warn_bytes,
            "disk_warn_percent": row.disk_warn_percent,
            "archive_concurrency_warn": row.archive_concurrency_warn,
            "upload_quota_warn_bytes": row.upload_quota_warn_bytes,
            "threshold_factors": row.threshold_factors,
            "updated_by": row.updated_by.get_username(),
            "updated_at": row.updated_at.isoformat()}


def _thresholds():
    row = policy()
    values = dict(DEFAULT_THRESHOLDS)
    if row is not None:
        for name in DEFAULT_THRESHOLDS:
            values[name] = getattr(row, name)
    return values


def _validate(values):
    clean = {}
    for name, (low, high) in BOUNDS.items():
        value = values.get(name, DEFAULT_THRESHOLDS[name])
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise CapacityError(f"{name} must be an integer in [{low}, {high}]")
        clean[name] = value
    return clean


@transaction.atomic
def configure_policy(*, actor, **values):
    """Supersede the active policy. Prospective only: no historical row changes."""
    clean = _validate(values)
    current = policy()
    previous = serialize_policy(current)
    if current is not None:
        current.is_active = False
        current.save(update_fields=["is_active"])
    row = CapacityPolicy.objects.create(
        is_active=True, version=(current.version + 1) if current else 1,
        threshold_factors=values.get("threshold_factors", {}) or {},
        updated_by=actor, **clean,
    )
    CapacityPolicyEvent.objects.create(actor=actor, action="updated",
                                       previous=previous, applied=serialize_policy(row))
    return row


# --- health / headroom ------------------------------------------------------

def _dir_free(path):
    try:
        free = shutil.disk_usage(path).free
    except OSError:
        return None
    return free


def metrics():
    """Current indicators plus configurable-warning and hard-limit clarity.

    Every entry is ``{value, warn_at, state}`` where state is ``ok``,
    ``warning`` or ``hard``; hard limits are technical, not administrable.
    """
    thresholds = _thresholds()
    evidence = EvidenceBlob.objects.aggregate(total=Sum("size"), count=Count("sha256"))
    evidence_total = evidence["total"] or 0
    evidence_count = evidence["count"] or 0
    free = _dir_free(store_root())
    used_percent = None
    if free is not None:
        usage = shutil.disk_usage(store_root())
        used_percent = round(usage.used * 100 / usage.total) if usage.total else 0
    open_jobs = ArchiveJob.objects.filter(state__in=("queued", "running")).count()

    def state(value, warn_at):
        if value is None or warn_at is None:
            return "unknown"
        return "warning" if value >= warn_at else "ok"

    return {
        "evidence_bytes": {"value": evidence_total,
                           "warn_at": thresholds["evidence_warn_bytes"],
                           "state": state(evidence_total, thresholds["evidence_warn_bytes"])},
        "evidence_count": {"value": evidence_count,
                           "hard_max": HARD_MAX_RECORDS, "state": "ok"},
        "disk_used_percent": {"value": used_percent,
                              "warn_at": thresholds["disk_warn_percent"],
                              "state": state(used_percent, thresholds["disk_warn_percent"])},
        "archive_concurrency": {"value": open_jobs,
                                "warn_at": thresholds["archive_concurrency_warn"],
                                "state": state(open_jobs, thresholds["archive_concurrency_warn"])},
        "hard_limits": {"evidence_upload_bytes": HARD_UPLOAD_BYTES,
                        "records": HARD_MAX_RECORDS,
                        "archive_uncompressed_bytes": HARD_ARCHIVE_BYTES,
                        "administrable": False},
        "policy": serialize_policy(policy()),
    }


# --- durable login throttle -------------------------------------------------

THROTTLE_MAX_FAILURES = 5
THROTTLE_LOCK_SECONDS = 900


def _key(*parts):
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _row(key):
    return AccessThrottle.objects.filter(key_digest=key).first()


def is_locked(*, identifier, ip=""):
    key = _key("login", identifier.lower(), ip)
    row = _row(key)
    if row is None or row.locked_until is None:
        return False
    return row.locked_until > timezone.now()


@transaction.atomic
def record_failure(*, identifier, ip=""):
    key = _key("login", identifier.lower(), ip)
    row = AccessThrottle.objects.select_for_update().filter(key_digest=key).first()
    now = timezone.now()
    if row is None:
        row = AccessThrottle.objects.create(key_digest=key)
    row.failures += 1
    row.last_failure_at = now
    if row.failures >= THROTTLE_MAX_FAILURES:
        row.locked_until = now + timedelta(seconds=THROTTLE_LOCK_SECONDS)
    row.save()
    return row


@transaction.atomic
def clear_failures(*, identifier, ip=""):
    AccessThrottle.objects.filter(
        key_digest=_key("login", identifier.lower(), ip)).delete()
