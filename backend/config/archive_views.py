"""FUT-02: explicit archive-export grant; read-only platform roles cannot stream confidential bytes."""
import logging
from django.http import FileResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .archive_services import ArchiveError, build_native_export
from .auth_views import capability, json_no_store
from .evidence_store import EvidenceError

logger = logging.getLogger(__name__)


@require_GET
@never_cache
@capability("archive_export")
def native_export(request):
    if request.GET:
        return json_no_store({"error": "unsupported_export_options"}, 400)
    try:
        archive = build_native_export()
    except (ArchiveError, EvidenceError) as error:
        logger.warning("archive_export_refused actor_id=%s reason=integrity", request.user.pk)
        return json_no_store({"error": "archive_integrity_failed",
                              "message": str(error)}, 409)
    logger.warning("security_audit archive_export_built actor_id=%s format=native-v1", request.user.pk)
    response = FileResponse(
        archive, as_attachment=True, filename="ai-compass-native-v1.zip",
        content_type="application/zip",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
@never_cache
@capability("platform_view")
def archive_inventory(request):
    """Read-only catalog of supported archive operations, NEVER archive content."""
    return json_no_store({
        "native": {"format": "ai-compass-native-v1",
                   "export": "/api/v1/archives/native",
                   "job_build": "/api/v1/archives/jobs",
                   "can_export": request.user.has_perm("auth.archive_export"),
                   "required_permission": "archive_export"},
        "complete_recovery": {"transfer": "operator_cli_only",
                              "http_download": "not_yet_available"},
    })
