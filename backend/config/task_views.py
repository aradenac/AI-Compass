"""Session-authenticated task taxonomy API. No Demo fallback or destructive routes."""
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .auth_views import capability, json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .catalog_services import ExhaustedIds, RevisionConflict
from .models import CatalogRevision, TaskNode
from .task_services import InvalidTask, create_task, serialize_task, update_task

BASE_FIELDS = frozenset({"name", "properties", "parent_id", "before"})
UPDATE_FIELDS = BASE_FIELDS | {"expected_revision"}


def _invalid(error):
    return json_no_store({"error": "invalid_task", "detail": str(error)}, status=400)


def _parse(request, allowed):
    payload = read_payload(request)
    unknown = set(payload) - allowed
    if unknown:
        raise InvalidTask("Unsupported fields: " + ", ".join(sorted(unknown)))
    for key in ("parent_id", "before"):
        if key in payload and payload[key] is not None and not isinstance(payload[key], str):
            raise InvalidTask(key + " must be a task ID or null")
    if "properties" in payload and not isinstance(payload["properties"], dict):
        raise InvalidTask("properties must be an object")
    return payload


def _node(public_id):
    if not public_id.startswith("tsk-"):
        raise Http404("Wrong task identifier type")
    return get_object_or_404(
        TaskNode.objects.select_related(
            "item__current_revision__schema_version",
            "item__current_revision__created_by", "parent__item"
        ), item__public_id=public_id, item__type_slug="task",
    )


@require_GET
@capability("business_read")
@never_cache
def list_tasks(request):
    nodes = TaskNode.objects.select_related(
        "item__current_revision__schema_version",
        "item__current_revision__created_by", "parent__item",
    ).order_by("position", "item__public_id")
    return json_no_store({"results": [serialize_task(n) for n in nodes]})


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def add_task(request):
    try:
        payload = _parse(request, BASE_FIELDS)
        task = create_task(
            actor=request.user, name=payload.get("name"),
            properties=payload.get("properties"),
            parent_id=payload.get("parent_id"), before=payload.get("before"),
        )
    except (InvalidModel, InvalidTask) as error:
        return _invalid(error)
    except ExhaustedIds:
        return json_no_store({"error": "id_capacity_exhausted"}, status=503)
    response = json_no_store(serialize_task(task), status=201)
    response["Location"] = "/api/v1/tasks/" + task.item.public_id
    return response


@require_GET
@capability("business_read")
@never_cache
def get_task(request, public_id):
    return json_no_store(serialize_task(_node(public_id)))


@require_http_methods(["PATCH"])
@csrf_protect
@capability("business_write")
@never_cache
def patch_task(request, public_id):
    node = _node(public_id)
    try:
        payload = _parse(request, UPDATE_FIELDS)
        if not isinstance(payload.get("expected_revision"), str):
            raise InvalidTask("expected_revision is required")
        kwargs = {}
        if "parent_id" in payload:
            kwargs["parent_id_marker"] = payload["parent_id"]
        if "before" in payload:
            kwargs["before_marker"] = payload["before"]
        if "properties" in payload:
            kwargs["properties"] = payload["properties"]
        if "name" in payload:
            kwargs["name"] = payload["name"]
        updated, changed = update_task(
            public_id=node.item.public_id, actor=request.user,
            expected_revision=payload["expected_revision"], **kwargs,
        )
    except (InvalidModel, InvalidTask) as error:
        return _invalid(error)
    except RevisionConflict as error:
        return json_no_store({"error": "revision_conflict", "detail": str(error)}, status=409)
    return json_no_store({"task": serialize_task(updated), "changed": changed})


@require_GET
@capability("business_read")
@never_cache
def task_history(request, public_id):
    node = _node(public_id)
    revisions = CatalogRevision.objects.filter(item=node.item).select_related(
        "schema_version", "created_by", "task_structure__parent__item"
    ).order_by("number")
    return json_no_store({
        "id": public_id,
        "revisions": [serialize_task(node, rev) for rev in revisions],
    })


@require_GET
@capability("business_read")
@never_cache
def task_revision(request, public_id, number):
    node = _node(public_id)
    rev = get_object_or_404(
        CatalogRevision.objects.select_related(
            "schema_version", "created_by", "task_structure__parent__item"
        ), item=node.item, number=number,
    )
    return json_no_store(serialize_task(node, rev))


def collection(request):
    if request.method == "GET":
        return list_tasks(request)
    if request.method == "POST":
        return add_task(request)
    return HttpResponseNotAllowed(["GET", "POST"])


def detail(request, public_id):
    if request.method == "GET":
        return get_task(request, public_id)
    if request.method == "PATCH":
        return patch_task(request, public_id)
    return HttpResponseNotAllowed(["GET", "PATCH"])
