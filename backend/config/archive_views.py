"""Operator-only, no-store native archive download (PLAT-30)."""
from django.http import FileResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .archive_services import ArchiveError, build_native_export
from .auth_views import capability, json_no_store
from .evidence_store import EvidenceError


@require_GET
@never_cache
@capability("platform_view")
def native_export(request):
    if request.GET:
        return json_no_store({"error": "unsupported_export_options"}, 400)
    try:
        archive = build_native_export()
    except (ArchiveError, EvidenceError) as error:
        return json_no_store({"error": "archive_integrity_failed",
                              "message": str(error)}, 409)
    response = FileResponse(
        archive, as_attachment=True, filename="ai-compass-native-v1.zip",
        content_type="application/zip",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
