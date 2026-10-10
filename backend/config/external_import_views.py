"""Authenticated mock-import preview/apply; never reachable on normal Server."""
import json

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .auth_views import capability, json_no_store
from .external_mock_import import (
    ImportInputError, ImportConflict, mock_enabled, plan, signed_preview,
    apply as apply_rows, receipt,
)
from .models import ExternalImportBatch


def input_json(request):
    if len(request.body) > 64 * 1024:
        raise ImportInputError("Mock import request exceeds 64 KiB")
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError) as error:
        raise ImportInputError("Expected valid JSON object") from error
    if not isinstance(payload, dict):
        raise ImportInputError("Expected JSON object")
    return payload


@require_POST
@csrf_protect
@never_cache
@capability("import_preview")
def preview(request):
    if not mock_enabled():
        raise Http404("Mock import disabled outside isolated staging")
    try:
        result = plan(input_json(request))
        result["preview_token"] = signed_preview(result, request.user)
        return json_no_store(result)
    except ImportInputError as error:
        return json_no_store({"error": "invalid_mock_source", "detail": str(error)}, 400)


@require_POST
@csrf_protect
@never_cache
@capability("import_apply")
def apply(request):
    if not mock_enabled():
        raise Http404("Mock import disabled outside isolated staging")
    try:
        content = input_json(request)
        token = content.pop("preview_token", None)
        result = apply_rows(content, preview_token=token, actor=request.user)
        return json_no_store(result, 200 if result["already_imported"] else 201)
    except ImportConflict as error:
        return json_no_store({"error": "source_or_preview_conflict", "detail": str(error)}, 409)
    except ImportInputError as error:
        return json_no_store({"error": "invalid_mock_source", "detail": str(error)}, 400)


@require_GET
@never_cache
@capability("import_preview")
def batch(request, batch_id):
    if not mock_enabled():
        raise Http404("Mock import disabled outside isolated staging")
    if request.GET:
        return json_no_store({"error": "invalid_query"}, 400)
    return json_no_store(receipt(get_object_or_404(ExternalImportBatch, pk=batch_id)))
