"""FUT-06: self-service profile and safe, read-only composite OS discovery.

Auth is checked on every request. The actor can edit their OWN environment
only: no ability to edit another account or change role/entitlement.
"""
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .auth_views import capability, json_no_store, read_json
from .environment_services import (
    InvalidEnvironment, compose, validate_os, record_os, OS, DEPENDENT_TYPES)
from .models import UserEnvironmentRevision, CatalogItem, CatalogRevision


def _latest(user):
    return UserEnvironmentRevision.objects.filter(user=user).order_by("-number").first()


def _profile(user):
    latest = _latest(user)
    return {"configured": latest is not None,
            "available_os": latest.available_os if latest else None,
            "revision": f"r{latest.number:03d}" if latest else None,
            "entitlement_status": "not_verified_by_os",
            "source": "self_declared" if latest else "unconfigured"}


@require_http_methods(["GET", "PATCH"])
@never_cache
@csrf_protect
@capability("business_read")
def profile(request):
    if request.method == "GET":
        if request.GET:
            return json_no_store({"error": "invalid_query"}, 400)
        return json_no_store(_profile(request.user))
    data = read_json(request)
    if not isinstance(data, dict) or set(data) != {"expected_revision", "available_os"}:
        return json_no_store({"error": "invalid_environment_payload"}, 400)
    try:
        values = validate_os(data["available_os"])
    except InvalidEnvironment as exc:
        return json_no_store({"error": "invalid_environment", "detail": str(exc)}, 400)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk, is_active=True)
        current = _latest(user)
        expected = f"r{current.number:03d}" if current else None
        if data["expected_revision"] != expected:
            return json_no_store({"error": "revision_conflict",
                "detail": "Reload your personal environment before editing"}, 409)
        if current is not None and current.available_os == values:
            return json_no_store(_profile(user))
        UserEnvironmentRevision.objects.create(
            user=user, number=current.number + 1 if current else 1, available_os=values)
        return json_no_store(_profile(user))


@require_GET
@never_cache
@capability("business_read")
def profile_revisions(request):
    if request.GET:
        return json_no_store({"error": "invalid_query"}, 400)
    return json_no_store({"revisions": [
        {"revision":f"r{rev.number:03d}","available_os":rev.available_os,
         "created_at":rev.created_at.isoformat()}
        for rev in UserEnvironmentRevision.objects.filter(
            user=request.user).order_by("number")
    ]})


@require_http_methods(["POST"])
@never_cache
@csrf_protect
@capability("business_read")
def configuration(request):
    """Only identifiers of pinned Server catalog source revisions, never Demo records.

    Evaluates one local environment. Multiple participants are treated as
    sharing an OS, not as a falsely verified cross-machine workflow.
    """
    # The shared POST evaluator can include up to 65 exact source revisions;
    # the generic sign-in 4 KiB body limit is intentionally not reused here.
    import json
    try:
        data = json.loads(request.body) if len(request.body) <= 16384 else None
    except (UnicodeDecodeError, ValueError):
        data = None
    if not isinstance(data, dict) or set(data) - {"components", "topology"}:
        return json_no_store({"error": "invalid_configuration"}, 400)
    refs = data.get("components")
    topology = data.get("topology", "shared_os")
    if not isinstance(refs, list) or not 1 <= len(refs) <= 65:
        return json_no_store({"error": "invalid_configuration"}, 400)
    if not isinstance(topology, str) or topology not in ("shared_os", "distributed_unknown"):
        return json_no_store({"error": "invalid_topology"}, 400)
    # Require an exact immutable revision ID for reproducibility; caller must
    # explicitly choose the revision, never silently resolve latest at evaluation.
    resolved = []
    ids = set()
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"type", "id", "revision_id"} or (
            not isinstance(ref.get("type"), str) or ref["type"] not in DEPENDENT_TYPES or
            not isinstance(ref.get("id"), str) or len(ref["id"]) > 120 or
            not isinstance(ref.get("revision_id"), str) or len(ref["revision_id"]) > 48):
            return json_no_store({"error": "invalid_component_reference"}, 400)
        try:
            revision_uuid = UUID(ref["revision_id"])
        except (ValueError, AttributeError):
            return json_no_store({"error": "invalid_revision_identifier"}, 400)
        lookup = (ref["type"], ref["id"], ref["revision_id"])
        if lookup in ids:
            return json_no_store({"error": "duplicate_component_reference"}, 400)
        ids.add(lookup)
        item = CatalogItem.objects.filter(public_id=ref["id"],
            type_slug=ref["type"]).first()
        if item is None:
            return json_no_store({"error": "unknown_component_reference"}, 404)
        rev = CatalogRevision.objects.filter(pk=revision_uuid, item=item).first()
        if rev is None:
            return json_no_store({"error": "revision_not_pinned_to_component"}, 400)
        resolved.append({"type":ref["type"],"id":item.public_id,
                         "revision":f"r{rev.number:03d}","revision_id":str(rev.id),
                         "properties":rev.properties})
    available = _profile(request.user)["available_os"]
    result = compose(resolved, available, topology=topology)
    result["sources"] = [{
        **s, "revision_id": next(p["revision_id"] for p in resolved
            if p["id"] == s["id"] and p["revision"] == s["revision"])
    } for s in result.get("sources", [])]
    result["user_environment"] = _profile(request.user)
    result["enterprise_accessibility"] = "separate_catalog_metadata"
    result["individual_entitlement"] = "not_verified"
    result["setup_guide"] = "not_verified"
    result["evidence_quality"] = "not_assessed"
    return json_no_store(result)
