"""FUT-15: confidential deployment planning and self-only Engineer read projection."""
import json

from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .auth_views import capability, json_no_store
from .models import DeploymentTarget, WorkloadProfile
from . import deployment_services as svc

LIMIT = 32768


def _body(request):
    if len(request.body) > LIMIT:
        raise svc.InvalidDeployment("Deployment request too large")
    try:
        data = json.loads(request.body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise svc.InvalidDeployment("Invalid JSON body") from exc
    if not isinstance(data, dict):
        raise svc.InvalidDeployment("JSON object required")
    return data


def _error(exc):
    return json_no_store({"error": "revision_conflict" if isinstance(exc, svc.StaleDeployment)
                          else "invalid_deployment", "detail": str(exc)},
                         409 if isinstance(exc, svc.StaleDeployment) else 400)


def _item(public_id):
    item = DeploymentTarget.objects.filter(public_id=public_id).first()
    if item is None:
        raise Http404("Unknown deployment target")
    return item


@require_http_methods(["GET", "POST"])
@never_cache
@csrf_protect
@capability("planning_view")
def collection(request):
    if request.method == "GET":
        if set(request.GET) - {"profile_id"}:
            return json_no_store({"error": "invalid_filter"}, 400)
        rows = DeploymentTarget.objects.select_related(
            "population", "task__item", "candidate").order_by("created_at", "public_id")
        if request.GET.get("profile_id"):
            rows = rows.filter(population__public_id=request.GET["profile_id"])
        entries = list(rows[:501])
        if len(entries) > 500:
            return json_no_store({"error": "too_many_targets"}, 422)
        return json_no_store({"results": [svc.status(x, private=False) for x in entries]})
    if not request.user.has_perm("auth.planning_manage"):
        return json_no_store({"error": "permission_denied"}, 403)
    try:
        result = svc.create(request.user, _body(request))
        return json_no_store(svc.status(result), 201)
    except svc.InvalidDeployment as exc:
        return _error(exc)


@require_http_methods(["GET", "PATCH"])
@never_cache
@csrf_protect
@capability("planning_view")
def detail(request, public_id):
    target = _item(public_id)
    if request.method == "GET":
        if request.GET:
            return json_no_store({"error": "invalid_filter"}, 400)
        return json_no_store(svc.status(target))
    if not request.user.has_perm("auth.planning_manage"):
        return json_no_store({"error": "permission_denied"}, 403)
    try:
        data = _body(request)
        if set(data) != {"expected_revision", "selection"}:
            raise svc.InvalidDeployment("Revision and full selection required")
        svc.revise(request.user, target, data["expected_revision"], data["selection"])
        return json_no_store(svc.status(target))
    except svc.InvalidDeployment as exc:
        return _error(exc)


@require_GET
@never_cache
@capability("planning_view")
def history(request, public_id):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    target = _item(public_id)
    return json_no_store({"id": target.public_id, "revisions": [{
        "revision": "r%03d" % r.number, "revision_id": str(r.pk),
        "selection": r.selection, "actor": r.created_by.get_username(),
        "created_at": r.created_at.isoformat()
    } for r in target.revisions.select_related("created_by").order_by("number")]})


@require_POST
@never_cache
@csrf_protect
@capability("planning_view")
def record(request, public_id):
    if not request.user.has_perm("auth.planning_manage"):
        return json_no_store({"error": "permission_denied"}, 403)
    try:
        entry = svc.record(request.user, _item(public_id), _body(request))
        return json_no_store({"event_id": str(entry.pk),
                              "target": svc.status(entry.target)}, 201)
    except svc.InvalidDeployment as exc:
        return _error(exc)


@require_GET
@never_cache
@capability("planning_view")
def export(request):
    """Bounded authorized machine-readable request summary, without user salaries."""
    if set(request.GET) != {"profile_id"}:
        return json_no_store({"error": "profile_id_required"}, 400)
    rows = list(DeploymentTarget.objects.filter(
        population__public_id=request.GET["profile_id"]).order_by("public_id")[:501])
    if len(rows) > 500:
        return json_no_store({"error": "too_many_targets"}, 422)
    return json_no_store({"purpose": "manual_external_tool_access_planning",
                          "disclaimer": "Not proof of external IAM grant, payment or actual savings",
                          "targets": [svc.status(x, private=False) for x in rows]})


@require_GET
@never_cache
@capability("business_read")
def mine(request):
    """Self-only; no colleague status, labor rate, or business-plan data."""
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    from .models import WorkloadRevision
    linked = WorkloadRevision.objects.filter(linked_user=request.user,
        profile__kind="person").values_list("profile_id", flat=True).distinct()
    people = WorkloadProfile.objects.filter(pk__in=linked)
    current = {p.public_id for p in people if svc.latest(p).linked_user_id == request.user.pk}
    if not current:
        return json_no_store({"results": []})
    rows = DeploymentTarget.objects.all().order_by("created_at", "public_id")[:501]
    if len(rows) > 500:
        return json_no_store({"error": "too_many_targets"}, 422)
    results = []
    for target in rows:
        snapshot = svc.status(target)
        own = [s for s in snapshot["beneficiaries"] if s["person_profile_id"] in current]
        for s in own:
            results.append({"target_id": target.public_id,
                "task_id": snapshot["task_id"], "candidate_id": snapshot["candidate_id"],
                "kind": snapshot["kind"], "ready": s["ready"],
                "first_use_confirmed": s["first_use_confirmed"],
                "blockers": s["blockers"], "entitlements": s["entitlements"]})
    return json_no_store({"results": results})
