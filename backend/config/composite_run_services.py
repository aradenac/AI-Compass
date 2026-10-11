"""PLAT-16: one immutable team result, never an individual AI Solution measurement.

Reuses PLAT-15 validation, PLAT-14 checkpoint/evidence and locked session semantics.
All component identities, revisions, role labels and settings come exclusively from
the session's original immutable campaign snapshot.
"""
import copy

from django.db import IntegrityError, transaction

from .catalog_ids import new_public_id
from .models import (BenchmarkRun, BenchmarkSession, CampaignParticipantPin,
                     CompositeBenchmarkRun, CompositeRunEvidence, CompositeRunParticipant)
from .run_services import _metrics
from .session_services import (InvalidSession, SessionAccessDenied, SessionConflict,
                               _allowed_evidence, _checkpoint, _save, can_edit)


def _members(session):
    identifiers=session.selected_participants
    if not session.campaign_snapshot.framework_id or not isinstance(identifiers,list) or len(identifiers)<2:
        raise SessionConflict("Composite runs require two or more selected Framework participants")
    if len(identifiers)!=len(set(identifiers)):
        raise InvalidSession("Duplicate participant identity in the original session")
    pins=CampaignParticipantPin.objects.select_related(
        "participant","model","provider","harness"
    ).filter(snapshot=session.campaign_snapshot,participant__public_id__in=identifiers)
    by_id={pin.participant.public_id:pin for pin in pins}
    if set(by_id)!=set(identifiers):
        raise InvalidSession("Selected participants no longer resolve to original pinned Framework snapshots")
    return [by_id[identifier] for identifier in identifiers]


def _snapshot(pin):
    return {
        "participant_id":pin.participant.public_id,
        "participant_revision_id":str(pin.pk),
        "role":pin.role,"label":pin.label,
        "position":pin.position,
        "configuration_version":pin.configuration_version,
        "settings":pin.settings,"properties":pin.properties,
        "component_ids":{kind:getattr(pin,kind).public_id
                         for kind in ("model","provider","harness")},
        "component_revision_ids":{kind:str(getattr(pin,kind+"_revision_id"))
                                  for kind in ("model","provider","harness")},
    }


def close(*,actor,public_id,expected_revision,data):
    if not isinstance(expected_revision,str):
        raise InvalidSession("expected_revision is required")
    with transaction.atomic():
        session=BenchmarkSession.objects.select_for_update(of=("self",)).select_related(
            "campaign_snapshot__revision__item","campaign_snapshot__owner",
            "campaign_snapshot__framework","case_pin__revision",
            "case_pin__test_case__item","method_definition","guide","guide_revision"
        ).filter(public_id=public_id).first()
        if session is None:raise InvalidSession("Unknown Server session")
        if not can_edit(actor,session):
            raise SessionAccessDenied("Only session creator or campaign owner can close this run")
        if (BenchmarkRun.objects.filter(session=session).exists() or
                CompositeBenchmarkRun.objects.filter(session=session).exists()):
            raise SessionConflict("Session already has a permanent Run")
        current=_checkpoint(session)
        if expected_revision!=f"r{current.number:03d}":
            raise SessionConflict("Session was changed elsewhere; reload before closing")
        if current.state.get("status")!="in_progress":
            raise SessionConflict("Paused and closed sessions cannot be closed")
        members=_members(session)
        if not current.state.get("interactions"):
            raise InvalidSession("At least one recorded interaction is required")
        state=copy.deepcopy(current.state)
        from .run_cost_services import quote, contract, InvalidMeter, MissingMeter
        prices=contract(session)
        results={**state.get("results_draft",{}),**data}
        cost_snapshot=None
        if prices is not None:
            if set(data)&{"cost_mode","cost_eur"}:
                raise InvalidSession("Collaborative tariff cost is computed, not manually assigned")
            try:cost_snapshot=quote(session,state.get("metering",{}))
            except MissingMeter as exc:
                raise SessionConflict("Composite Run remains pending with saved work: "+str(exc)) from exc
            except InvalidMeter as exc:
                raise SessionConflict("Original composite tariff is not computable: "+str(exc)) from exc
            totals=cost_snapshot["variable_reference_by_currency"]
            if not cost_snapshot["variable_charges"]:
                results.update(cost_mode="flat_rate",cost_eur=None)
            elif set(totals)=={"EUR"}:
                results.update(cost_mode="amount",cost_eur=float(totals["EUR"]))
            else:
                results.update(cost_mode="unknown",cost_eur=None)
        metrics=_metrics(results,state)
        if cost_snapshot is not None:
            metrics["reference_cost"]=cost_snapshot
        final_links=metrics.pop("evidence_link_ids")
        state["closing_evidence_link_ids"]=final_links
        evidence=_allowed_evidence(session,state)  # Verifies bytes and exact scopes.
        state["status"]="closed"
        state["result"]=copy.deepcopy(metrics)
        final=_save(session,actor,"closed",state,current.number+1)
        snapshots=[_snapshot(pin) for pin in members]
        snap=session.campaign_snapshot
        provenance={
            "scope":"composite",
            "evaluation_id":state.get("evaluation_id"),
            "execution_environment":state["setup"].get("environment",{}),
            "setup_deviations":state["setup"].get("notes",""),
            "campaign_id":snap.revision.item.public_id,
            "campaign_revision_id":str(session.campaign_snapshot_id),
            "campaign_mode":snap.revision.properties["mode"],
            "campaign_configuration":snap.configuration,
            "framework_id":snap.framework.public_id,
            "framework_revision_id":str(snap.framework_revision_id),
            "selected_participant_ids":session.selected_participants,
            "test_case_id":session.case_pin.test_case.item.public_id,
            "test_case_revision_id":str(session.case_pin.revision_id),
            "method_version":session.method_definition.version,
            "method_definition_id":str(session.method_definition_id),
            "method_descriptor":session.method_descriptor,
            "guide_id":session.guide.public_id if session.guide_id else None,
            "guide_revision_id":str(session.guide_revision_id) if session.guide_revision_id else None,
        }
        for _ in range(12):
            candidate=new_public_id("run")
            try:
                with transaction.atomic():
                    if BenchmarkRun.objects.filter(public_id=candidate).exists():
                        continue
                    run=CompositeBenchmarkRun.objects.create(
                        public_id=candidate,session=session,closing_checkpoint=final,
                        framework=snap.framework,framework_revision=snap.framework_revision,
                        outcome=metrics["outcome"],metrics=metrics,
                        result={"produced_outputs":metrics["produced_outputs"],
                                "notes":metrics["notes"],"extensions":metrics["extensions"]},
                        provenance=provenance,participant_snapshots=snapshots,
                        recorded_by=actor)
                    CompositeRunParticipant.objects.bulk_create([
                        CompositeRunParticipant(run=run,participant_pin=pin,position=n)
                        for n,pin in enumerate(members)
                    ])
                    CompositeRunEvidence.objects.bulk_create([
                        CompositeRunEvidence(run=run,evidence=link) for link in evidence
                    ])
                    return run
            except IntegrityError:
                if (CompositeBenchmarkRun.objects.filter(public_id=candidate).exists() or
                        BenchmarkRun.objects.filter(public_id=candidate).exists()):
                    continue
                raise
    raise InvalidSession("Failed to allocate permanent Composite Run identity")


def serialize(run,include_raw=True):
    cp=run.closing_checkpoint
    roles={p["participant_id"]:p["label"]+" · "+p["role"]
           for p in run.participant_snapshots}
    result={
        "id":run.public_id,"uuid":str(run.pk),"kind":"composite",
        "scope":"framework_workflow",
        "solution_id":None,"solution_revision_id":None,
        "session_id":run.session.public_id,
        "closing_checkpoint":f"r{cp.number:03d}",
        "framework_id":run.framework.public_id,
        "framework_revision_id":str(run.framework_revision_id),
        "participants":run.participant_snapshots,
        "outcome":run.outcome,"metrics":run.metrics,
        "result":run.result,"provenance":run.provenance,
        "evidence":[{
            "id":str(pin.evidence_id),"sha256":pin.evidence.blob_id,
            "filename":pin.evidence.original_filename,
            "download":"/api/v1/evidence/"+str(pin.evidence_id)+"/download",
        } for pin in run.evidence_pins.select_related("evidence").order_by("evidence_id")],
        "recorded_by":run.recorded_by.get_username(),
        "created_at":run.created_at.isoformat(),
    }
    if include_raw:
        # Labels are a read-only projection: raw checkpoint/interactions remain immutable.
        result["raw_session_state"]=cp.state
        result["interaction_actor_labels"]=[
            {"interaction_id":row["id"],"participant_id":row.get("participant_id"),
             "actor_label":roles.get(row.get("participant_id"),"Coordinator / unspecified")}
            for row in cp.state["interactions"]
        ]
    return result
