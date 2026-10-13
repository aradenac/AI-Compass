"""FUT-20: platform-operator capacity policy and health/headroom dashboard.

Read (health/headroom + policy) requires ``platform_view``; policy edit requires
``platform_manage``. Other roles cannot read or infer sensitive settings
(e.g. a data-maintainer's ``maintenance_view`` grants nothing here).
"""
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .auth_views import capability, json_no_store, read_json
from .capacity_services import (
    BOUNDS, CapacityError, configure_policy, metrics, policy, serialize_policy,
)
from .models import CapacityPolicyEvent


@require_GET
@capability("platform_view")
@never_cache
def capacity_health(request):
    return json_no_store(metrics())


@require_GET
@capability("platform_view")
@never_cache
def capacity_policy(request):
    return json_no_store({"policy": serialize_policy(policy()),
                          "bounds": {k: list(v) for k, v in BOUNDS.items()}})


@require_http_methods(["PATCH", "PUT"])
@csrf_protect
@capability("platform_manage")
@never_cache
def capacity_policy_edit(request):
    payload = read_json(request)
    allowed = set(BOUNDS) | {"threshold_factors"}
    if payload is None or set(payload) - allowed:
        return json_no_store({"error": "invalid_payload"}, 400)
    try:
        row = configure_policy(actor=request.user, **payload)
    except CapacityError as exc:
        return json_no_store({"error": "invalid_policy", "detail": str(exc)}, 400)
    return json_no_store({"policy": serialize_policy(row)}, 201)


@require_GET
@capability("platform_view")
@never_cache
def capacity_policy_history(request):
    rows = CapacityPolicyEvent.objects.order_by("-created_at")[:50]
    return json_no_store({"results": [{
        "action": e.action, "previous": e.previous, "applied": e.applied,
        "actor": e.actor.get_username() if e.actor else None,
        "at": e.created_at.isoformat()} for e in rows]})
