"""Version-pinned public selection and strictly private review/preflight APIs."""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .auth_views import capability, json_no_store
from .catalog_services import RevisionConflict, SchemaWriteBlocked
from .campaign_services import InvalidCampaign, InvalidTransition, serialize
from .catalog_views import read_payload
from .models import CatalogItem
from . import publication_services as publication


def _item(public_id):
    if not public_id.startswith("cmp-"):
        raise Http404("Invalid campaign ID")
    return get_object_or_404(CatalogItem, type_slug="campaign", public_id=public_id)


@require_GET
@capability("business_read")
@never_cache
def current(request, public_id):
    """Published-only contract for all roles; no draft candidates or confidential setup."""
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    item = _item(public_id)
    event = publication.active_manifest(item)
    return json_no_store({
        "campaign_id": public_id, "publication": event,
        "effective_run_ids": [row["id"] for row in event["runs"]] if event else [],
        "scope": "effective_published_only"})


@require_GET
@capability("business_read")
@never_cache
def review(request, public_id):
    if not publication.can_preview(request.user):
        return json_no_store({"error": "permission_denied"}, 403)
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    item = _item(public_id)
    return json_no_store({
        "campaign_id": public_id, "revision": "r%03d" % item.current_revision.number,
        "status": item.current_revision.properties.get("status"),
        "candidates": publication.candidates(item),
        "last_publication": publication.effective(item),
        "scope": "private_workgroup_review"})


@require_POST
@csrf_protect
@capability("publication_review")
@never_cache
def publish(request, public_id):
    _item(public_id)
    try:
        data = read_payload(request)
        if set(data) - {"expected_revision", "run_ids", "removal_reason"}:
            raise InvalidCampaign("Unsupported publication fields")
        updated = publication.publish(
            actor=request.user, public_id=public_id,
            expected_revision=data.get("expected_revision"),
            run_ids=data.get("run_ids"),
            removal_reason=data.get("removal_reason", ""))
        return json_no_store({"campaign": serialize(updated),
                              "publication": publication.active_manifest(updated)})
    except (InvalidCampaign, ValueError) as exc:
        return json_no_store({"error": "invalid_publication", "detail": str(exc)}, 400)
    except (InvalidTransition, RevisionConflict, SchemaWriteBlocked) as exc:
        return json_no_store({"error": "publication_conflict", "detail": str(exc)}, 409)


@require_POST
@csrf_protect
@capability("publication_review")
@never_cache
def withdraw(request, public_id):
    _item(public_id)
    try:
        data = read_payload(request)
        if set(data) != {"expected_revision"} or not isinstance(data["expected_revision"], str):
            raise InvalidCampaign("Exactly one expected_revision is required")
        updated = publication.revoke(
            actor=request.user, public_id=public_id,
            expected_revision=data["expected_revision"])
        return json_no_store({"campaign": serialize(updated), "publication": None})
    except (InvalidCampaign, ValueError) as exc:
        return json_no_store({"error": "invalid_publication", "detail": str(exc)}, 400)
    except (InvalidTransition, RevisionConflict, SchemaWriteBlocked) as exc:
        return json_no_store({"error": "publication_conflict", "detail": str(exc)}, 409)
