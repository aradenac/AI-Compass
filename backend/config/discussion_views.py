"""PLAT-23: real authenticated feedback/discussions (read, create, reply, correct, files)."""
import json

from django.conf import settings
from django.http import Http404,HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET,require_POST

from .auth_views import capability,json_no_store
from .catalog_views import read_payload
from .catalog_schemas import InvalidModel
from .catalog_services import RevisionConflict, SchemaWriteBlocked,ExhaustedIds
from .evidence_store import EvidenceError,BrokenEvidence,attach,serialize as evidence_serialize,verify_bytes
from .models import CatalogRevision,DiscussionThread,DiscussionMessage
from . import discussion_services as svc


def error(exc):
    if isinstance(exc,RevisionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    if isinstance(exc,SchemaWriteBlocked):
        return json_no_store({"error":"schema_write_blocked","detail":str(exc)},409)
    if isinstance(exc,ExhaustedIds):
        return json_no_store({"error":"id_exhausted"},503)
    return json_no_store({"error":"invalid_discussion","detail":str(exc)},400)


def thread_for(request,public_id):
    try:
        thread=svc._thread(public_id)
    except svc.InvalidDiscussion as exc:raise Http404(str(exc)) from exc
    if not svc._thread_visible(thread,request.user):
        raise Http404("Internal discussion")
    return thread


def message_for(request,public_id,revision=None):
    try:message=svc._message(public_id)
    except svc.InvalidDiscussion as exc:raise Http404(str(exc)) from exc
    if not svc._message_visible(message,request.user,revision):
        raise Http404("Internal message")
    return message


@csrf_protect
@capability("business_read")
@never_cache
def threads(request):
    if request.method=="GET":
        if request.GET:return json_no_store({"error":"invalid_filter"},400)
        try:return json_no_store({"results":svc.list_threads(request.user)})
        except svc.InvalidDiscussion as exc:return error(exc)
    if request.method!="POST":return HttpResponseNotAllowed(["GET","POST"])
    try:
        thread,initial=svc.create_thread(request.user,read_payload(request))
        return json_no_store({
            "thread":svc.thread_record(thread,request.user),
            "message":svc.message_record(initial,request.user),
        },201)
    except (svc.InvalidDiscussion,InvalidModel,ExhaustedIds,ValueError,TypeError) as exc:
        return error(exc)


@csrf_protect
@capability("business_read")
@never_cache
def thread_detail(request,public_id):
    thread=thread_for(request,public_id)
    if request.method!="GET":return HttpResponseNotAllowed(["GET"])
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    try:
        return json_no_store({"thread":svc.thread_record(thread,request.user),
                              "messages":svc.list_messages(thread,request.user)})
    except svc.InvalidDiscussion as exc:return error(exc)


@require_POST
@csrf_protect
@capability("business_read")
@never_cache
def reply(request,public_id):
    thread=thread_for(request,public_id)
    try:
        msg=svc.create_message(request.user,thread,read_payload(request))
        return json_no_store(svc.message_record(msg,request.user),201)
    except (svc.InvalidDiscussion,InvalidModel,ExhaustedIds,TypeError,ValueError) as exc:return error(exc)


@csrf_protect
@capability("business_read")
@never_cache
def message_detail(request,public_id):
    msg=message_for(request,public_id)
    if request.method=="GET":
        if request.GET:return json_no_store({"error":"invalid_filter"},400)
        return json_no_store(svc.message_record(msg,request.user))
    if request.method!="PATCH":return HttpResponseNotAllowed(["GET","PATCH"])
    try:
        data=read_payload(request)
        if set(data)!={"expected_revision","properties"}:
            raise svc.InvalidDiscussion("Message correction requires expected_revision and properties")
        revised=svc.revise_message(request.user,public_id,data["expected_revision"],data["properties"])
        return json_no_store(svc.message_record(revised,request.user))
    except (svc.InvalidDiscussion,InvalidModel,RevisionConflict,
            SchemaWriteBlocked,ValueError,TypeError) as exc:return error(exc)


@require_GET
@capability("business_read")
@never_cache
def message_history(request,public_id):
    msg=message_for(request,public_id)
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    rows=CatalogRevision.objects.filter(item=msg.item).select_related("created_by").order_by("number")
    return json_no_store({"id":msg.item.public_id,"revisions":[item for item in (
        svc.message_record(msg,request.user,rev=revision) for revision in rows) if item is not None]})


@require_GET
@capability("business_read")
@never_cache
def message_version(request,public_id,number):
    msg=message_for(request,public_id)
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    rev=get_object_or_404(CatalogRevision.objects.select_related("created_by"),
                          item=msg.item,number=number)
    if not svc._message_visible(msg,request.user,rev):
        raise Http404("Internal version")
    return json_no_store(svc.message_record(msg,request.user,rev=rev))


@require_POST
@csrf_protect
@capability("business_read")
@never_cache
def attachment(request,public_id):
    """Ordinary engineer may attach original bytes ONLY to their own latest message.
    Shared evidence store and hash verification remain the sole source of truth.
    """
    msg=message_for(request,public_id)
    rev=msg.item.current_revision
    if not svc._message_visible(msg,request.user):
        raise Http404("Internal message")
    if not svc.privileged(request.user) and (
        msg.item.revisions.order_by("number").first().created_by_id!=request.user.pk):
        return json_no_store({"error":"permission_denied"},403)
    try:
        length=request.META.get("CONTENT_LENGTH","")
        if length and int(length)>settings.EVIDENCE_MAX_BYTES+512*1024:
            raise EvidenceError("Attachment request too large")
        if not request.content_type.startswith("multipart/form-data"):
            raise EvidenceError("Only multipart/form-data is accepted")
        if set(request.FILES)!={"file"} or len(request.FILES.getlist("file"))!=1:
            raise EvidenceError("Exactly one original file required")
        upload=request.FILES["file"]
        if upload.size<1 or upload.size>settings.EVIDENCE_MAX_BYTES:
            raise EvidenceError("Attachment must be 1 byte to 16 MiB")
        requested=request.POST.get("expected_revision")
        if requested!=f"r{rev.number:03d}":
            raise RevisionConflict("Message version changed; reload before attaching")
        # An author must not be allowed to upload a file to an internal revision.
        if not svc._message_visible(msg,request.user,rev):
            raise EvidenceError("Internal attachment access denied")
        source=request.POST.get("source","feedback")
        if not isinstance(source,str) or len(source)>600:raise EvidenceError("Invalid source")
        link=attach(item=msg.item,revision=rev,file=upload,actor=request.user,
                    source=source,provenance={"thread_id":msg.thread.item.public_id,
                                              "message_id":msg.item.public_id,
                                              "visibility":rev.properties["visibility"]})
        verify_bytes(link.blob_id,size=link.blob.size)
        result=json_no_store(evidence_serialize(link),201)
        result["Location"]="/api/v1/evidence/"+str(link.pk)
        return result
    except (EvidenceError,BrokenEvidence,ValueError,TypeError) as exc:return error(exc)
    except RevisionConflict as exc:return error(exc)
