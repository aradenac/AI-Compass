"""Confidential Server-only workload planning API (DAP-01)."""
import json

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_GET

from .auth_views import capability, json_no_store
from .models import TaskNode, WorkloadProfile
from .workload_services import (
    InvalidWorkload, StaleWorkload, create_profile, revise_profile, latest,
    serialize_profile, serialize_revision, effective,
)

MAX_BODY = 128 * 1024


def payload(request):
    if len(request.body) > MAX_BODY:
        raise InvalidWorkload("Profile payload exceeds 128 KiB")
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError) as error:
        raise InvalidWorkload("Invalid JSON") from error
    if not isinstance(data, dict):
        raise InvalidWorkload("Expected JSON object")
    return data


@require_GET
@never_cache
@capability("planning_view")
def task_choices(request):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    rows = TaskNode.objects.select_related("item__current_revision").order_by("item__public_id")[:501]
    if len(rows) > 500:
        return json_no_store({"error": "too_many_tasks"}, 422)
    return json_no_store({"results": [
        {"id": node.item.public_id,
         "name": node.item.current_revision.display_name,
         "parent_id": node.parent.item.public_id if node.parent else None}
        for node in rows
    ]})


@require_http_methods(["GET", "POST"])
@never_cache
@capability("planning_view")
def collection(request):
    if request.method == "GET":
        if request.GET:
            return json_no_store({"error": "invalid_filter"}, 400)
        qs = WorkloadProfile.objects.all().order_by("kind", "public_id")[:501]
        if len(qs) > 500:
            return json_no_store({"error": "too_many_profiles"}, 422)
        return json_no_store({"results": [serialize_profile(x) for x in qs]})
    if not request.user.has_perm("auth.planning_manage"):
        return json_no_store({"error": "permission_denied"}, 403)
    if request.method == "POST":
        return _write(request, None)
    return json_no_store({"error": "method_not_allowed"}, 405)


def _write(request, public_id):
    try:
        data = payload(request)
        if public_id is None:
            kind = data.pop("kind", None)
            profile = create_profile(actor=request.user, kind=kind, data=data)
            code = 201
        else:
            expected = data.pop("expected_revision", None)
            profile = revise_profile(actor=request.user, public_id=public_id,
                                     expected_revision=expected, data=data)
            code = 200
        return json_no_store(serialize_profile(profile), code)
    except StaleWorkload as error:
        return json_no_store({"error": "revision_conflict", "detail": str(error)}, 409)
    except InvalidWorkload as error:
        return json_no_store({"error": "invalid_workload", "detail": str(error)}, 400)


@require_http_methods(["GET", "PATCH"])
@never_cache
@capability("planning_view")
def detail(request, public_id):
    profile = get_object_or_404(WorkloadProfile, public_id=public_id)
    if request.method == "GET":
        if request.GET:
            return json_no_store({"error": "invalid_filter"}, 400)
        return json_no_store(serialize_profile(profile))
    if not request.user.has_perm("auth.planning_manage"):
        return json_no_store({"error": "permission_denied"}, 403)
    return _write(request, public_id)


@require_GET
@never_cache
@capability("planning_view")
def revisions(request, public_id):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    profile = get_object_or_404(WorkloadProfile, public_id=public_id)
    return json_no_store({"id": public_id, "revisions": [
        serialize_revision(x) for x in profile.revisions.select_related(
            "role", "specialty", "created_by").order_by("number")
    ]})


@require_GET
@never_cache
@capability("planning_view")
def revision(request, public_id, number):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    profile = get_object_or_404(WorkloadProfile, public_id=public_id)
    row = profile.revisions.filter(number=number).first()
    if row is None:
        raise Http404("Unknown historical revision")
    return json_no_store(serialize_revision(row))


@require_GET
@never_cache
@capability("planning_view")
def effective_workload(request, public_id):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    profile = get_object_or_404(WorkloadProfile, public_id=public_id)
    return json_no_store(effective(profile))
