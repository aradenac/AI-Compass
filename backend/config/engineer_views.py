"""Engineer-specific public projection and contextual discussion actions.

Business-read is a read capability, not a grant to private planning records.
Published source selection, discussion thread permissions, and CSRF remain in
their owning services.
"""
from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .auth_views import capability, json_no_store, read_json
from . import engineer_services as svc
from . import discussion_services as discussions


@require_GET
@never_cache
@capability("business_read")
def workspace(request):
    if set(request.GET)-{"view","all_tasks"}:
        return json_no_store({"error":"invalid_filter"},400)
    if request.GET.get("all_tasks", "false") not in ("true","false"):
        return json_no_store({"error":"invalid_filter"},400)
    try:
        return json_no_store(svc.workspace(
            request.user, view=request.GET.get("view","task"),
            all_tasks=request.GET.get("all_tasks")=="true"))
    except svc.InvalidWorkspace as exc:
        return json_no_store({"error":"invalid_workspace","detail":str(exc)},422)


@require_GET
@never_cache
@capability("business_read")
def solution(request, public_id):
    if set(request.GET)-{"task_id"}:
        return json_no_store({"error":"invalid_filter"},400)
    try:
        record=svc.detail(request.user,public_id,task_id=request.GET.get("task_id"))
    except svc.InvalidWorkspace as exc:
        return json_no_store({"error":"invalid_solution","detail":str(exc)},400)
    if record is None:
        raise Http404("No active published Solution evidence for this Task")
    return json_no_store(record)


@require_POST
@never_cache
@csrf_protect
@capability("business_read")
def feedback(request):
    """Write an ordinary chronological public discussion, never an access grant."""
    data=read_json(request)
    if not isinstance(data,dict) or set(data)!={"kind","context_id","body"}:
        return json_no_store({"error":"invalid_feedback"},400)
    kind=data.get("kind")
    context=data.get("context_id")
    body=data.get("body")
    if kind not in ("feedback","request","idea") or not isinstance(context,str):
        return json_no_store({"error":"invalid_feedback"},400)
    if kind == "feedback" and not context.startswith("sol-"):
        return json_no_store({"error":"invalid_feedback_context"},400)
    if kind == "idea" and not context.startswith("tsk-"):
        return json_no_store({"error":"invalid_feedback_context"},400)
    if kind == "request" and not context.startswith(("tsk-","sol-")):
        return json_no_store({"error":"invalid_feedback_context"},400)
    if kind == "feedback" and isinstance(body,str):
        body = "Self-reported tool experience (entitlement not independently verified): " + body
    if kind == "request" and isinstance(body,str):
        body = "Access interest only; no entitlement, approval or provisioning implied: " + body
    try:
        row,first=discussions.create_thread(request.user,{
            "title":{"feedback":"Tool usage feedback", "request":"Access interest",
                     "idea":"Engineering need or technology idea"}[kind],
            "context_id":context,"body":body,"visibility":"public",
            "properties":{"kind":kind,"scope":"public"}})
        return json_no_store({
            "id":row.item.public_id,"context_id":context,
            "status":"discussion_recorded_not_a_ticket",
            "entitlement_granted":False,
            "message_id":first.item.public_id,
            "discussion_url":"/api/v1/discussions/"+row.item.public_id},201)
    except (discussions.InvalidDiscussion, ValueError, TypeError) as exc:
        return json_no_store({"error":"invalid_feedback","detail":str(exc)},400)
