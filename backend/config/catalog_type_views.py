"""Typed shared REST contract for Provider/Harness/Framework, using Model foundation.

GET/POST collection; GET object; GET/POST immutable revision collection;
GET historical revision. No mutable PUT/PATCH/DELETE routes, no AI Solution side effects.
"""
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .auth_views import capability, json_no_store
from .catalog_schemas import InvalidModel
from .catalog_services import (
    CATALOG_TYPES, ExhaustedIds, RevisionConflict, SchemaWriteBlocked,
    create_component, revise_component,
)
from .catalog_views import read_payload, serialize
from .catalog_compat import registry_for_types
from .models import CatalogItem, CatalogRevision

EXTENDED_TYPES = frozenset({"provider", "harness", "framework"})


def registered_type(type_slug):
    if type_slug not in EXTENDED_TYPES:
        raise Http404("Unsupported catalog collection")
    return type_slug


def item_of_type(type_slug, public_id):
    registered_type(type_slug)
    if not public_id.startswith(CATALOG_TYPES[type_slug] + "-"):
        raise Http404("Wrong catalog type prefix")
    return get_object_or_404(
        CatalogItem.objects.select_related(
            "current_revision__schema_version", "current_revision__created_by"
        ), public_id=public_id, type_slug=type_slug,
    )


def invalid(error):
    return json_no_store({"error": "invalid_catalog_item", "detail": str(error)}, status=400)


@require_GET
@capability("business_read")
@never_cache
def list_components(request, type_slug):
    registered_type(type_slug)
    items = CatalogItem.objects.filter(type_slug=type_slug).select_related(
        "current_revision__schema_version", "current_revision__created_by"
    ).order_by("created_at")
    registry = registry_for_types([type_slug])
    return json_no_store({"results": [serialize(item, registries=registry) for item in items]})


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def add_component(request, type_slug):
    registered_type(type_slug)
    try:
        payload = read_payload(request)
        if set(payload) - {"name", "properties"}:
            raise InvalidModel("unknown top-level fields; use properties for extensions")
        item = create_component(
            type_slug=type_slug, actor=request.user,
            name=payload.get("name"), properties=payload.get("properties", {})
        )
    except InvalidModel as error:
        return invalid(error)
    except ExhaustedIds:
        return json_no_store({"error": "id_capacity_exhausted"}, status=503)
    response = json_no_store(serialize(item), status=201)
    response["Location"] = f"/api/v1/catalog/{type_slug}/{item.public_id}"
    return response


@require_GET
@capability("business_read")
@never_cache
def get_component(request, type_slug, public_id):
    return json_no_store(serialize(item_of_type(type_slug, public_id)))


@require_GET
@capability("business_read")
@never_cache
def list_revisions(request, type_slug, public_id):
    item = item_of_type(type_slug, public_id)
    rows = item.revisions.select_related("schema_version", "created_by").order_by("number")
    return json_no_store({"id": public_id, "revisions": [serialize(item, row) for row in rows]})


@require_GET
@capability("business_read")
@never_cache
def get_revision(request, type_slug, public_id, number):
    item = item_of_type(type_slug, public_id)
    row = get_object_or_404(
        CatalogRevision.objects.select_related("schema_version", "created_by"),
        item=item, number=number,
    )
    return json_no_store(serialize(item, row))


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def append_revision(request, type_slug, public_id):
    item = item_of_type(type_slug, public_id)
    try:
        payload = read_payload(request)
        if set(payload) - {"expected_revision", "name", "properties"}:
            raise InvalidModel("unknown top-level fields")
        expected = payload.get("expected_revision")
        if not isinstance(expected, str):
            raise InvalidModel("expected_revision is mandatory (e.g. r001)")
        if "properties" in payload and not isinstance(payload["properties"], dict):
            raise InvalidModel("properties must be a JSON object")
        revised = revise_component(
            type_slug=type_slug, item=item, actor=request.user,
            expected_revision=expected, name=payload.get("name"),
            properties=payload.get("properties"),
        )
    except InvalidModel as error:
        return invalid(error)
    except RevisionConflict as error:
        return json_no_store({"error": "revision_conflict", "detail": str(error)}, status=409)
    except SchemaWriteBlocked as error:
        return json_no_store({
            "error": "schema_write_blocked", "detail": str(error),
            "compatibility": error.compatibility,
        }, status=409)
    return json_no_store(serialize(revised), status=201)


def collection(request, type_slug):
    registered_type(type_slug)
    if request.method == "GET":
        return list_components(request, type_slug)
    if request.method == "POST":
        return add_component(request, type_slug)
    return HttpResponseNotAllowed(["GET", "POST"])


def revisions(request, type_slug, public_id):
    registered_type(type_slug)
    if request.method == "GET":
        return list_revisions(request, type_slug, public_id)
    if request.method == "POST":
        return append_revision(request, type_slug, public_id)
    return HttpResponseNotAllowed(["GET", "POST"])
