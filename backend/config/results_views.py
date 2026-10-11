"""PLAT-21: Server-only Results Explorer and immutable interpretation revisions."""
from django.http import Http404,HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET

from .auth_views import capability,json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .catalog_services import RevisionConflict,SchemaWriteBlocked,ExhaustedIds
from .models import CatalogItem,CatalogRevision,ObjectTypeVersion
from . import evaluation_services as svc
from .results_explorer_services import explore,InvalidExplorer


def _private(user):
    return (user.has_perm("auth.business_write") or
            user.has_perm("auth.publication_review"))


def _item(public_id):
    if not isinstance(public_id,str) or not public_id.startswith("evl-"):
        raise Http404("Not an evaluation identity")
    return get_object_or_404(CatalogItem.objects.select_related("current_revision__created_by"),
                             type_slug="evaluation",public_id=public_id)


def _error(exc):
    if isinstance(exc,RevisionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    if isinstance(exc,SchemaWriteBlocked):
        return json_no_store({"error":"schema_write_blocked","detail":str(exc)},409)
    if isinstance(exc,ExhaustedIds):
        return json_no_store({"error":"id_capacity_exhausted"},503)
    return json_no_store({"error":"invalid_evaluation","detail":str(exc)},400)


@require_GET
@capability("business_read")
@never_cache
def explorer(request):
    try:return json_no_store(explore(request.user,request.GET))
    except InvalidExplorer as exc:
        code=422 if "Too many" in str(exc) else 400
        return json_no_store({"error":"invalid_explorer","detail":str(exc)},code)


@csrf_protect
@capability("business_read")
@never_cache
def collection(request):
    if request.method=="GET":
        if request.GET:return json_no_store({"error":"invalid_filter"},400)
        if not _private(request.user):
            # Evaluation snapshots are draft interpretations, not reviewed
            # active publication; only the effective Results Explorer is public.
            return json_no_store({"results":[]})
        records=list(CatalogItem.objects.filter(type_slug="evaluation").select_related(
            "current_revision__created_by").order_by("created_at","public_id")[:501])
        if len(records)>500:return json_no_store({"error":"too_many_evaluations"},422)
        return json_no_store({"results":[svc.serialize(record) for record in records]})
    if request.method!="POST":return HttpResponseNotAllowed(["GET","POST"])
    if not request.user.has_perm("auth.business_write"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=read_payload(request)
        item=svc.create(actor=request.user,data=data)
        response=json_no_store(svc.serialize(item),201)
        response["Location"]="/api/v1/evaluations/"+item.public_id
        return response
    except (InvalidModel,svc.InvalidEvaluation,RevisionConflict,SchemaWriteBlocked,
            ExhaustedIds,TypeError,ValueError) as exc:return _error(exc)


@csrf_protect
@capability("business_read")
@never_cache
def detail(request,public_id):
    item=_item(public_id)
    if request.method=="GET":
        if request.GET:return json_no_store({"error":"invalid_filter"},400)
        if not _private(request.user):raise Http404("Private evaluation")
        return json_no_store(svc.serialize(item))
    if request.method!="PATCH":return HttpResponseNotAllowed(["GET","PATCH"])
    if not request.user.has_perm("auth.business_write"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=read_payload(request)
        expected=data.pop("expected_revision",None)
        if not isinstance(expected,str):
            raise svc.InvalidEvaluation("Expected exact evaluation revision")
        updated=svc.revise(actor=request.user,identifier=public_id,
                           expected_revision=expected,data=data)
        return json_no_store({"record":svc.serialize(updated),"changed":True})
    except (InvalidModel,svc.InvalidEvaluation,RevisionConflict,SchemaWriteBlocked,
            ExhaustedIds,ValueError,TypeError) as exc:return _error(exc)


@require_GET
@capability("business_read")
@never_cache
def history(request,public_id):
    if not _private(request.user):raise Http404("Private evaluation history")
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    item=_item(public_id)
    versions=CatalogRevision.objects.filter(item=item).select_related(
        "created_by").order_by("number")
    return json_no_store({"id":item.public_id,
                          "revisions":[svc.serialize(item,rev) for rev in versions]})


@require_GET
@capability("business_read")
@never_cache
def version(request,public_id,number):
    if not _private(request.user):raise Http404("Private evaluation history")
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    item=_item(public_id)
    rev=get_object_or_404(CatalogRevision.objects.select_related("created_by"),
                          item=item,number=number)
    return json_no_store(svc.serialize(item,rev))
