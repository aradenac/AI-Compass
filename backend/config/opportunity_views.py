"""FUT-13: planning-only economic scenarios, previews and immutable revisions."""
import json
from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_GET, require_POST

from .auth_views import capability, json_no_store
from .models import OpportunityScenario, WorkloadProfile
from . import opportunity_services as svc

MAX_BODY=24000


def body(request):
    if len(request.body)>MAX_BODY:
        raise svc.InvalidOpportunity("Scenario request exceeds 24 KiB")
    try:
        data=json.loads(request.body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise svc.InvalidOpportunity("Invalid JSON") from exc
    if not isinstance(data,dict):
        raise svc.InvalidOpportunity("Expected JSON object")
    return data


def failure(exc):
    return json_no_store({"error":"stale_scenario" if isinstance(exc,svc.StaleOpportunity)
                          else "invalid_opportunity","detail":str(exc)},
                         409 if isinstance(exc,svc.StaleOpportunity) else 400)


def item(public_id):
    return OpportunityScenario.objects.filter(public_id=public_id).first()


@require_http_methods(["GET","POST"])
@never_cache
@csrf_protect
@capability("planning_view")
def collection(request):
    if request.method=="GET":
        if request.GET:return json_no_store({"error":"invalid_filter"},400)
        rows=list(OpportunityScenario.objects.select_related("profile").order_by(
            "created_at","public_id")[:501])
        if len(rows)>500:return json_no_store({"error":"too_many_scenarios"},422)
        return json_no_store({"results":[{
            "id":r.public_id,"profile_id":r.profile.public_id,
            "latest_revision":"r%03d"%r.snapshots.order_by("-number").first().number}
            for r in rows]})
    if not request.user.has_perm("auth.planning_manage"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        entry=svc.create(request.user,body(request))
        return json_no_store(svc.serialize(entry,current=True),201)
    except svc.InvalidOpportunity as exc:return failure(exc)


@require_POST
@never_cache
@csrf_protect
@capability("planning_view")
def preview(request):
    if not request.user.has_perm("auth.planning_manage"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=body(request)
        if set(data)!={"profile_id","scenario"}:
            raise svc.InvalidOpportunity("Select one profile and scenario")
        profile=svc._profile(data["profile_id"])
        return json_no_store(svc.project(profile,data["scenario"]))
    except svc.InvalidOpportunity as exc:return failure(exc)


@require_http_methods(["GET","PATCH"])
@never_cache
@csrf_protect
@capability("planning_view")
def detail(request,public_id):
    entry=item(public_id)
    if entry is None:raise Http404("No such planning scenario")
    if request.method=="GET":
        if request.GET:return json_no_store({"error":"invalid_filter"},400)
        try:return json_no_store(svc.serialize(entry,current=True))
        except svc.InvalidOpportunity as exc:return failure(exc)
    if not request.user.has_perm("auth.planning_manage"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        payload=body(request)
        if not isinstance(payload,dict) or set(payload)!={"expected_revision","scenario"}:
            raise svc.InvalidOpportunity("Expected revision and full new scenario")
        updated=svc.revise(request.user,public_id,payload["expected_revision"],
                           {"scenario":payload["scenario"]})
        return json_no_store(svc.serialize(updated,current=True))
    except svc.InvalidOpportunity as exc:return failure(exc)


@require_GET
@never_cache
@capability("planning_view")
def history(request,public_id):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    entry=item(public_id)
    if entry is None:raise Http404("No such planning scenario")
    return json_no_store({"id":entry.public_id,"revisions":[{
        "revision":"r%03d"%row.number,"revision_id":str(row.pk),
        "created_at":row.created_at.isoformat(),"created_by":row.created_by.get_username(),
        "algorithm":row.algorithm,"totals":row.projection["totals"],
        "source_frozen":True}
        for row in entry.snapshots.select_related("created_by").order_by("number")]})


@require_GET
@never_cache
@capability("planning_view")
def revision(request,public_id,number):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    entry=item(public_id)
    if entry is None:raise Http404("No such planning scenario")
    old=entry.snapshots.filter(number=number).select_related("created_by").first()
    if old is None:raise Http404("No such immutable scenario snapshot")
    return json_no_store(svc.serialize(entry,revision=old))
