"""PLAT-18: Server-only Research Source + Technology Watch REST endpoints.

Readers can see only published revisions with publicly visible, originally-pinned
sources; contributors/reviewers may inspect internal content. No Demo fallback.
"""
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from .auth_views import capability,json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .catalog_services import RevisionConflict,SchemaWriteBlocked,ExhaustedIds
from .models import CatalogItem,CatalogRevision
from . import watch_services as svc

LIMITS={"research_source":{"name","properties"},
        "watch_entry":{"name","properties","sources"}}


def _workgroup(user):
    return user.has_perm("auth.business_write") or user.has_perm("auth.publication_review")


def _item(kind,id):
    if kind not in svc.TYPES or not id.startswith(svc.TYPES[kind]+"-"):
        raise Http404("Unknown Watch object")
    return get_object_or_404(CatalogItem.objects.select_related(
        "current_revision__created_by","current_revision__schema_version"),
        public_id=id,type_slug=kind)


def _visible(item,rev,user):
    row=svc.serialize(item,rev=rev,reader=not _workgroup(user))
    if row is None:raise Http404("Watch object is not publicly visible")
    return row


def _payload(request,keys):
    data=read_payload(request)
    if set(data)-keys:raise InvalidModel("Unsupported input properties")
    if "properties" in data and not isinstance(data["properties"],dict):
        raise InvalidModel("properties must be an object")
    return data


def _error(exc):
    if isinstance(exc,RevisionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    if isinstance(exc,SchemaWriteBlocked):
        return json_no_store({"error":"unsupported_schema","detail":str(exc)},409)
    if isinstance(exc,ExhaustedIds):
        return json_no_store({"error":"id_exhausted"},503)
    return json_no_store({"error":"invalid_watch_record","detail":str(exc)},400)


@capability("business_read")
@csrf_protect
@never_cache
def sources(request):
    return _collection(request,svc.SOURCE)


@capability("business_read")
@csrf_protect
@never_cache
def entries(request):
    return _collection(request,svc.WATCH)


def _collection(request,kind):
    if request.method=="GET":
        if set(request.GET)-{"q"}:
            return json_no_store({"error":"invalid_filter"},400)
        q=request.GET.get("q","")
        if len(q)>160:return json_no_store({"error":"invalid_filter"},400)
        results=svc.accessible(kind,request.user,q.strip())
        if len(results)>500:return json_no_store({"error":"too_many_records"},422)
        return json_no_store({"results":results})
    if request.method!="POST":return HttpResponseNotAllowed(["GET","POST"])
    if not request.user.has_perm("auth.business_write"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=_payload(request,LIMITS[kind])
        obj=svc.create(kind,actor=request.user,name=data.get("name"),
                       properties=data.get("properties",{}),sources=data.get("sources"))
    except (InvalidModel,ValueError,SchemaWriteBlocked,ExhaustedIds) as exc:
        return _error(exc)
    response=json_no_store(svc.serialize(obj),201)
    response["Location"]="/api/v1/"+("sources" if kind==svc.SOURCE else "watch-entries")+"/"+obj.public_id
    return response


@capability("business_read")
@csrf_protect
@never_cache
def source(request,public_id):
    return _detail(request,svc.SOURCE,public_id)


@capability("business_read")
@csrf_protect
@never_cache
def entry(request,public_id):
    return _detail(request,svc.WATCH,public_id)


def _detail(request,kind,public_id):
    obj=_item(kind,public_id)
    if request.method=="GET":return json_no_store(_visible(obj,None,request.user))
    if request.method!="PATCH":return HttpResponseNotAllowed(["GET","PATCH"])
    if not request.user.has_perm("auth.business_write"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=_payload(request,LIMITS[kind]|{"expected_revision"})
        if not isinstance(data.get("expected_revision"),str):
            raise InvalidModel("expected_revision is required")
        revised,changed=svc.revise(kind,actor=request.user,item=obj,
                        expected_revision=data["expected_revision"],
                        name=data.get("name"),properties=data.get("properties"),
                        sources=data.get("sources"))
    except (InvalidModel,RevisionConflict,SchemaWriteBlocked,ValueError) as exc:
        return _error(exc)
    return json_no_store({"record":svc.serialize(revised),"changed":changed})


@capability("business_read")
@never_cache
def source_history(request,public_id):
    return _history(request,svc.SOURCE,public_id)


@capability("business_read")
@never_cache
def entry_history(request,public_id):
    return _history(request,svc.WATCH,public_id)


def _history(request,kind,public_id):
    if request.method!="GET":return HttpResponseNotAllowed(["GET"])
    item=_item(kind,public_id)
    # A past internal revision stays hidden even if a later revision is public.
    rows=[]
    for rev in CatalogRevision.objects.filter(item=item).select_related(
            "created_by","schema_version").order_by("number"):
        data=svc.serialize(item,rev,reader=not _workgroup(request.user))
        if data is not None:rows.append(data)
    if not rows and not _workgroup(request.user):
        raise Http404("No publicly visible source history")
    return json_no_store({"id":item.public_id,"revisions":rows})


@capability("business_read")
@never_cache
def source_revision(request,public_id,number):
    return _version(request,svc.SOURCE,public_id,number)


@capability("business_read")
@never_cache
def entry_revision(request,public_id,number):
    return _version(request,svc.WATCH,public_id,number)


def _version(request,kind,public_id,number):
    if request.method!="GET":return HttpResponseNotAllowed(["GET"])
    obj=_item(kind,public_id)
    revision=get_object_or_404(CatalogRevision.objects.select_related(
        "created_by"),item=obj,number=number)
    return json_no_store(_visible(obj,revision,request.user))


@capability("business_read")
@csrf_protect
@never_cache
def source_action(request,public_id,action):
    return _review(request,svc.SOURCE,public_id,action)


@capability("business_read")
@csrf_protect
@never_cache
def entry_action(request,public_id,action):
    return _review(request,svc.WATCH,public_id,action)


def _review(request,kind,public_id,action):
    if request.method!="POST":return HttpResponseNotAllowed(["POST"])
    if not request.user.has_perm("auth.publication_review"):
        return json_no_store({"error":"permission_denied"},403)
    item=_item(kind,public_id)
    try:
        data=_payload(request,{"expected_revision"})
        if not isinstance(data.get("expected_revision"),str):
            raise InvalidModel("expected_revision is required")
        updated,changed=svc.revise(kind,actor=request.user,item=item,
                    expected_revision=data["expected_revision"],review_action=action)
    except (InvalidModel,RevisionConflict,SchemaWriteBlocked,ValueError) as exc:
        return _error(exc)
    return json_no_store({"record":svc.serialize(updated),"changed":changed})
