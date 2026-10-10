"""PLAT-20: authenticated versioned theoretical forecasts and explicit validation-campaign action."""
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
from . import forecast_services as svc
from .campaign_services import InvalidCampaign,serialize as campaign_serialize


def _reader(user):
    return not (user.has_perm("auth.business_write") or
                user.has_perm("auth.publication_review"))


def _item(identifier):
    if not isinstance(identifier,str) or not identifier.startswith("fct-"):
        raise Http404("Not a Forecast identifier")
    return get_object_or_404(CatalogItem.objects.select_related(
        "current_revision__created_by"),public_id=identifier,type_slug="forecast")


def _visible(item,rev,user):
    record=svc.serialize(item,rev=rev,reader=_reader(user))
    if record is None:raise Http404("Internal forecast")
    return record


def _payload(request,allowed):
    data=read_payload(request)
    if set(data)-allowed:raise svc.ForecastInvalid("Unsupported Forecast fields")
    return data


def _error(error):
    if isinstance(error,RevisionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(error)},409)
    if isinstance(error,SchemaWriteBlocked):
        return json_no_store({"error":"schema_write_blocked","detail":str(error)},409)
    if isinstance(error,ExhaustedIds):
        return json_no_store({"error":"id_exhausted"},503)
    return json_no_store({"error":"invalid_forecast","detail":str(error)},400)


@csrf_protect
@capability("business_read")
@never_cache
def collection(request):
    if request.method=="GET":
        if set(request.GET)-{"task_id"}:
            return json_no_store({"error":"invalid_filter"},400)
        task_id=request.GET.get("task_id")
        if task_id is not None and (not task_id.startswith("tsk-") or len(task_id)>120):
            return json_no_store({"error":"invalid_task_filter"},400)
        results=svc.accessible(request.user,task_id=task_id)
        if len(results)>500:return json_no_store({"error":"too_many_forecasts"},422)
        return json_no_store({"results":results})
    if request.method!="POST":return HttpResponseNotAllowed(["GET","POST"])
    if not request.user.has_perm("auth.business_write"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=_payload(request,{"name","properties","task_id","component_ids",
                               "configuration","watch_links"})
        item=svc.create(actor=request.user,data=data)
        response=json_no_store(svc.serialize(item),201)
        response["Location"]="/api/v1/forecasts/"+item.public_id
        return response
    except (InvalidModel,svc.ForecastInvalid,RevisionConflict,SchemaWriteBlocked,
            ExhaustedIds,ValueError) as error:return _error(error)


@csrf_protect
@capability("business_read")
@never_cache
def detail(request,public_id):
    item=_item(public_id)
    if request.method=="GET":return json_no_store(_visible(item,None,request.user))
    if request.method!="PATCH":return HttpResponseNotAllowed(["GET","PATCH"])
    if not request.user.has_perm("auth.business_write"):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=_payload(request,{"expected_revision","name","properties","task_id",
                               "component_ids","configuration","watch_links"})
        if not isinstance(data.get("expected_revision"),str):
            raise svc.ForecastInvalid("expected_revision required")
        item,changed=svc.change(actor=request.user,identifier=public_id,data=data)
        return json_no_store({"record":svc.serialize(item),"changed":changed})
    except (InvalidModel,svc.ForecastInvalid,RevisionConflict,SchemaWriteBlocked,ValueError) as error:
        return _error(error)


@require_GET
@capability("business_read")
@never_cache
def history(request,public_id):
    item=_item(public_id)
    rows=[]
    for rev in CatalogRevision.objects.filter(item=item).select_related("created_by").order_by("number"):
        record=svc.serialize(item,rev=rev,reader=_reader(request.user))
        if record is not None:rows.append(record)
    if _reader(request.user) and not rows:raise Http404("Internal forecast")
    return json_no_store({"id":item.public_id,"revisions":rows})


@require_GET
@capability("business_read")
@never_cache
def version(request,public_id,number):
    item=_item(public_id)
    rev=get_object_or_404(CatalogRevision.objects.select_related(
        "created_by"),item=item,number=number)
    return json_no_store(_visible(item,rev,request.user))


@require_POST
@csrf_protect
@capability("business_read")
@never_cache
def action(request,public_id,action):
    _item(public_id)
    required="publication_review" if action in ("review","publish","unpublish") else "business_write"
    if not request.user.has_perm("auth."+required):
        return json_no_store({"error":"permission_denied"},403)
    try:
        data=_payload(request,{"expected_revision","review_notes"})
        if not isinstance(data.get("expected_revision"),str):
            raise svc.ForecastInvalid("expected_revision required")
        item,changed=svc.change(actor=request.user,identifier=public_id,
                                data=data,action=action)
        return json_no_store({"record":svc.serialize(item),"changed":changed})
    except (InvalidModel,svc.ForecastInvalid,RevisionConflict,SchemaWriteBlocked,ValueError) as error:
        return _error(error)


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def start_campaign(request,public_id):
    _item(public_id)
    try:
        data=_payload(request,{"forecast_revision","name","objective","notes",
                               "test_case_ids","guide_id","owner"})
        item=svc.start_campaign(actor=request.user,identifier=public_id,data=data)
        response=json_no_store(campaign_serialize(item),201)
        response["Location"]="/api/v1/campaigns/"+item.public_id
        return response
    except (InvalidModel,svc.ForecastInvalid,InvalidCampaign,RevisionConflict,
            SchemaWriteBlocked,ExhaustedIds,ValueError) as error:
        return _error(error)
