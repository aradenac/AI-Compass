"""PLAT-14: scoped and CSRF-protected resumable benchmark draft APIs."""
import json

from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .auth_views import capability, json_no_store
from .evidence_store import BrokenEvidence, EvidenceError
from .models import BenchmarkSession, CatalogItem, SessionCheckpoint
from .session_services import (
    InvalidSession, SessionAccessDenied, SessionConflict,
    append, create, serialize,
)


def _payload(request, allowed):
    if len(request.body)>512*1024:
        raise InvalidSession("Request exceeds 512 KiB")
    try:
        data=json.loads(request.body)
    except (ValueError,UnicodeDecodeError) as exc:
        raise InvalidSession("Request must contain JSON") from exc
    if not isinstance(data,dict) or set(data)-allowed:
        raise InvalidSession("Unsupported JSON fields")
    return data


def _fail(exc):
    if isinstance(exc,SessionAccessDenied):
        return json_no_store({"error":"permission_denied","detail":str(exc)},403)
    if isinstance(exc,SessionConflict):
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    if isinstance(exc,(EvidenceError,BrokenEvidence)):
        return json_no_store({"error":"evidence_unavailable","detail":str(exc)},409)
    return json_no_store({"error":"invalid_session","detail":str(exc)},400)


def _run(fn):
    try: return fn()
    except (InvalidSession,SessionAccessDenied,SessionConflict,EvidenceError) as exc:
        return _fail(exc)


def _require_private_review(request):
    from .publication_services import can_preview
    if not can_preview(request.user):
        raise Http404("Private experiment session")


def _item(campaign_id):
    if not campaign_id.startswith("cmp-"):raise Http404("Unknown campaign")
    return get_object_or_404(CatalogItem,public_id=campaign_id,type_slug="campaign")


def _session(public_id):
    if not public_id.startswith("ses-"):raise Http404("Unknown session")
    return get_object_or_404(
        BenchmarkSession.objects.select_related(
            "campaign_snapshot__revision__item","campaign_snapshot__owner",
            "case_pin__test_case__item","method_definition","guide","created_by"),
        public_id=public_id)


@require_GET
@never_cache
@capability("business_read")
def list_sessions(request,campaign_id):
    _require_private_review(request)
    campaign=_item(campaign_id)
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    rows=list(BenchmarkSession.objects.select_related(
        "campaign_snapshot__revision__item","campaign_snapshot__owner",
        "case_pin__test_case__item","method_definition","guide","created_by"
    ).filter(campaign_snapshot__revision__item=campaign).order_by("-created_at","-id")[:501])
    if len(rows)>500:return json_no_store({"error":"too_many_sessions"},422)
    return json_no_store({"results":[serialize(s,include_state=False) for s in rows]})


@require_POST
@csrf_protect
@never_cache
@capability("business_write")
def add_session(request,campaign_id):
    _item(campaign_id)
    def run():
        session=create(actor=request.user,campaign_id=campaign_id,data=_payload(request,{
            "test_case_id","guide_id","selected_participant_ids","evaluation_id",
            "component_ids","settings","properties","configuration_version",
            "pricing_selections"}))
        response=json_no_store(serialize(session),201)
        response["Location"]="/api/v1/sessions/"+session.public_id
        return response
    return _run(run)


@require_GET
@never_cache
@capability("business_read")
def get_session(request,public_id):
    _require_private_review(request)
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    return json_no_store(serialize(_session(public_id)))


@require_GET
@never_cache
@capability("business_read")
def get_pinned_guide(request,public_id):
    _require_private_review(request)
    if request.GET:
        return json_no_store({"error":"invalid_filter"},400)
    from .setup_recipe_services import from_session
    from .setup_composition import SetupCompositionError
    try:
        return json_no_store(from_session(_session(public_id)))
    except SetupCompositionError as exc:
        return json_no_store({"error":"invalid_pinned_recipe","detail":str(exc)},409)


@require_GET
@never_cache
@capability("business_read")
def get_checkpoints(request,public_id):
    _require_private_review(request)
    session=_session(public_id)
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    checkpoints=SessionCheckpoint.objects.filter(session=session).order_by("number")
    # Bound history page; immutable full revisions accessible individually.
    if checkpoints.count()>1000:return json_no_store({"error":"history_too_large"},422)
    return json_no_store({"id":session.public_id,"checkpoints":[{
        "revision":f"r{cp.number:03d}","action":cp.action,
        "saved_at":cp.saved_at.isoformat(),"actor":cp.actor.get_username(),
    } for cp in checkpoints.select_related("actor")]})


@require_GET
@never_cache
@capability("business_read")
def get_checkpoint(request,public_id,number):
    _require_private_review(request)
    session=_session(public_id)
    cp=get_object_or_404(SessionCheckpoint,session=session,number=number)
    return json_no_store(serialize(session,cp))


def _change(request,public_id,action,allowed,step_key=None):
    _session(public_id)
    def run():
        payload=_payload(request,allowed|{"expected_revision"})
        expected=payload.pop("expected_revision",None)
        session=append(actor=request.user,public_id=public_id,
                       expected_revision=expected,action=action,data=payload,
                       step_key=step_key)
        return json_no_store(serialize(session))
    return _run(run)


@require_http_methods(["PATCH"])
@csrf_protect
@never_cache
@capability("business_write")
def update_setup(request,public_id):
    return _change(request,public_id,"setup",{
        "started_at","installation_duration_minutes","environment",
        "notes","extensions","evidence_link_ids"})


@require_http_methods(["PATCH"])
@csrf_protect
@never_cache
@capability("business_write")
def update_step(request,public_id,step_key):
    return _change(request,public_id,"step",{
        "status","values","notes","duration_minutes","extensions",
        "evidence_link_ids","schema_version","current_step"},step_key=step_key)


@require_http_methods(["PATCH"])
@csrf_protect
@never_cache
@capability("business_write")
def update_metering(request,public_id):
    return _change(request,public_id,"metering",{"consumption"})


@require_http_methods(["PATCH"])
@csrf_protect
@never_cache
@capability("business_write")
def update_results(request,public_id):
    return _change(request,public_id,"results",{
        "outcome","quality_score","quality_evaluation","information_utility_score",
        "information_utility_evaluation","tokens_count","tokens_multiplier",
        "cost_mode","cost_eur","human_review_minutes","human_correction_minutes",
        "produced_outputs","notes","extensions","evidence_link_ids"})


@require_POST
@csrf_protect
@never_cache
@capability("business_write")
def add_interaction(request,public_id):
    return _change(request,public_id,"interaction",{
        "type","content","occurred_at","human_minutes","agent_minutes",
        "participant_id","notes","extensions","evidence_link_ids",
        "schema_version"})


@require_POST
@csrf_protect
@never_cache
@capability("business_write")
def lifecycle(request,public_id,action):
    if action not in ("pause","resume"):
        return json_no_store({"error":"invalid_action"},400)
    return _change(request,public_id,action,set())


def collection(request,campaign_id):
    if request.method=="GET":return list_sessions(request,campaign_id)
    if request.method=="POST":return add_session(request,campaign_id)
    return HttpResponseNotAllowed(["GET","POST"])
