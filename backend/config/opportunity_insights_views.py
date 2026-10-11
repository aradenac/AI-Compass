"""FUT-14: strictly confidential read-only Management/Planner projections."""
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .auth_views import capability, json_no_store
from . import opportunity_insights_services as svc
from .opportunity_services import InvalidOpportunity

def _q(request, allowed):
    if set(request.GET) - set(allowed):
        raise InvalidOpportunity("Unexpected query filter")
    data = request.GET
    if not data.get("profile_id"):
        raise InvalidOpportunity("An authorized explicit population is required")
    revision = data.get("revision")
    if revision is not None:
        if not revision.startswith("r") or len(revision) != 4 or not revision[1:].isdigit():
            raise InvalidOpportunity("Historical revision must be r001 style")
        revision = int(revision[1:])
        if revision < 1:
            raise InvalidOpportunity("Invalid revision number")
    return dict(profile_id=data["profile_id"], scenario_id=data.get("scenario_id") or None,
                revision=revision)

def _error(exc):
    return json_no_store({"error":"invalid_insights_request","detail":str(exc)},400)

@require_GET
@never_cache
@capability("planning_view")
def heatmap(request):
    try:
        params=_q(request,("profile_id","scenario_id","revision","row_page",
                           "column_page","row_size","column_size","period"))
        if request.GET.get("period", "annual") != "annual":
            raise InvalidOpportunity("Only annual valuations are supported; no fictional seasonality")
        for field in ("row_page","column_page","row_size","column_size"):
            if field in request.GET:
                params[field] = request.GET[field]
        return json_no_store(svc.heatmap(**params))
    except InvalidOpportunity as exc:return _error(exc)

@require_GET
@never_cache
@capability("planning_view")
def management(request):
    try:
        params=_q(request,("profile_id","scenario_id","revision","period"))
        if request.GET.get("period","annual")!="annual":
            raise InvalidOpportunity("Only annual valuations are supported")
        return json_no_store(svc.insights(**params))
    except InvalidOpportunity as exc:return _error(exc)

@require_GET
@never_cache
@capability("planning_view")
def explain(request):
    try:
        params=_q(request,("profile_id","scenario_id","revision",
                           "task_id","kind","candidate_id"))
        if not all(request.GET.get(k) for k in ("task_id","kind","candidate_id")):
            raise InvalidOpportunity("Exact Task and saved candidate are required")
        if request.GET["kind"] not in ("benchmark","forecast"):
            raise InvalidOpportunity("Unknown candidate type")
        return json_no_store(svc.explain(**params,
            task_id=request.GET["task_id"], kind=request.GET["kind"],
            candidate_id=request.GET["candidate_id"]))
    except InvalidOpportunity as exc:return _error(exc)

@require_GET
@never_cache
@capability("planning_view")
def suggestions(request):
    try:
        params=_q(request,("profile_id","limit"))
        if params["scenario_id"] or params["revision"] is not None:
            raise InvalidOpportunity("Suggestions always use current published evidence")
        return json_no_store(svc.suggestions(
            profile_id=params["profile_id"],max_items=request.GET.get("limit","40")))
    except InvalidOpportunity as exc:return _error(exc)
