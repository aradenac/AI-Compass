"""FUT-16: authorized, no-store, CSRF-protected budget planning endpoints."""
import json

from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .auth_views import capability, json_no_store
from .models import BudgetPlan, DeploymentTarget, CatalogItem, WorkloadProfile
from .opportunity_services import candidates
from .deployment_services import status as deployment_status
from .pricing_services import readiness
from . import budget_services as svc

MAX_BODY = 32768


def body(request):
    if len(request.body) > MAX_BODY:
        raise svc.InvalidBudget("Budget request exceeds 32 KiB")
    try:
        data = json.loads(request.body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise svc.InvalidBudget("Invalid JSON body") from exc
    if not isinstance(data, dict):
        raise svc.InvalidBudget("Expected JSON object")
    return data


def error(exc):
    return json_no_store({"error": "revision_conflict" if isinstance(exc, svc.StaleBudget)
                          else "invalid_budget", "detail": str(exc)},
                         409 if isinstance(exc, svc.StaleBudget) else 400)


def editable(request):
    return request.user.has_perm("auth.planning_manage")


def get(public_id):
    row = BudgetPlan.objects.select_related("profile").filter(public_id=public_id).first()
    if row is None:
        raise Http404("Unknown resource budget")
    return row


@require_GET
@never_cache
@capability("planning_view")
def options(request):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    try:
        profiles = list(WorkloadProfile.objects.order_by("public_id")[:501])
        targets = list(DeploymentTarget.objects.select_related(
            "population", "task__item", "candidate").order_by("public_id")[:501])
        offers = list(CatalogItem.objects.filter(type_slug="pricing_offer",
            current_revision__isnull=False).select_related(
                "current_revision").order_by("public_id")[:501])
        if max(len(profiles), len(targets), len(offers)) > 500:
            return json_no_store({"error": "bounded_catalog_exceeded"}, 422)
        return json_no_store({
            "profiles": [{"id": p.public_id, "kind": p.kind,
                          "name": p.revisions.order_by("-number").first().name}
                         for p in profiles],
            "candidates": candidates(),
            "targets": [deployment_status(t, private=False) for t in targets
                        if t.kind == "benchmark"],
            "offers": [{"id": x.public_id,
                        "revision_id": str(x.current_revision_id),
                        "name": x.current_revision.display_name,
                        "component_id": x.current_revision.properties.get("component_id"),
                        "currency": x.current_revision.properties.get("currency"),
                        "billing_owner": x.current_revision.properties.get("billing_owner"),
                        "complete": readiness(x.current_revision)["complete"]}
                       for x in offers],
        })
    except (ValueError, svc.InvalidBudget) as exc:
        return error(exc)


@require_http_methods(["GET", "POST"])
@never_cache
@csrf_protect
@capability("planning_view")
def collection(request):
    if request.method == "GET":
        if request.GET:
            return json_no_store({"error": "invalid_filter"}, 400)
        rows = list(BudgetPlan.objects.select_related("profile").order_by(
            "created_at", "public_id")[:501])
        if len(rows) > 500:
            return json_no_store({"error": "too_many_budgets"}, 422)
        return json_no_store({"results": [{
            "id": x.public_id, "profile_id": x.profile.public_id,
            "revision": "r%03d" % x.revisions.order_by("-number").first().number}
            for x in rows]})
    if not editable(request):
        return json_no_store({"error": "permission_denied"}, 403)
    try:
        budget = svc.create(request.user, body(request))
        return json_no_store(svc.serialize(budget), 201)
    except svc.InvalidBudget as exc:
        return error(exc)


@require_POST
@never_cache
@csrf_protect
@capability("planning_view")
def preview(request):
    if not editable(request):
        return json_no_store({"error": "permission_denied"}, 403)
    try:
        return json_no_store(svc.preview(body(request)))
    except svc.InvalidBudget as exc:
        return error(exc)


@require_http_methods(["GET", "PATCH"])
@never_cache
@csrf_protect
@capability("planning_view")
def detail(request, public_id):
    budget = get(public_id)
    if request.method == "GET":
        if request.GET:
            return json_no_store({"error": "invalid_filter"}, 400)
        return json_no_store(svc.serialize(budget))
    if not editable(request):
        return json_no_store({"error": "permission_denied"}, 403)
    try:
        data = body(request)
        if set(data) != {"expected_revision", "plan"}:
            raise svc.InvalidBudget("Expected revision and complete plan")
        svc.revise(request.user, budget, data["expected_revision"], data["plan"])
        return json_no_store(svc.serialize(budget))
    except svc.InvalidBudget as exc:
        return error(exc)


@require_GET
@never_cache
@capability("planning_view")
def history(request, public_id):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    budget = get(public_id)
    return json_no_store({"id": budget.public_id,
        "revisions": [{"revision": "r%03d" % r.number, "revision_id": str(r.pk),
                       "created_at": r.created_at.isoformat(),
                       "created_by": r.created_by.get_username(),
                       "ready_for_request": r.projection["ready_for_request"],
                       "source_frozen": True}
                      for r in budget.revisions.select_related("created_by").order_by("number")]})


@require_GET
@never_cache
@capability("planning_view")
def revision(request, public_id, number):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    budget = get(public_id)
    old = budget.revisions.filter(number=number).select_related("created_by").first()
    if old is None:
        raise Http404("No such immutable budget revision")
    return json_no_store(svc.serialize(budget, revision=old, current=False))


@require_GET
@never_cache
@capability("planning_view")
def export(request, public_id):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    budget = get(public_id)
    # Export deliberately retains source revisions and aggregate native-money
    # requirements but never includes employee identities or labor rates.
    result = svc.serialize(budget, current=False)
    return json_no_store({"type": "resource_request_summary", "schema_version": 1,
        "budget": result, "authorization": "planning_view",
        "not_purchase_order_or_credential_request": True})
