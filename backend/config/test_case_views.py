"""Authenticated Server Test Design API. No Demo data or implicit imports."""
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .auth_views import capability, json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .catalog_services import RevisionConflict, ExhaustedIds
from .models import CatalogRevision, TestCase
from .test_case_services import InvalidTestCase, _case, create, fork, revise, serialize

CASE_FIELDS = frozenset({"task_id", "name", "properties"})
FORK_FIELDS = frozenset({"expected_parent_revision", "name", "properties"})
UPDATE_FIELDS = frozenset({"expected_revision", "name", "properties"})


def _parse(request, permitted):
    data=read_payload(request)
    if set(data)-permitted:
        raise InvalidTestCase("Unsupported fields: "+", ".join(sorted(set(data)-permitted)))
    if "properties" in data and not isinstance(data["properties"],dict):
        raise InvalidTestCase("properties must be a JSON object")
    return data


def _bad(error):
    return json_no_store({"error":"invalid_test_case","detail":str(error)},400)


def _write(handler):
    try:
        return handler()
    except (InvalidModel, InvalidTestCase) as err:
        return _bad(err)
    except RevisionConflict as err:
        return json_no_store({"error":"revision_conflict","detail":str(err)},409)
    except ExhaustedIds:
        return json_no_store({"error":"id_capacity_exhausted"},503)


@require_GET
@capability("business_read")
@never_cache
def list_cases(request):
    if set(request.GET)-{"task_id"}:
        return json_no_store({"error":"invalid_filter"},400)
    q=TestCase.objects.select_related(
        "item__current_revision__schema_version",
        "item__current_revision__created_by",
        "task__item","fork_parent__item",
        "task_revision_at_creation","fork_source_revision",
    ).order_by("task__item__public_id","case_version","item__public_id")
    task_id=request.GET.get("task_id")
    if task_id is not None:
        if not task_id.startswith("tsk-"):
            return json_no_store({"error":"invalid_task_id"},400)
        q=q.filter(task__item__public_id=task_id)
    return json_no_store({"results":[serialize(c) for c in q]})


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def add_case(request):
    def handle():
        data=_parse(request,CASE_FIELDS)
        case=create(actor=request.user,name=data.get("name"),
                    task_id=data.get("task_id"),properties=data.get("properties",{}))
        response=json_no_store(serialize(case),201)
        response["Location"]="/api/v1/test-cases/"+case.item.public_id
        return response
    return _write(handle)


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def fork_case(request,public_id):
    def handle():
        data=_parse(request,FORK_FIELDS)
        if not isinstance(data.get("expected_parent_revision"),str):
            raise InvalidTestCase("expected_parent_revision is required")
        case=fork(actor=request.user,parent_id=public_id,
                  expected_parent_revision=data["expected_parent_revision"],
                  name=data.get("name"),properties=data.get("properties"))
        response=json_no_store(serialize(case),201)
        response["Location"]="/api/v1/test-cases/"+case.item.public_id
        return response
    return _write(handle)


@require_GET
@capability("business_read")
@never_cache
def case_detail(request, public_id):
    return json_no_store(serialize(get_object_or_404(
        TestCase.objects.select_related("item__current_revision__schema_version",
            "item__current_revision__created_by","task__item",
            "fork_parent__item","task_revision_at_creation","fork_source_revision"),
        item__public_id=public_id,item__type_slug="test_case"
    )))


@require_http_methods(["PATCH"])
@csrf_protect
@capability("business_write")
@never_cache
def edit_case(request, public_id):
    def handle():
        data=_parse(request,UPDATE_FIELDS)
        if not isinstance(data.get("expected_revision"),str):
            raise InvalidTestCase("expected_revision is required")
        case=revise(actor=request.user,public_id=public_id,
                    expected_revision=data["expected_revision"],
                    name=data.get("name"),properties=data.get("properties"))
        return json_no_store(serialize(case))
    return _write(handle)


@require_GET
@capability("business_read")
@never_cache
def case_history(request,public_id):
    case=get_object_or_404(TestCase.objects.select_related(
        "task__item","fork_parent__item","task_revision_at_creation","fork_source_revision"),
        item__public_id=public_id,item__type_slug="test_case")
    revisions=CatalogRevision.objects.filter(item=case.item).select_related(
        "schema_version","created_by").order_by("number")
    return json_no_store({"id":public_id,"revisions":[serialize(case,r) for r in revisions]})


@require_GET
@capability("business_read")
@never_cache
def case_revision(request,public_id,number):
    case=get_object_or_404(TestCase.objects.select_related(
        "task__item","fork_parent__item","task_revision_at_creation","fork_source_revision"),
        item__public_id=public_id,item__type_slug="test_case")
    revision=get_object_or_404(CatalogRevision.objects.select_related(
        "schema_version","created_by"),item=case.item,number=number)
    return json_no_store(serialize(case,revision))


def collection(request):
    if request.method=="GET": return list_cases(request)
    if request.method=="POST": return add_case(request)
    return HttpResponseNotAllowed(["GET","POST"])


def detail(request,public_id):
    if request.method=="GET": return case_detail(request,public_id)
    if request.method=="PATCH": return edit_case(request,public_id)
    return HttpResponseNotAllowed(["GET","PATCH"])
