"""PLAT-12: authenticated campaign planning, revisions and workgroup pipeline."""
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .auth_views import capability, json_no_store
from .catalog_schemas import InvalidModel
from .pricing_services import InvalidPricing
from .catalog_services import RevisionConflict, SchemaWriteBlocked, ExhaustedIds
from .catalog_views import read_payload
from .models import CatalogItem, CatalogRevision, ObjectTypeVersion
from .campaign_services import (
    InvalidCampaign, InvalidTransition, MODES, create, modify, serialize,
)

FIELDS=frozenset({"name","objective","notes","properties","owner","mode",
                  "method_version","task_id","component_ids","test_case_ids",
                  "guide_id","configuration","repin","framework_id","participants", "pricing_selections"})
EDIT_FIELDS=FIELDS|{"expected_revision"}
ACTION_FIELDS=frozenset({"expected_revision"})
TRANSITIONS=frozenset({"start","close","rework","publish","unpublish","reopen","archive","restore"})


def _payload(request, allowed):
    data=read_payload(request)
    unexpected=set(data)-allowed
    if unexpected:
        raise InvalidCampaign("Unsupported fields: "+", ".join(sorted(unexpected)))
    return data


def _error(exc):
    if isinstance(exc,RevisionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    if isinstance(exc,SchemaWriteBlocked):
        return json_no_store({"error":"schema_write_blocked","detail":str(exc),
                              "compatibility":exc.compatibility},409)
    if isinstance(exc,InvalidTransition):
        return json_no_store({"error":"invalid_transition","detail":str(exc)},409)
    if isinstance(exc,ExhaustedIds):
        return json_no_store({"error":"public_id_exhausted"},503)
    return json_no_store({"error":"invalid_campaign","detail":str(exc)},400)


def _write(fn):
    try:
        return fn()
    except (InvalidPricing,InvalidModel,InvalidCampaign,InvalidTransition,RevisionConflict,
            SchemaWriteBlocked,ExhaustedIds) as exc:
        return _error(exc)


def _item(public_id):
    if not public_id.startswith("cmp-"):
        from django.http import Http404
        raise Http404("Not a campaign identifier")
    return get_object_or_404(CatalogItem.objects.select_related(
        "current_revision__schema_version","current_revision__created_by"),
        public_id=public_id,type_slug="campaign")


@require_GET
@capability("business_read")
@never_cache
def methods(request):
    if request.GET:
        return json_no_store({"error":"invalid_filter"},400)
    rows=ObjectTypeVersion.objects.filter(type_slug__in=[
        "campaign_method_"+m for m in MODES]).order_by("type_slug","version")
    return json_no_store({"results":[
        {"id":str(row.pk),"mode":row.type_slug.removeprefix("campaign_method_"),
         "version":row.version,"descriptor":row.json_schema}
        for row in rows]})


def _list(include_archived=True):
    items=CatalogItem.objects.filter(type_slug="campaign").select_related(
        "current_revision__schema_version","current_revision__created_by"
    ).order_by("created_at","public_id")
    rows=list(items[:501])
    if len(rows)>500:
        return None
    result=[serialize(item) for item in rows]
    return result if include_archived else [x for x in result if not x["archived"]]


@require_GET
@capability("business_read")
@never_cache
def list_campaigns(request):
    if set(request.GET)-{"include_archived"}:
        return json_no_store({"error":"invalid_filter"},400)
    flag=request.GET.get("include_archived","true")
    if flag not in ("true","false"):
        return json_no_store({"error":"invalid_filter"},400)
    result=_list(include_archived=(flag=="true"))
    if result is None:
        return json_no_store({"error":"too_many_campaigns","detail":"Campaign listing limit (500) reached"},422)
    return json_no_store({"results":result})


@require_GET
@capability("business_read")
@never_cache
def pipeline(request):
    if request.GET: return json_no_store({"error":"invalid_filter"},400)
    result=_list(include_archived=False)
    if result is None:
        return json_no_store({"error":"too_many_campaigns"},422)
    return json_no_store({"columns":{state:[
        {"id":row["id"],"name":row["name"],"objective":row["properties"]["objective"],
         "owner":row["owner"],"mode":row["mode"],
         "test_case_count":len(row["test_case_ids"]),
         "completed_runs":0,"revision":row["revision"]}
        for row in result if row["status"]==state
    ] for state in ("planned","in_progress","under_review","published")}})


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def add_campaign(request):
    def run():
        item=create(actor=request.user,data=_payload(request,FIELDS))
        response=json_no_store(serialize(item),201)
        response["Location"]="/api/v1/campaigns/"+item.public_id
        return response
    return _write(run)


@require_GET
@capability("business_read")
@never_cache
def get_campaign(request, public_id):
    return json_no_store(serialize(_item(public_id)))


@require_http_methods(["PATCH"])
@csrf_protect
@capability("business_write")
@never_cache
def edit_campaign(request, public_id):
    _item(public_id)
    def run():
        data=_payload(request,EDIT_FIELDS)
        if not isinstance(data.get("expected_revision"),str):
            raise InvalidCampaign("expected_revision is required")
        item,changed=modify(actor=request.user,public_id=public_id,data=data)
        return json_no_store({"campaign":serialize(item),"changed":changed})
    return _write(run)


@require_POST
@csrf_protect
@capability("business_read")
@never_cache
def transition(request,public_id,action):
    _item(public_id)
    required="publication_review" if action in ("publish","unpublish") else "business_write"
    if not request.user.has_perm("auth."+required):
        return json_no_store({"error":"permission_denied"},403)
    def run():
        if action not in TRANSITIONS:
            raise InvalidCampaign("Unknown lifecycle action")
        data=_payload(request,ACTION_FIELDS)
        if not isinstance(data.get("expected_revision"),str):
            raise InvalidCampaign("expected_revision is required")
        item,changed=modify(actor=request.user,public_id=public_id,data=data,action=action)
        return json_no_store({"campaign":serialize(item),"changed":changed})
    return _write(run)


@require_GET
@capability("business_read")
@never_cache
def history(request,public_id):
    item=_item(public_id)
    revisions=CatalogRevision.objects.filter(item=item).select_related(
        "schema_version","created_by").order_by("number")
    return json_no_store({"id":item.public_id,
                          "revisions":[serialize(item,rev) for rev in revisions]})


@require_GET
@capability("business_read")
@never_cache
def revision(request,public_id,number):
    item=_item(public_id)
    rev=get_object_or_404(CatalogRevision.objects.select_related(
        "schema_version","created_by"),item=item,number=number)
    return json_no_store(serialize(item,rev))


def collection(request):
    if request.method=="GET": return list_campaigns(request)
    if request.method=="POST": return add_campaign(request)
    return HttpResponseNotAllowed(["GET","POST"])


def detail(request,public_id):
    if request.method=="GET": return get_campaign(request,public_id)
    if request.method=="PATCH": return edit_campaign(request,public_id)
    return HttpResponseNotAllowed(["GET","PATCH"])
