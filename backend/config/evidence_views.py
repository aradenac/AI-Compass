"""Session/CSRF-protected evidence API, never exposes filesystem paths."""
import json
import re

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .auth_views import capability, json_no_store
from .evidence_store import (
    BrokenEvidence, EvidenceError, attach, serialize, verify_bytes,
)
from .models import CatalogItem, CatalogRevision, EvidenceLink
from django.conf import settings

REVISION = re.compile(r"^r([1-9][0-9]{0,8})$")


def _item(public_id):
    return get_object_or_404(CatalogItem.objects.select_related("current_revision"), public_id=public_id)


def _owned_link(link_id):
    return get_object_or_404(
        EvidenceLink.objects.select_related("blob", "item", "revision", "uploaded_by"),
        pk=link_id,
    )


def _checked(link):
    row = serialize(link)
    try:
        verify_bytes(link.blob_id, size=link.blob.size)
        row["integrity"] = "ok"
    except (BrokenEvidence, EvidenceError):
        row["integrity"] = "broken"
    return row


@require_GET
@capability("business_read")
@never_cache
def list_evidence(request, public_id):
    item = _item(public_id)
    rows = EvidenceLink.objects.filter(item=item).select_related(
        "blob", "revision", "uploaded_by", "item"
    ).order_by("created_at", "id")
    return json_no_store({"item_id": public_id, "results": [_checked(link) for link in rows]})


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def upload_evidence(request, public_id):
    item = _item(public_id)
    try:
        # Avoid processing oversized request bodies before Django spools an upload.
        size = request.META.get("CONTENT_LENGTH", "")
        if size and int(size) > settings.EVIDENCE_MAX_BYTES + 512 * 1024:
            raise EvidenceError("Multipart request exceeds evidence upload limit")
        if not request.content_type.startswith("multipart/form-data"):
            raise EvidenceError("Multipart/form-data is required")
        if set(request.FILES) != {"file"} or len(request.FILES.getlist("file")) != 1:
            raise EvidenceError("Exactly one file must be uploaded")
        file = request.FILES["file"]
        if file.size > settings.EVIDENCE_MAX_BYTES or file.size < 1:
            raise EvidenceError("Evidence file must be nonempty and at most 16 MiB")
        source = request.POST.get("source", "")
        if not isinstance(source, str) or len(source) > 600:
            raise EvidenceError("Source must be at most 600 characters")
        raw_provenance = request.POST.get("provenance", "{}")
        if len(raw_provenance) > 8192:
            raise EvidenceError("Provenance metadata exceeds limit")
        try:
            provenance = json.loads(raw_provenance)
        except (ValueError, UnicodeDecodeError) as exc:
            raise EvidenceError("Provenance must be valid JSON") from exc
        if not isinstance(provenance, dict):
            raise EvidenceError("Provenance must be a JSON object")
        requested = request.POST.get("revision", "")
        revision = None
        if requested:
            match = REVISION.fullmatch(requested)
            if not match:
                raise EvidenceError("Revision must be an exact r001-style identifier")
            revision = get_object_or_404(CatalogRevision, item=item, number=int(match.group(1)))
        link = attach(
            item=item, revision=revision, file=file, actor=request.user,
            source=source, provenance=provenance,
        )
    except (EvidenceError, ValueError) as error:
        return json_no_store({"error": "invalid_evidence", "detail": str(error)}, status=400)
    response = json_no_store(_checked(link), status=201)
    response["Location"] = "/api/v1/evidence/" + str(link.pk)
    return response


@require_GET
@capability("business_read")
@never_cache
def evidence_detail(request, link_id):
    return json_no_store(_checked(_owned_link(link_id)))


@require_GET
@capability("business_read")
@never_cache
def evidence_download(request, link_id):
    link = _owned_link(link_id)
    try:
        path = verify_bytes(link.blob_id, size=link.blob.size)
        payload = path.open("rb")
    except (BrokenEvidence, EvidenceError, OSError):
        return json_no_store({
            "error": "broken_evidence", "detail": "Original evidence bytes are unavailable or corrupt",
        }, status=409)
    response = FileResponse(
        payload, as_attachment=True, filename=link.original_filename,
        content_type="application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
