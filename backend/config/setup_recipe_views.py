"""FUT-07: scoped, revision-pinned Setup Guide composition preflight.

This is a read-only applicability inspector. It does not approve publication,
fetch any external URL or trust submitted values as measured Run evidence.
"""
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from .auth_views import capability, json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .models import CatalogItem, CatalogRevision
from .setup_composition import SetupCompositionError
from .setup_recipe_services import from_revision


@require_POST
@csrf_protect
@capability("business_read")
@never_cache
def render_recipe(request):
    try:
        payload = read_payload(request)
        if set(payload) != {"guide_id", "revision", "configuration"}:
            raise SetupCompositionError("guide_id, revision and configuration are required")
        gid, rev, cfg = payload["guide_id"], payload["revision"], payload["configuration"]
        if not isinstance(gid, str) or not gid.startswith("gui-"):
            raise SetupCompositionError("Invalid recipe identifier")
        if not isinstance(rev, str) or not (
            4 <= len(rev) <= 10 and rev.startswith("r") and rev[1:].isdigit()
        ):
            raise SetupCompositionError("Exact recipe revision required")
        if not isinstance(cfg, dict) or len(cfg) > 64:
            raise SetupCompositionError("Invalid configuration")
        item = CatalogItem.objects.filter(public_id=gid, type_slug="setup_guide").first()
        if item is None:
            return json_no_store({"error": "not_found"}, 404)
        recipe_revision = CatalogRevision.objects.filter(item=item, number=int(rev[1:])).first()
        if recipe_revision is None:
            return json_no_store({"error": "not_found"}, 404)
        rendered = from_revision(recipe_revision, cfg,
                                 require_wiring=bool(cfg.get("framework")))
        return json_no_store(rendered)
    except (SetupCompositionError, InvalidModel, ValueError, TypeError) as exc:
        return json_no_store({"error": "invalid_recipe", "detail": str(exc)}, 400)
