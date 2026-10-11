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

REVISION = re.compile(r"^r(0*[1-9][0-9]{0,8})$")


def _item(public_id):
    return get_object_or_404(CatalogItem.objects.select_related("current_revision"), public_id=public_id)


def _owned_link(link_id):
    return get_object_or_404(
        EvidenceLink.objects.select_related("blob", "item", "revision", "uploaded_by"),
        pk=link_id,
    )




def _watch_evidence_published(item, revision):
    if item.type_slug=="recommendation":
        from .recommendation_services import serialize
    elif item.type_slug=="forecast":
        from .forecast_services import serialize
    else:
        from .watch_services import serialize
    return (revision is not None and serialize(item,rev=revision,reader=True) is not None)


def _watch_readable(request, item, revision=None):
    """Never disclose unpublished source/watch files by guessing stable evidence UUIDs."""
    if item.type_slug in ("discussion_thread","discussion_message"):
        from django.http import Http404
        from .discussion_services import readable_revision
        if revision is None or not readable_revision(item,request.user,revision):
            raise Http404("Private or unpinned discussion evidence")
        return
    if item.type_slug not in ("research_source","watch_entry","forecast","recommendation"):
        return
    if request.user.has_perm("auth.business_write") or request.user.has_perm("auth.publication_review"):
        return
    from django.http import Http404
    if item.type_slug=="recommendation":
        from .recommendation_services import serialize
    elif item.type_slug=="forecast":
        from .forecast_services import serialize
    else:
        from .watch_services import serialize
    data=serialize(item,rev=revision,reader=True)
    if revision is None and item.type_slug in ("research_source","watch_entry","forecast","recommendation"):
        # Old links without a precise revision must never be made public by
        # a later change of visibility.
        data=None
    if data is None:
        raise Http404("Private Research Source / Watch evidence")

def _campaign_link_readable(request, link):
    """An unpublished campaign upload must not be downloadable via guessed UUID."""
    if link.item.type_slug != "campaign":
        return
    if request.user.has_perm("auth.business_write") or request.user.has_perm("auth.publication_review"):
        return
    from django.http import Http404
    from .publication_services import effective_ids
    from .models import BenchmarkRunEvidence, CompositeRunEvidence
    allowed = effective_ids(link.item.public_id)
    if not (BenchmarkRunEvidence.objects.filter(
            evidence=link, run__public_id__in=allowed).exists() or
            CompositeRunEvidence.objects.filter(
            evidence=link, run__public_id__in=allowed).exists()):
        raise Http404("Unpublished campaign evidence")


def _checked(link, *, full_integrity=True):
    row = serialize(link)
    # A metadata listing NEVER reads file bytes. A null verification timestamp is
    # honest: only explicit detail, download, archive or maintenance scan re-hash
    # evidence; we do not persist a per-blob freshness checkpoint yet.
    if not full_integrity:
        row["integrity"] = "not_checked"
        row["verification"] = {"status": "not_checked", "last_verified_at": None}
        return row
    try:
        verify_bytes(link.blob_id, size=link.blob.size)
        row["integrity"] = "ok"
    except (BrokenEvidence, EvidenceError):
        row["integrity"] = "broken"
    row["verification"] = {"status": row["integrity"],
                           "last_verified_at": None, "scope": "this_request"}
    return row


@require_GET
@capability("business_read")
@never_cache
def list_evidence(request, public_id):
    item = _item(public_id)
    if item.type_slug in ("research_source","watch_entry","forecast","recommendation") and not (
            request.user.has_perm("auth.business_write") or
            request.user.has_perm("auth.publication_review")):
        from django.http import Http404
        if item.type_slug=="recommendation":
            from .recommendation_services import serialize
        elif item.type_slug=="forecast":
            from .forecast_services import serialize
        else:
            from .watch_services import serialize
        if serialize(item,reader=True) is None:
            raise Http404("Private Research Source / Watch evidence")
    if item.type_slug in ("discussion_thread","discussion_message"):
        from django.http import Http404
        from .discussion_services import readable_revision
        if not readable_revision(item,request.user):
            raise Http404("Private discussion attachments")
    rows = EvidenceLink.objects.filter(item=item).select_related(
        "blob", "revision", "uploaded_by", "item"
    ).order_by("created_at", "id")
    if item.type_slug in ("research_source","watch_entry","forecast","recommendation") and not (
            request.user.has_perm("auth.business_write") or
            request.user.has_perm("auth.publication_review")):
        rows = [link for link in rows if link.revision_id is not None and
                _watch_evidence_published(item,link.revision)]
    if item.type_slug in ("discussion_thread","discussion_message"):
        from .discussion_services import readable_revision
        rows=[link for link in rows if link.revision_id is not None and
              readable_revision(item,request.user,link.revision)]
    if item.type_slug == "campaign" and not (
            request.user.has_perm("auth.business_write") or
            request.user.has_perm("auth.publication_review")):
        from .publication_services import effective_ids
        from .models import BenchmarkRunEvidence, CompositeRunEvidence
        allowed = effective_ids(item.public_id)
        run_pins = set(BenchmarkRunEvidence.objects.filter(
            run__public_id__in=allowed).values_list("evidence_id", flat=True))
        run_pins.update(CompositeRunEvidence.objects.filter(
            run__public_id__in=allowed).values_list("evidence_id", flat=True))
        rows = [link for link in rows if link.pk in run_pins]
    return json_no_store({"item_id": public_id, "results": [_checked(link, full_integrity=False) for link in rows]})


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
        if item.type_slug in ("research_source","watch_entry","forecast","recommendation",
                              "discussion_thread","discussion_message") and not requested:
            raise EvidenceError("Source and Watch evidence must pin an exact revision")
        revision = None
        if requested:
            match = REVISION.fullmatch(requested)
            if not match or requested != f"r{int(match.group(1)):03d}":
                raise EvidenceError("Revision must be an exact r001-style identifier")
            revision = get_object_or_404(CatalogRevision, item=item, number=int(match.group(1)))
        if item.type_slug in ("discussion_thread","discussion_message"):
            from .discussion_services import readable_revision
            if revision is None or not readable_revision(item,request.user,revision):
                from django.http import Http404
                raise Http404("Private discussion evidence")
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
    link=_owned_link(link_id)
    _watch_readable(request,link.item,link.revision)
    _campaign_link_readable(request,link)
    return json_no_store(_checked(link))


@require_GET
@capability("business_read")
@never_cache
def evidence_download(request, link_id):
    link = _owned_link(link_id)
    _watch_readable(request,link.item,link.revision)
    _campaign_link_readable(request,link)
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
