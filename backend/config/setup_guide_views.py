"""PLAT-11: authenticated Setup Guide CRUD + immutable read-back.

Designed for Guides & Charter and the future campaign inline selector;
does not create fake campaigns or synchronize Demo.
"""
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET,require_POST,require_http_methods

from .auth_views import capability,json_no_store
from .catalog_views import read_payload,serialize
from .catalog_schemas import InvalidModel
from .catalog_services import RevisionConflict,ExhaustedIds,SchemaWriteBlocked
from .models import CatalogItem,CatalogRevision
from .setup_guide_services import create,revise,TYPE

FIELDS=frozenset({"name","properties"})
EDIT_FIELDS=FIELDS|{"expected_revision"}


def _payload(request,allowed):
    data=read_payload(request)
    if set(data)-allowed:
        raise InvalidModel("Unsupported fields: "+", ".join(sorted(set(data)-allowed)))
    if "properties" in data and not isinstance(data["properties"],dict):
        raise InvalidModel("properties must be a JSON object")
    return data


def _error(exc):
    if isinstance(exc,RevisionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    if isinstance(exc,SchemaWriteBlocked):
        return json_no_store({"error":"schema_write_blocked","detail":str(exc),
                              "compatibility":exc.compatibility},409)
    if isinstance(exc,ExhaustedIds):
        return json_no_store({"error":"public_id_exhausted"},503)
    return json_no_store({"error":"invalid_guide","detail":str(exc)},400)


def _guide(item,revision=None):
    result=serialize(item,revision=revision)
    current=revision if revision is not None else item.current_revision
    result["revision_id"]=str(current.pk) if current else None
    return result


def _item(public_id):
    if not public_id.startswith("gui-"):
        from django.http import Http404
        raise Http404("Not a guide identifier")
    return get_object_or_404(
        CatalogItem.objects.select_related("current_revision__schema_version",
                                           "current_revision__created_by"),
        public_id=public_id,type_slug=TYPE)


@require_GET
@capability("business_read")
@never_cache
def list_guides(request):
    if set(request.GET)-{"q"}:
        return json_no_store({"error":"invalid_filter"},400)
    q=request.GET.get("q","")
    if len(q)>160:
        return json_no_store({"error":"invalid_filter"},400)
    items=CatalogItem.objects.filter(type_slug=TYPE).select_related(
        "current_revision__schema_version","current_revision__created_by"
    ).order_by("public_id")
    if q.strip():
        from django.db.models import Q
        items=items.filter(Q(public_id__icontains=q.strip())|
                           Q(current_revision__display_name__icontains=q.strip()))
    return json_no_store({"results":[_guide(item) for item in items[:501]]})


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def add_guide(request):
    try:
        payload=_payload(request,FIELDS)
        item=create(actor=request.user,name=payload.get("name"),
                    properties=payload.get("properties",{}))
    except (InvalidModel,RevisionConflict,SchemaWriteBlocked,ExhaustedIds) as exc:
        return _error(exc)
    response=json_no_store(_guide(item),201)
    response["Location"]="/api/v1/guides/"+item.public_id
    return response


@require_GET
@capability("business_read")
@never_cache
def get_guide(request,public_id):
    return json_no_store(_guide(_item(public_id)))


@require_http_methods(["PATCH"])
@csrf_protect
@capability("business_write")
@never_cache
def patch_guide(request,public_id):
    item=_item(public_id)
    try:
        payload=_payload(request,EDIT_FIELDS)
        if not isinstance(payload.get("expected_revision"),str):
            raise InvalidModel("expected_revision is required")
        updated,changed=revise(actor=request.user,public_id=item.public_id,
                               expected_revision=payload["expected_revision"],
                               name=payload.get("name"),
                               properties=payload.get("properties"))
    except (InvalidModel,RevisionConflict,SchemaWriteBlocked,ExhaustedIds) as exc:
        return _error(exc)
    return json_no_store({"guide":_guide(updated),"changed":changed})


@require_GET
@capability("business_read")
@never_cache
def history(request,public_id):
    item=_item(public_id)
    revisions=CatalogRevision.objects.filter(item=item).select_related(
        "schema_version","created_by").order_by("number")
    return json_no_store({"id":item.public_id,
                          "revisions":[_guide(item,revision=r) for r in revisions]})


@require_GET
@capability("business_read")
@never_cache
def version(request,public_id,number):
    item=_item(public_id)
    rev=get_object_or_404(CatalogRevision.objects.select_related(
        "schema_version","created_by"),item=item,number=number)
    return json_no_store(_guide(item,revision=rev))


def collection(request):
    if request.method=="GET": return list_guides(request)
    if request.method=="POST": return add_guide(request)
    return HttpResponseNotAllowed(["GET","POST"])


def detail(request,public_id):
    if request.method=="GET": return get_guide(request,public_id)
    if request.method=="PATCH": return patch_guide(request,public_id)
    return HttpResponseNotAllowed(["GET","PATCH"])
