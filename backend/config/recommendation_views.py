"""PLAT-22: scoped Recommendations endpoints, explicit one-reviewer publication."""
from django.http import Http404,HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET,require_POST

from .auth_views import capability,json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .catalog_services import RevisionConflict,SchemaWriteBlocked,ExhaustedIds
from .models import CatalogItem,CatalogRevision
from . import recommendation_services as svc


def _privileged(user):
    return user.has_perm("auth.business_write") or user.has_perm("auth.publication_review")


def _record(identifier):
    if not isinstance(identifier,str) or not identifier.startswith("rec-"):
        raise Http404("Unknown recommendation")
    return get_object_or_404(CatalogItem.objects.select_related(
        "current_revision__created_by"),public_id=identifier,type_slug="recommendation")


def _visible(item,revision,user):
    row=svc.serialize(item,rev=revision,reader=not _privileged(user))
    if row is None:raise Http404("Unpublished recommendation")
    return row


def _error(exc):
    if isinstance(exc,RevisionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    if isinstance(exc,SchemaWriteBlocked):
        return json_no_store({"error":"schema_write_blocked","detail":str(exc)},409)
    if isinstance(exc,ExhaustedIds):
        return json_no_store({"error":"id_capacity_exhausted"},503)
    return json_no_store({"error":"invalid_recommendation","detail":str(exc)},400)


@csrf_protect
@capability("business_read")
@never_cache
def collection(request):
    if request.method=="GET":
        if set(request.GET)-{"task_id","solution_id"}:
            return json_no_store({"error":"invalid_filter"},400)
        task=request.GET.get("task_id")
        solution=request.GET.get("solution_id")
        if (task and (not task.startswith("tsk-") or len(task)>120)) or (
                solution and (not solution.startswith("sol-") or len(solution)>120)):
            return json_no_store({"error":"invalid_filter"},400)
        try:
            return json_no_store({"results":svc.list_records(request.user,task,solution)})
        except svc.InvalidRecommendation as exc:return _error(exc)
    if request.method!="POST":return HttpResponseNotAllowed(["GET","POST"])
    if not request.user.has_perm("auth.business_write"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        item=svc.create(actor=request.user,data=read_payload(request))
        response=json_no_store(svc.serialize(item),201)
        response["Location"]="/api/v1/recommendations/"+item.public_id
        return response
    except (InvalidModel,svc.InvalidRecommendation,RevisionConflict,SchemaWriteBlocked,
            ExhaustedIds,ValueError,TypeError) as exc:return _error(exc)


@csrf_protect
@capability("business_read")
@never_cache
def detail(request,public_id):
    item=_record(public_id)
    if request.method=="GET":
        if request.GET:return json_no_store({"error":"invalid_filter"},400)
        return json_no_store(_visible(item,None,request.user))
    if request.method!="PATCH":return HttpResponseNotAllowed(["GET","PATCH"])
    if not request.user.has_perm("auth.business_write"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=read_payload(request)
        updated=svc.change(actor=request.user,identifier=public_id,data=data)
        return json_no_store({"record":svc.serialize(updated),"changed":True})
    except (InvalidModel,svc.InvalidRecommendation,RevisionConflict,SchemaWriteBlocked,
            ExhaustedIds,TypeError,ValueError) as exc:return _error(exc)


@require_GET
@capability("business_read")
@never_cache
def history(request,public_id):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    item=_record(public_id)
    reader=not _privileged(request.user)
    revisions=CatalogRevision.objects.filter(item=item).select_related(
        "created_by").order_by("number")
    records=[svc.serialize(item,rev=revision,reader=reader) for revision in revisions]
    records=[row for row in records if row is not None]
    if reader and not records:raise Http404("No visible publication history")
    return json_no_store({"id":item.public_id,"revisions":records})


@require_GET
@capability("business_read")
@never_cache
def version(request,public_id,number):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    item=_record(public_id)
    revision=get_object_or_404(CatalogRevision.objects.select_related("created_by"),
                              item=item,number=number)
    return json_no_store(_visible(item,revision,request.user))


@require_POST
@csrf_protect
@capability("business_read")
@never_cache
def action(request,public_id,action):
    _record(public_id)
    capability_name="business_write" if action=="submit" else "publication_review"
    if not request.user.has_perm("auth."+capability_name):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=read_payload(request)
        result=svc.change(actor=request.user,identifier=public_id,data=data,action=action)
        return json_no_store({"record":svc.serialize(result),"changed":True})
    except (InvalidModel,svc.InvalidRecommendation,RevisionConflict,SchemaWriteBlocked,
            ExhaustedIds,TypeError,ValueError) as exc:return _error(exc)
