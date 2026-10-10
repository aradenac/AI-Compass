"""FUT-05. Authenticated source-backed, immutable commercial offer API.

Enterprise accessibility != individual entitlement. All edits use CSRF,
explicit expected revision, append-only catalog audit and strict capability.
"""
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .auth_views import capability, json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .catalog_services import (revise_component, RevisionConflict,
                               SchemaWriteBlocked, ExhaustedIds)
from .models import CatalogItem, CatalogRevision
from .pricing_services import (ACCESS, KINDS, InvalidPricing, accessibility,
    offer_create, offer_revise, offer_record, readiness, validate_offer)


def _response_error(exc):
    if isinstance(exc, RevisionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    if isinstance(exc, SchemaWriteBlocked):
        return json_no_store({"error":"schema_write_blocked","detail":str(exc)},409)
    if isinstance(exc, ExhaustedIds):
        return json_no_store({"error":"capacity_exhausted"},503)
    return json_no_store({"error":"invalid_pricing","detail":str(exc)},400)


def _item(public_id):
    if not isinstance(public_id,str) or not public_id.startswith("off-"):
        raise Http404("Not an offer")
    return get_object_or_404(CatalogItem.objects.select_related(
        "current_revision__created_by"), public_id=public_id,
        type_slug="pricing_offer")


@require_http_methods(["GET","POST"])
@never_cache
@csrf_protect
def offers(request):
    if request.method == "GET":
        return offer_list(request)
    return offer_add(request)


@capability("business_read")
def offer_list(request):
    if set(request.GET)-{"component_id"}:
        return json_no_store({"error":"invalid_filter"},400)
    items=CatalogItem.objects.filter(type_slug="pricing_offer").select_related(
        "current_revision__created_by").order_by("created_at","public_id")
    component_id=request.GET.get("component_id")
    if component_id is not None:
        if len(component_id)>120:
            return json_no_store({"error":"invalid_filter"},400)
        items=[i for i in items if i.current_revision.properties.get("component_id")==component_id]
    else:
        items=list(items[:501])
    if len(items)>500:
        return json_no_store({"error":"too_many_offers"},422)
    return json_no_store({"results":[offer_record(i) for i in items]})


@capability("business_write")
def offer_add(request):
    try:
        data=read_payload(request)
        if set(data)!={"name","properties"}:
            raise InvalidPricing("Offer requires name and structured properties")
        item=offer_create(actor=request.user,name=data["name"],properties=data["properties"])
        result=json_no_store(offer_record(item),201)
        result["Location"]="/api/v1/pricing/offers/"+item.public_id
        return result
    except (InvalidPricing,InvalidModel,RevisionConflict,SchemaWriteBlocked,ExhaustedIds) as exc:
        return _response_error(exc)


@require_http_methods(["GET","PATCH"])
@never_cache
@csrf_protect
def offer_detail(request,public_id):
    if request.method=="GET":return offer_get(request,public_id)
    return offer_update(request,public_id)


@capability("business_read")
def offer_get(request,public_id):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    return json_no_store(offer_record(_item(public_id)))


@capability("business_write")
def offer_update(request,public_id):
    item=_item(public_id)
    try:
        data=read_payload(request)
        if set(data)!={"expected_revision","name","properties"}:
            raise InvalidPricing("Revisions need expected_revision, name and full tariff properties")
        item=offer_revise(actor=request.user,item=item,
             expected_revision=data["expected_revision"],name=data["name"],properties=data["properties"])
        return json_no_store(offer_record(item))
    except (InvalidPricing,InvalidModel,RevisionConflict,SchemaWriteBlocked,ExhaustedIds) as exc:
        return _response_error(exc)


@require_GET
@never_cache
@capability("business_read")
def offer_revisions(request,public_id):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    item=_item(public_id)
    return json_no_store({"id":public_id,"revisions":[offer_record(item,r)
         for r in item.revisions.select_related("created_by").order_by("number")]})


@require_GET
@never_cache
@capability("business_read")
def offer_version(request,public_id,number):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    item=_item(public_id)
    rev=get_object_or_404(CatalogRevision,item=item,number=number)
    return json_no_store(offer_record(item,rev))


@require_http_methods(["GET","PATCH"])
@never_cache
@csrf_protect
def component_access(request,type_slug,public_id):
    if type_slug not in KINDS:raise Http404("Not a component type")
    item=get_object_or_404(CatalogItem.objects.select_related("current_revision"),
            type_slug=type_slug, public_id=public_id)
    if request.method=="GET":return _access_get(request,item)
    return _access_patch(request,item)


@capability("business_read")
def _access_get(request,item):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    return json_no_store({"component_id":item.public_id,
            "enterprise_accessibility":accessibility(item.current_revision.properties),
            "revision":f"r{item.current_revision.number:03d}",
            "individual_entitlement":"not_recorded_here"})


@capability("business_write")
def _access_patch(request,item):
    try:
        payload=read_payload(request)
        if set(payload)!={"expected_revision","enterprise_accessibility"} or (
            not isinstance(payload["enterprise_accessibility"],str) or
            payload["enterprise_accessibility"] not in ACCESS):
            raise InvalidPricing("Explicit enterprise accessibility status required")
        current=item.current_revision
        props=dict(current.properties)
        props["enterprise_accessibility"]=payload["enterprise_accessibility"]
        updated=revise_component(item=item,type_slug=item.type_slug,actor=request.user,
                                 expected_revision=payload["expected_revision"],
                                 properties=props)
        return json_no_store({"component_id":updated.public_id,
             "enterprise_accessibility":accessibility(updated.current_revision.properties),
             "revision":f"r{updated.current_revision.number:03d}",
             "individual_entitlement":"not_recorded_here"})
    except (InvalidPricing,InvalidModel,RevisionConflict,SchemaWriteBlocked,ExhaustedIds) as exc:
        return _response_error(exc)
