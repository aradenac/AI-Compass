"""PLAT-15: close one controlled individual session into immutable, auditable evidence."""
import copy
import hashlib
import json
import math

from django.db import IntegrityError, transaction

from .activity_services import record_catalog_event
from .catalog_ids import new_public_id
from .evidence_store import verify_bytes
from .models import (BenchmarkRun, BenchmarkRunEvidence, BenchmarkSession,
                     CatalogItem, CatalogRevision, MeasuredSolution,
                     ObjectTypeVersion, SessionCheckpoint, SessionSolutionPin)
from .session_services import (InvalidSession, SessionAccessDenied, SessionConflict,
                               _allowed_evidence, _checkpoint, _minutes, _save, can_edit)

KINDS=("model","provider","harness")
OUTCOMES=("accepted","failed")
COST_MODES=("amount","flat_rate","unknown")


def _score(value,field):
    if value is None:return None
    if type(value) not in (int,float) or not math.isfinite(value) or value<0 or value>100:
        raise InvalidSession(field+" must be a 0–100 number or null")
    return value


def _text(value,field,maxlength=20000,required=False):
    if not isinstance(value,str) or len(value)>maxlength or (required and not value.strip()):
        raise InvalidSession(field+" must be a valid nonempty text field" if required else field+" must be text")
    return value


def _dict(value,field):
    if not isinstance(value,dict) or len(json.dumps(value,ensure_ascii=False,allow_nan=False))>65536:
        raise InvalidSession(field+" must be a bounded JSON object")
    return value


def _metrics(data,state):
    if set(data)-{
        "outcome","quality_score","quality_evaluation","information_utility_score",
        "information_utility_evaluation","tokens_count","tokens_multiplier",
        "cost_mode","cost_eur","human_review_minutes","human_correction_minutes",
        "produced_outputs","notes","extensions","evidence_link_ids",
    }:
        raise InvalidSession("Unsupported run close fields")
    outcome=data.get("outcome")
    if outcome not in OUTCOMES:
        raise InvalidSession("DoD outcome must be accepted or failed")
    outputs=_text(data.get("produced_outputs"),"produced_outputs",20000,required=True)
    count=data.get("tokens_count")
    multiplier=data.get("tokens_multiplier",1)
    if count is not None and (type(count) is not int or count<0 or count>10**12):
        raise InvalidSession("Token count must be a nonnegative integer or null")
    if type(multiplier) is not int or multiplier not in (1,10,100,1000,1000000):
        raise InvalidSession("Unsupported token multiplier")
    if count is None and multiplier!=1:
        raise InvalidSession("Unknown tokens cannot carry a multiplier")
    if count is not None and count*multiplier>10**12:
        raise InvalidSession("Token total exceeds limit")
    mode=data.get("cost_mode","unknown")
    if mode not in COST_MODES:
        raise InvalidSession("Cost must be amount, flat_rate or unknown")
    amount=data.get("cost_eur")
    if mode=="amount":
        if type(amount) not in (int,float) or not math.isfinite(amount) or amount<0 or amount>10**9:
            raise InvalidSession("Amount cost must be a finite nonnegative EUR number")
    elif amount is not None:
        raise InvalidSession("Flat-rate or unknown cost cannot be represented by zero EUR")
    review=_minutes(data.get("human_review_minutes"),"human_review_minutes")
    correction=_minutes(data.get("human_correction_minutes"),"human_correction_minutes")
    quality=_score(data.get("quality_score"),"quality_score")
    utility=_score(data.get("information_utility_score"),"information_utility_score")
    quality_text=_text(data.get("quality_evaluation",""),"quality_evaluation")
    utility_text=_text(data.get("information_utility_evaluation",""),"information_utility_evaluation")
    notes=_text(data.get("notes",""),"notes")
    extensions=_dict(data.get("extensions",{}),"extensions")
    eids=data.get("evidence_link_ids",[])
    if not isinstance(eids,list):
        raise InvalidSession("Evidence references must be a list")
    measured=state["measurements"]
    installation=state["setup"]["installation_duration_minutes"]
    interactions_human=measured["human_total_minutes"]
    if None in (installation,interactions_human,review,correction):
        human_total=None
    else:
        human_total=installation+interactions_human+review+correction
    return {
        "outcome":outcome,"quality_score":quality,
        "quality_evaluation":quality_text,"information_utility_score":utility,
        "information_utility_evaluation":utility_text,
        "tokens_count":count,"tokens_multiplier":multiplier,
        "tokens_total":count*multiplier if count is not None else None,
        "cost_mode":mode,"cost_eur":amount,
        "installation_minutes":installation,
        "interaction_human_minutes":interactions_human,
        "interaction_agent_minutes":measured["agent_total_minutes"],
        "human_review_minutes":review,"human_correction_minutes":correction,
        "human_total_minutes":human_total,
        "produced_outputs":outputs,"notes":notes,"extensions":extensions,
        "evidence_link_ids":eids,
    }


def _fingerprint(pin):
    fingerprint={
        "components":{k:{
            "id":str(getattr(pin,k+"_id")),
            "revision":str(getattr(pin,k+"_revision_id")),
        } for k in KINDS},
        "configuration_version":pin.configuration_version,
        "settings":pin.settings,"properties":pin.properties,
    }
    canonical=json.dumps(fingerprint,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(),fingerprint


def _solution(actor,pin):
    digest,configuration=_fingerprint(pin)
    existing=MeasuredSolution.objects.select_related("item__current_revision").filter(fingerprint=digest).first()
    if existing is not None:return existing
    schema=ObjectTypeVersion.objects.get(type_slug="ai_solution",version=1)
    for _ in range(12):
        public_id=new_public_id("sol")
        try:
            # A savepoint isolates the fingerprint/HRID uniqueness race and
            # rolls back the complete candidate CatalogItem + revision together.
            with transaction.atomic():
                item=CatalogItem.objects.create(public_id=public_id,type_slug="ai_solution")
                rev=CatalogRevision.objects.create(
                    item=item,number=1,schema_version=schema,
                    display_name="Measured AI Solution "+public_id,
                    properties={"fingerprint":digest,"lifecycle":"draft","setup":configuration},
                    created_by=actor)
                item.current_revision=rev
                item.save(update_fields=["current_revision"])
                row=MeasuredSolution.objects.create(item=item,fingerprint=digest)
                record_catalog_event(item=item,revision=rev,actor=actor,action="first_measured_run")
                return row
        except IntegrityError:
            existing=MeasuredSolution.objects.select_related("item__current_revision").filter(
                fingerprint=digest).first()
            if existing is not None:return existing
            if CatalogItem.objects.filter(public_id=public_id).exists():
                continue
            raise
    raise InvalidSession("Could not reserve a unique measured AI Solution ID")


def close(*,actor,public_id,expected_revision,data):
    if not isinstance(expected_revision,str):
        raise InvalidSession("expected_revision is required")
    with transaction.atomic():
        session=BenchmarkSession.objects.select_for_update().select_related(
            "campaign_snapshot__revision__item","campaign_snapshot__owner",
            "case_pin__revision","case_pin__test_case__item",
            "method_definition","guide_revision","guide").filter(public_id=public_id).first()
        if session is None:raise InvalidSession("Unknown real Server session")
        if not can_edit(actor,session):
            raise SessionAccessDenied("Only draft creator or campaign owner can close it")
        if BenchmarkRun.objects.filter(session=session).exists():
            raise SessionConflict("This session already has a permanent run")
        current=_checkpoint(session)
        if expected_revision!=f"r{current.number:03d}":
            raise SessionConflict("Draft changed in another browser; reload first")
        if current.state.get("status")!="in_progress":
            raise SessionConflict("A paused/closed session cannot be closed as a run")
        # Drafts selecting multiple Framework participants remain for PLAT-16.
        if len(session.selected_participants)>1:
            raise SessionConflict("Collaborative Framework runs require PLAT-16")
        pin=SessionSolutionPin.objects.select_related(
            "model","provider","harness").filter(session=session).first()
        if pin is None:
            raise SessionConflict("This draft has no version-pinned individual trio; create a new session with a defined setup")
        state=copy.deepcopy(current.state)
        if not state["interactions"]:
            raise InvalidSession("At least one recorded interaction is required before closing")
        metrics=_metrics(data,state)
        evidence_ids=metrics.pop("evidence_link_ids")
        state["closing_evidence_link_ids"]=evidence_ids
        evidence=_allowed_evidence(session,state)
        for link in evidence:
            verify_bytes(link.blob_id,size=link.blob.size)
        solution=_solution(actor,pin)
        solution_revision=solution.item.current_revision
        state["status"]="closed"
        state["result"]=copy.deepcopy(metrics)
        final=_save(session,actor,"closed",state,current.number+1)
        provenance={
            "campaign_id":session.campaign_snapshot.revision.item.public_id,
            "campaign_revision_id":str(session.campaign_snapshot_id),
            "campaign_mode":session.campaign_snapshot.revision.properties["mode"],
            "campaign_configuration":session.campaign_snapshot.configuration,
            "framework_id":session.campaign_snapshot.framework.public_id if session.campaign_snapshot.framework_id else None,
            "framework_revision_id":str(session.campaign_snapshot.framework_revision_id)
                if session.campaign_snapshot.framework_revision_id else None,
            "selected_participant_ids":session.selected_participants,
            "test_case_id":session.case_pin.test_case.item.public_id,
            "test_case_revision_id":str(session.case_pin.revision_id),
            "method_version":session.method_definition.version,
            "method_definition_id":str(session.method_definition_id),
            "method_descriptor":session.method_descriptor,
            "guide_id":session.guide.public_id if session.guide_id else None,
            "guide_revision_id":str(session.guide_revision_id) if session.guide_revision_id else None,
            "setup_fingerprint":solution.fingerprint,
            "configuration":_fingerprint(pin)[1],
        }
        for _ in range(12):
            candidate=new_public_id("run")
            try:
                with transaction.atomic():
                    run=BenchmarkRun.objects.create(
                        public_id=candidate,session=session,closing_checkpoint=final,
                        solution=solution,solution_revision=solution_revision,
                        outcome=metrics["outcome"],metrics=metrics,
                        result={"produced_outputs":metrics["produced_outputs"],
                                "notes":metrics["notes"],"extensions":metrics["extensions"]},
                        provenance=provenance,recorded_by=actor)
                    BenchmarkRunEvidence.objects.bulk_create([
                        BenchmarkRunEvidence(run=run,evidence=link) for link in evidence])
                    return run
            except IntegrityError:
                if BenchmarkRun.objects.filter(public_id=candidate).exists():
                    continue
                raise
    raise InvalidSession("Could not reserve a unique permanent Run ID")


def serialize(run,include_raw=True):
    session=run.session
    solution=run.solution
    cp=run.closing_checkpoint
    evidence=[{
        "id":str(p.evidence_id),"sha256":p.evidence.blob_id,
        "filename":p.evidence.original_filename,
        "download":"/api/v1/evidence/"+str(p.evidence_id)+"/download",
    } for p in run.evidence_pins.select_related("evidence").order_by("evidence_id")]
    result={
        "id":run.public_id,"uuid":str(run.pk),
        "session_id":session.public_id,
        "closing_checkpoint":f"r{cp.number:03d}",
        "solution_id":solution.item.public_id,
        "solution_revision_id":str(run.solution_revision_id),
        "solution_lifecycle":run.solution_revision.properties.get("lifecycle","draft"),
        "outcome":run.outcome,"metrics":run.metrics,
        "result":run.result,"provenance":run.provenance,
        "evidence":evidence,
        "recorded_by":run.recorded_by.get_username(),
        "created_at":run.created_at.isoformat(),
    }
    if include_raw:
        result["raw_session_state"]=cp.state
    return result
