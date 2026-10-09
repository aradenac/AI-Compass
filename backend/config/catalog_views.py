"""Small, session-authenticated Model JSON API, deliberately independent of Demo data."""
import json

from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .auth_views import capability, json_no_store
from .catalog_schemas import InvalidModel
from .catalog_services import create_model, model_schema, revise_model, RevisionConflict, ExhaustedIds
from .models import CatalogItem, CatalogRevision


def read_payload(request):
    if len(request.body) > 32_768:
        raise InvalidModel("request exceeds 32 KiB")
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise InvalidModel("expected JSON object") from None
    if not isinstance(data, dict):
        raise InvalidModel("expected JSON object")
    return data


def serialize(item, revision=None):
    rev = revision or item.current_revision
    return {
        "id": item.public_id,
        "uuid": str(item.pk),
        "type": item.type_slug,
        "name": rev.display_name,
        "properties": rev.properties,
        "schema_version": rev.schema_version.version,
        "revision": f"r{rev.number:03d}",
        "created_at": rev.created_at.isoformat(),
        "created_by": rev.created_by.get_username(),
    }


def find_item(public_id):
    return get_object_or_404(
        CatalogItem.objects.select_related("current_revision__schema_version", "current_revision__created_by"),
        public_id=public_id, type_slug="model"
    )


@require_GET
@capability("business_read")
@never_cache
def list_models(request):
    items = CatalogItem.objects.filter(type_slug="model").select_related(
        "current_revision__schema_version", "current_revision__created_by"
    ).order_by("created_at")
    return json_no_store({"results": [serialize(item) for item in items]})


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def add_model(request):
    try:
        payload = read_payload(request)
        if set(payload) - {"name", "properties"}:
            raise InvalidModel("unknown top-level fields; use properties for extensions")
        item = create_model(
            actor=request.user, name=payload.get("name"),
            properties=payload.get("properties", {})
        )
    except InvalidModel as exc:
        return json_no_store({"error": "invalid_model", "detail": str(exc)}, status=400)
    except ExhaustedIds:
        return json_no_store({"error": "id_capacity_exhausted"}, status=503)
    response = json_no_store(serialize(item), status=201)
    response["Location"] = f"/api/v1/models/{item.public_id}"
    return response


@require_GET
@capability("business_read")
@never_cache
def get_model(request, public_id):
    return json_no_store(serialize(find_item(public_id)))


@require_GET
@capability("business_read")
@never_cache
def model_revisions(request, public_id):
    item = find_item(public_id)
    revs = item.revisions.select_related("schema_version", "created_by").order_by("number")
    return json_no_store({"id": public_id, "revisions": [serialize(item, rev) for rev in revs]})


@require_GET
@capability("business_read")
@never_cache
def get_revision(request, public_id, number):
    item = find_item(public_id)
    rev = get_object_or_404(
        CatalogRevision.objects.select_related("schema_version", "created_by"),
        item=item, number=number
    )
    return json_no_store(serialize(item, rev))


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def add_revision(request, public_id):
    item = find_item(public_id)
    try:
        payload = read_payload(request)
        if set(payload) - {"expected_revision", "name", "properties"}:
            raise InvalidModel("unknown top-level fields")
        expected = payload.get("expected_revision")
        if not isinstance(expected, str):
            raise InvalidModel("expected_revision is mandatory (e.g. r001)")
        if "properties" in payload and not isinstance(payload["properties"], dict):
            raise InvalidModel("properties must be a JSON object")
        revised = revise_model(
            item=item, actor=request.user, expected_revision=expected,
            name=payload.get("name"),
            properties=payload.get("properties")
        )
    except InvalidModel as exc:
        return json_no_store({"error": "invalid_model", "detail": str(exc)}, status=400)
    except RevisionConflict as exc:
        return json_no_store({"error": "revision_conflict", "detail": str(exc)}, status=409)
    return json_no_store(serialize(revised), status=201)


@require_GET
@capability("business_read")
@never_cache
def get_model_schema(request):
    version = model_schema()
    return json_no_store({"type": version.type_slug, "version": version.version, "schema": version.json_schema})



def models_collection(request):
    """REST collection: GET list, POST create."""
    if request.method == "GET":
        return list_models(request)
    if request.method == "POST":
        return add_model(request)
    return HttpResponseNotAllowed(["GET", "POST"])


def revisions_collection(request, public_id):
    """REST history: GET all revisions, POST append with expected_revision."""
    if request.method == "GET":
        return model_revisions(request, public_id)
    if request.method == "POST":
        return add_revision(request, public_id)
    return HttpResponseNotAllowed(["GET", "POST"])
