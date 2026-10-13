"""FUT-19: durable archive jobs and scoped resumable confidential download.

Request/status/list require ``archive_export`` (an explicit export grant; generic
platform read-only is insufficient). Creation, grant issuance/revocation and the
byte stream are further gated, and no secret ever appears in a URL, log or audit
entry: the raw bearer token exists only in the response body of an authorized,
CSRF-protected call.
"""
import logging

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .archive_job_services import (
    ArchiveJobError, GrantDenied, issue_grant, open_artifact, parse_range,
    request_job, resolve_grant, revoke_grant, run_job, serialize_grant,
    serialize_job, touch_grant,
)
from .auth_views import capability, json_no_store, read_json
from .models import ArchiveGrant, ArchiveJob

logger = logging.getLogger(__name__)

CHUNK = 1024 * 1024


@require_http_methods(["GET", "POST"])
@csrf_protect
@capability("archive_export")
@never_cache
def archive_jobs(request):
    """GET list/status (read-only), POST request a new durable build job."""
    if request.method == "GET":
        rows = ArchiveJob.objects.order_by("-requested_at")[:50]
        return json_no_store({"results": [serialize_job(j) for j in rows]})
    payload = read_json(request)
    if payload is None or set(payload) - {"kind"}:
        return json_no_store({"error": "invalid_payload"}, 400)
    try:
        job = request_job(actor=request.user, kind=payload.get("kind"))
    except ArchiveJobError:
        return json_no_store({"error": "invalid_kind"}, 400)
    return json_no_store({"job": serialize_job(job)}, 201)


@require_GET
@capability("archive_export")
@never_cache
def archive_job_detail(request, public_id):
    job = get_object_or_404(ArchiveJob, public_id=public_id)
    return json_no_store({"job": serialize_job(job)})


@require_POST
@csrf_protect
@capability("archive_export")
@never_cache
def archive_job_run(request, public_id):
    """Trigger the build. The heavy work runs in a durable child process; the
    request returns the job's current state without buffering archive bytes."""
    job = get_object_or_404(ArchiveJob, public_id=public_id)
    if job.state not in ("queued", "failed"):
        return json_no_store({"error": "job_not_runnable", "state": job.state}, 409)
    job = run_job(job=job)
    return json_no_store({"job": serialize_job(job)}, 201 if job.state == "complete" else 502)


@require_POST
@csrf_protect
@capability("archive_export")
@never_cache
def archive_grant(request, public_id):
    """Issue a short-lived, artifact-scoped bearer token. Revealed exactly once
    here; never placed in a URL, log or audit entry."""
    job = get_object_or_404(ArchiveJob, public_id=public_id)
    payload = read_json(request)
    if payload is None or set(payload) - {"ttl_seconds"}:
        return json_no_store({"error": "invalid_payload"}, 400)
    try:
        grant, token = issue_grant(actor=request.user, job=job,
                                   ttl_seconds=payload.get("ttl_seconds", 3600))
    except GrantDenied:
        return json_no_store({"error": "job_not_complete"}, 409)
    logger.warning("security_audit archive_grant_issued actor_id=%s job=%s grant=%s",
                   request.user.pk, job.public_id, grant.public_id)
    return json_no_store({"grant": serialize_grant(grant), "token": token}, 201)


@require_GET
@capability("archive_export")
@never_cache
def archive_grants(request, public_id):
    job = get_object_or_404(ArchiveJob, public_id=public_id)
    rows = job.grants.order_by("-issued_at")[:50]
    return json_no_store({"results": [serialize_grant(g) for g in rows]})


@require_POST
@csrf_protect
@capability("archive_export")
@never_cache
def archive_grant_revoke(request, public_id, grant_id):
    job = get_object_or_404(ArchiveJob, public_id=public_id)
    grant = get_object_or_404(ArchiveGrant, public_id=grant_id, job=job)
    revoke_grant(actor=request.user, grant=grant)
    logger.warning("security_audit archive_grant_revoked actor_id=%s grant=%s",
                   request.user.pk, grant.public_id)
    return json_no_store({"grant": serialize_grant(grant)})


def _flush(handle, start, end):
    """Stream [start, end] inclusive from a seekable binary handle, closing it."""
    try:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            block = handle.read(min(CHUNK, remaining))
            if not block:
                break
            remaining -= len(block)
            yield block
    finally:
        handle.close()


@require_GET
@never_cache
def archive_download(request, public_id):
    """Streams the immutable artifact through an Authorization bearer token.

    Authorization is enforced on **every** request including a resume, so a
    Range can never return bytes the token is not entitled to. A single
    validated byte range yields 206 with a Content-Range; an unsatisfiable range
    yields 416; no support for user-controlled filesystem paths.
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return json_no_store({"error": "invalid_or_unusable_grant"}, 401)
    token = header[len("Bearer "):].strip()
    try:
        grant = resolve_grant(token, job_public_id=public_id)
        handle, size = open_artifact(grant.job)
    except GrantDenied:
        logger.warning("security_audit archive_download_denied job=%s", public_id)
        return json_no_store({"error": "invalid_or_unusable_grant"}, 403)
    try:
        requested = parse_range(request.headers.get("Range"), size)
    except GrantDenied:
        handle.close()
        response = json_no_store({"error": "range_not_satisfiable"}, 416)
        response["Content-Range"] = f"bytes */{size}"
        return response
    touch_grant(grant)
    logger.warning("security_audit archive_download actor_id=%s job=%s range=%s",
                   getattr(grant.issued_to, "pk", None), grant.job.public_id,
                   "resume" if requested else "full")
    if requested is None:
        start, end = 0, size - 1
        status = 200
    else:
        start, end = requested
        status = 206
    response = StreamingHttpResponse(
        _flush(handle, start, end), status=status, content_type="application/zip")
    response["Content-Length"] = str(end - start + 1)
    response["Content-Disposition"] = (
        f'attachment; filename="{grant.job.public_id}.zip"')
    response["Accept-Ranges"] = "bytes"
    if status == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["ETag"] = f'"{grant.job.sha256}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response._resource_closers.append(handle.close)
    return response
