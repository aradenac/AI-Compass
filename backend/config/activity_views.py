"""PLAT-24: bounded, permission-scoped read model for immutable backend audit.

Sources are the original append-only CatalogAuditEvent and UserAccessAuditEvent
tables. No denormalized copy, retroactive event fabrication or Demo imports.
Future domains should emit transactional audit records and expose a projection here.
"""
import csv
import io
import json
from uuid import UUID

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .auth_views import active_identity, json_no_store
from .models import CatalogAuditEvent, UserAccessAuditEvent

CATALOG_TYPES = frozenset({"model", "provider", "harness", "framework", "task"})
MAX_EVENTS = 1000
PAGE_SIZE = 50
HEADERS = (
    "id", "occurred_at", "actor", "actor_roles_at_event", "business_unit",
    "operation", "object_type", "object_id", "object_name",
    "revision", "revision_id", "outcome",
)
ALLOWED_FILTERS = frozenset({"type", "actor", "action", "from", "to", "page", "format"})
# Explicit allow-list for access detail: never surface credentials, emails, tokens,
# request payloads or uncontrolled metadata from historical audit JSON.
ACCESS_DETAIL_FIELDS = frozenset({"roles", "active", "sessions_revoked"})


class BadFilter(ValueError):
    pass


class ScopeDenied(PermissionError):
    pass


def _permissions(request):
    if not active_identity(request):
        return None
    return (request.user.has_perm("auth.business_read"),
            request.user.has_perm("auth.users_manage"))


def _parse(request, perms):
    if any(k not in ALLOWED_FILTERS for k in request.GET):
        raise BadFilter("unsupported_filter")
    kind = request.GET.get("type", "all")
    if kind not in CATALOG_TYPES | {"all", "access"}:
        raise BadFilter("invalid_type")
    if kind == "access" and not perms[1]:
        raise ScopeDenied()
    if kind in CATALOG_TYPES and not perms[0]:
        raise ScopeDenied()
    actor = request.GET.get("actor", "").strip()
    action = request.GET.get("action", "").strip()
    if len(actor) > 150 or len(action) > 32:
        raise BadFilter("invalid_filter_length")
    dates = []
    for key in ("from", "to"):
        raw = request.GET.get(key)
        if raw is None or raw == "":
            dates.append(None)
            continue
        if len(raw) > 48:
            raise BadFilter("invalid_datetime")
        parsed = parse_datetime(raw)
        if parsed is None or not is_aware(parsed):
            raise BadFilter("datetime_must_include_offset")
        dates.append(parsed)
    if dates[0] and dates[1] and dates[0] > dates[1]:
        raise BadFilter("inverted_date_range")
    try:
        page = int(request.GET.get("page", "1"))
    except (ValueError, TypeError):
        raise BadFilter("invalid_page") from None
    if not 1 <= page <= MAX_EVENTS // PAGE_SIZE:
        raise BadFilter("page_out_of_range")
    return kind, actor, action, dates[0], dates[1], page


def _catalog(event):
    revision = event.revision
    item = event.item
    return {
        "id": str(event.id),
        "occurred_at": event.created_at.isoformat(),
        "actor": event.actor.get_username(),
        "actor_roles_at_event": None,  # Not captured by historical audit source.
        "business_unit": None,         # No BU ACL or attribution exists yet.
        "operation": event.action,
        "object_type": item.type_slug,
        "object_id": item.public_id,
        "object_name": revision.display_name,
        "revision": f"r{revision.number:03d}",
        "revision_id": str(revision.id),
        "outcome": "succeeded",  # Events are inserted in committed transactions.
    }


def _access(event):
    return {
        "id": str(event.id),
        "occurred_at": event.created_at.isoformat(),
        "actor": event.actor.get_username(),
        "actor_roles_at_event": None,
        "business_unit": None,
        "operation": event.action,
        "object_type": "access",
        "object_id": f"user:{event.subject_id}",
        "object_name": event.subject.get_username(),
        "revision": None,
        "revision_id": None,
        "outcome": "succeeded",
    }


def _events(perms, filters):
    kind, actor, action, after, before, page = filters
    sources = []
    if perms[0] and kind != "access":
        q = CatalogAuditEvent.objects.select_related("actor", "item", "revision")
        if kind != "all":
            q = q.filter(item__type_slug=kind)
        if actor:
            q = q.filter(actor__username=actor)
        if action:
            q = q.filter(action=action)
        if after:
            q = q.filter(created_at__gte=after)
        if before:
            q = q.filter(created_at__lte=before)
        sources.extend((_catalog(row), row.created_at, row.id)
                       for row in q.order_by("-created_at", "-id")[:MAX_EVENTS + 1])
    if perms[1] and kind in ("all", "access"):
        q = UserAccessAuditEvent.objects.select_related("actor", "subject")
        if actor:
            q = q.filter(actor__username=actor)
        if action:
            q = q.filter(action=action)
        if after:
            q = q.filter(created_at__gte=after)
        if before:
            q = q.filter(created_at__lte=before)
        sources.extend((_access(row), row.created_at, row.id)
                       for row in q.order_by("-created_at", "-id")[:MAX_EVENTS + 1])
    # Deterministic newest-first order across both persisted sources.
    sources.sort(key=lambda row: (row[1], row[2]), reverse=True)
    return [row[0] for row in sources[:MAX_EVENTS + 1]]


def _authorize(request):
    perms = _permissions(request)
    if perms is None:
        return None, json_no_store({"error": "authentication_required"}, 401)
    if not any(perms):
        return None, json_no_store({"error": "permission_denied"}, 403)
    return perms, None


@require_GET
@never_cache
def collection(request):
    perms, error = _authorize(request)
    if error is not None:
        return error
    try:
        filters = _parse(request, perms)
    except BadFilter as exc:
        return json_no_store({"error": str(exc)}, 400)
    except ScopeDenied:
        return json_no_store({"error": "permission_denied"}, 403)
    if request.GET.get("format") is not None:
        return json_no_store({"error": "use_export_endpoint"}, 400)
    events = _events(perms, filters)
    page = filters[-1]
    start = (page - 1) * PAGE_SIZE
    return json_no_store({
        "results": events[start:start + PAGE_SIZE],
        "page": page, "page_size": PAGE_SIZE,
        "has_more": len(events) > start + PAGE_SIZE,
        "limited": len(events) > MAX_EVENTS,
        "scope": ["catalog" if perms[0] else None, "access" if perms[1] else None],
    })


@require_GET
@never_cache
def export(request):
    perms, error = _authorize(request)
    if error is not None:
        return error
    try:
        filters = _parse(request, perms)
    except BadFilter as exc:
        return json_no_store({"error": str(exc)}, 400)
    except ScopeDenied:
        return json_no_store({"error": "permission_denied"}, 403)
    fmt = request.GET.get("format", "json")
    if fmt not in ("json", "csv"):
        return json_no_store({"error": "unsupported_format"}, 400)
    events = _events(perms, filters)
    if len(events) > MAX_EVENTS:
        return json_no_store({"error": "export_limit_exceeded",
                              "detail": "Narrow the actor/type/time filters (maximum 1000 events)."}, 422)
    if fmt == "json":
        response = HttpResponse(json.dumps({"results": events}, ensure_ascii=False),
                                content_type="application/json; charset=utf-8")
    else:
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in events:
            # Spreadsheet injection protection for user-controlled names/identifiers.
            writer.writerow({key: ("'" + value if isinstance(value, str)
                                   and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n"))
                                   else value) for key, value in row.items()})
        response = HttpResponse(stream.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="ai-compass-activity.{fmt}"'
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
@never_cache
def detail(request, event_id):
    perms, error = _authorize(request)
    if error is not None:
        return error
    if perms[0]:
        row = CatalogAuditEvent.objects.select_related("actor", "item", "revision").filter(id=event_id).first()
        if row is not None:
            return json_no_store({"event": _catalog(row)})
    if perms[1]:
        row = UserAccessAuditEvent.objects.select_related("actor", "subject").filter(id=event_id).first()
        if row is not None:
            fields = {}
            for key, value in row.details.items():
                if key in ACCESS_DETAIL_FIELDS:
                    fields[key] = value
            return json_no_store({"event": _access(row), "changes": fields})
    return json_no_store({"error": "event_not_found"}, 404)
