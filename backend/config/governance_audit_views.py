"""FUT-17: maintenance-only, no-store, read-only audit inspection and export."""
import csv
import io
import json

from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .auth_views import capability, json_no_store
from . import governance_audit_services as audit


def _error(exc):
    return json_no_store({"error": str(exc)},
                         403 if isinstance(exc, audit.HiddenAudit) else 400)


def _filtered(request):
    return audit.parse(request.GET, request.user)


@require_GET
@never_cache
@capability("audit_view")
def collection(request):
    if "format" in request.GET:
        return json_no_store({"error": "use_export_endpoint"}, 400)
    try:
        filters = _filtered(request)
        rows = audit.collect(filters, request.user)
    except (audit.InvalidAudit, audit.HiddenAudit) as exc:
        return _error(exc)
    offset = (filters["page"] - 1) * audit.PAGE_SIZE
    return json_no_store({
        "results": rows[offset:offset + audit.PAGE_SIZE],
        "page": filters["page"], "page_size": audit.PAGE_SIZE,
        "has_more": len(rows) > offset + audit.PAGE_SIZE,
        "limited": len(rows) > audit.MAX_ROWS,
        "sources": sorted(audit.allowed_sources(request.user)),
        "privacy": "authorized_metadata_only; source detail restricted",
        "capture": "existing_immutable_committed_sources_only",
    })


@require_GET
@never_cache
@capability("audit_view")
def detail(request, event_key):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    try:
        source, pk = event_key.split(":", 1)
        data = audit.find(source, pk, request.user)
    except (audit.InvalidAudit, audit.HiddenAudit, ValueError) as exc:
        return _error(exc)
    if data is None:
        return json_no_store({"error": "event_not_found"}, 404)
    return json_no_store(data)


@require_GET
@never_cache
@capability("audit_view")
def history(request, object_id):
    if set(request.GET) - {"page", "source"}:
        return json_no_store({"error": "invalid_filter"}, 400)
    try:
        params = request.GET.copy()
        params["object_id"] = object_id
        filters = audit.parse(params, request.user)
        matches = audit.collect(filters, request.user)
    except (audit.InvalidAudit, audit.HiddenAudit) as exc:
        return _error(exc)
    offset = (filters["page"]-1) * audit.PAGE_SIZE
    return json_no_store({"object_id": object_id,
        "results": matches[offset:offset+audit.PAGE_SIZE],
        "page": filters["page"], "has_more": len(matches) > offset+audit.PAGE_SIZE,
        "limited": len(matches) > audit.MAX_ROWS})


@require_GET
@never_cache
@capability("audit_view")
def export(request):
    try:
        filters = _filtered(request)
        fmt = request.GET.get("format", "json")
        if fmt not in ("json", "csv"):
            raise audit.InvalidAudit("unsupported_format")
        rows = audit.collect(filters, request.user)
    except (audit.InvalidAudit, audit.HiddenAudit) as exc:
        return _error(exc)
    if len(rows) > audit.MAX_ROWS:
        return json_no_store({"error": "export_limit_exceeded",
                              "detail": "Narrow actor, type or date filters."}, 422)
    # Explicit list-only export: no hidden source content or account details.
    fields = ("id", "occurred_at", "actor", "operation", "source",
              "object_type", "object_id", "revision", "revision_id",
              "origin", "correlation_id")
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "'" + str(row[key]) if str(row.get(key, "")).startswith(
                ("=", "+", "-", "@", "\t", "\r", "\n")) else row.get(key)
                for key in fields})
        data = buf.getvalue()
        content_type = "text/csv; charset=utf-8"
    else:
        data = json.dumps({"results": [{k: r.get(k) for k in fields} for r in rows],
                           "coverage": "persisted_events_only", "filtered": True},
                          ensure_ascii=False)
        content_type = "application/json; charset=utf-8"
    result = HttpResponse(data, content_type=content_type)
    result["Content-Disposition"] = 'attachment; filename="ai-compass-governance-audit.' + fmt + '"'
    result["Cache-Control"] = "no-store"
    result["X-Content-Type-Options"] = "nosniff"
    return result
