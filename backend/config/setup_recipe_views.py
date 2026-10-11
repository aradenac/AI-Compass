"""Read-only composition of immutable Setup Guide revisions (FUT-07).

Recipes are versioned Setup Guide properties. The endpoint never follows URLs,
uses no Demo records, and rejects cross-type or unpinned references.
"""
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q
from .auth_views import capability, json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .models import CatalogItem, CatalogRevision
from .setup_composition import compose, SetupCompositionError


@require_POST
@csrf_protect
@capability("business_read")
@never_cache
def render_recipe(request):
    try:
        payload = read_payload(request)
        if not isinstance(payload, dict) or set(payload) != {"guide_id", "revision", "configuration"}:
            raise SetupCompositionError("guide_id, revision and configuration are required")
        gid, rev, cfg = payload["guide_id"], payload["revision"], payload["configuration"]
        if not isinstance(gid, str) or not gid.startswith("gui-"):
            raise SetupCompositionError("Invalid recipe identifier")
        if not isinstance(rev, str) or not rev.startswith("r") or not rev[1:].isdigit():
            raise SetupCompositionError("Exact recipe revision required")
        if not isinstance(cfg, dict) or len(cfg) > 64:
            raise SetupCompositionError("Invalid configuration")
        item = CatalogItem.objects.filter(public_id=gid, type_slug="setup_guide").first()
        if item is None:
            return json_no_store({"error": "not_found"}, 404)
        recipe_revision = CatalogRevision.objects.filter(item=item, number=int(rev[1:])).first()
        if recipe_revision is None:
            return json_no_store({"error": "not_found"}, 404)
        spec = recipe_revision.properties.get("recipe")
        if not isinstance(spec, dict):
            raise SetupCompositionError("The pinned guide has no composable recipe")
        entries = spec.get("modules", [])
        if not isinstance(entries, list) or len(entries) > 128:
            raise SetupCompositionError("Invalid module count")
        pins = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise SetupCompositionError("Invalid module")
            ident, revision = entry.get("id"), entry.get("revision")
            if not isinstance(ident, str) or not ident.startswith("gui-"):
                raise SetupCompositionError("Invalid module identity")
            if not isinstance(revision, str) or not revision.startswith("r") or not revision[1:].isdigit():
                raise SetupCompositionError("Unpinned module")
            pins.add((ident, revision))
        snapshots = {}
        for mid, mr in pins:
            source = CatalogRevision.objects.select_related("item").filter(
                item__public_id=mid, item__type_slug="setup_guide", number=int(mr[1:])).first()
            if source is not None:
                snapshots[(mid, mr)] = {
                    "name": source.display_name, "properties": source.properties}
        rendered = compose(spec, snapshots, cfg)
        rendered["recipe"] = {"id": gid, "revision": rev, "revision_id": str(recipe_revision.pk)}
        return json_no_store(rendered)
    except (SetupCompositionError, InvalidModel, ValueError, TypeError) as exc:
        return json_no_store({"error": "invalid_recipe", "detail": str(exc)}, 400)
