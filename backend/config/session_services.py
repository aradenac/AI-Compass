"""PLAT-14: transactional, append-only resumable sessions for real Server campaigns.

A session is bound to one immutable campaign snapshot, Test Case revision,
method definition/descriptor and optional guide revision. Each accepted action
adds a complete immutable checkpoint; no draft writes or artifacts are lost on
a browser change and unknown JSON fields are never coerced into measurements.
"""
import copy
import json
from datetime import datetime, timezone as datetime_timezone
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from .catalog_ids import new_public_id, uuid7
from .evidence_store import verify_bytes
from .models import (BenchmarkSession, CampaignSnapshot, CatalogItem,
                     EvidenceLink, SessionCheckpoint, SessionCheckpointEvidence, SessionPricingPin)

MAX_BYTES = 1024 * 1024
MAX_INTERACTIONS = 500
MAX_EVIDENCE = 128


class InvalidSession(ValueError):
    pass


class SessionConflict(Exception):
    pass


class SessionAccessDenied(Exception):
    pass


def _bounded_object(value, label, max_chars=65536):
    if not isinstance(value, dict) or len(json.dumps(value, ensure_ascii=False)) > max_chars:
        raise InvalidSession(label + " must be a bounded JSON object")
    return value


def _text(value, field, limit=20000, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise InvalidSession(field + " must be a valid string")
    return value


def _minutes(value, name):
    if value is not None and (type(value) not in (int, float) or
                               not 0 <= value <= 10080):
        raise InvalidSession(name + " must be a positive minute count or null")
    return value


def _timestamp(value, name):
    if value is None: return None
    if not isinstance(value,str) or len(value)>50:
        raise InvalidSession(name + " must be an ISO8601 date with timezone")
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise InvalidSession(name + " must be an ISO8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidSession(name + " requires an explicit timezone")
    return parsed.astimezone(datetime_timezone.utc).isoformat()


def _checkpoint(session):
    return session.checkpoints.order_by("-number").first()


def _descriptors(session):
    schema=session.method_descriptor
    if not isinstance(schema,dict) or not isinstance(schema.get("steps"),list):
        raise InvalidSession("Session's original experimental method descriptor is invalid")
    steps=schema["steps"]
    keys=[s.get("key") for s in steps if isinstance(s,dict)]
    if len(keys)!=len(steps) or len(set(keys))!=len(keys) or any(
            not isinstance(k,str) or not k or len(k)>64 for k in keys):
        raise InvalidSession("Original method step identifiers are inconsistent")
    return steps


def _allowed_evidence(session, state):
    ids=[]
    def append(refs):
        if not isinstance(refs,list) or len(refs)>MAX_EVIDENCE:
            raise InvalidSession("Evidence references must be a bounded list")
        for ref in refs:
            if not isinstance(ref,str) or len(ref)>50:
                raise InvalidSession("Invalid evidence link identifier")
            try:
                UUID(ref)
            except (ValueError,AttributeError) as exc:
                raise InvalidSession("Invalid evidence link identifier") from exc
            ids.append(ref)
    append(state["setup"].get("evidence_link_ids",[]))
    append(state.get("closing_evidence_link_ids",[]))
    # Pending results must pin original uploaded artifacts before metering is
    # complete, exactly as permanent close evidence does.
    append(state.get("results_draft",{}).get("evidence_link_ids",[]))
    for row in state["steps"].values():
        append(row.get("evidence_link_ids",[]))
    for row in state["interactions"]:
        append(row.get("evidence_link_ids",[]))
    ids=list(dict.fromkeys(ids))
    if len(ids)>MAX_EVIDENCE:
        raise InvalidSession("Maximum 128 distinct evidence links per session checkpoint")
    campaign_id=session.campaign_snapshot.revision.item_id
    testcase_id=session.case_pin.test_case.item_id
    links=list(EvidenceLink.objects.select_related("blob").filter(
        pk__in=ids,item_id__in=(campaign_id,testcase_id)))
    if len(links)!=len(ids):
        raise InvalidSession("Evidence link must exist on the pinned campaign or Test Case")
    for link in links:
        # A broken/corrupted file is never blessed as a valid draft attachment.
        verify_bytes(link.blob_id,size=link.blob.size)
    return links


def _save(session, actor, action, state, number):
    encoded=json.dumps(state, ensure_ascii=False,allow_nan=False)
    if len(encoded)>MAX_BYTES:
        raise InvalidSession("Session state exceeds 1 MiB")
    evidence=_allowed_evidence(session,state)
    checkpoint=SessionCheckpoint.objects.create(
        session=session,number=number,action=action,state=state,actor=actor)
    SessionCheckpointEvidence.objects.bulk_create([
        SessionCheckpointEvidence(checkpoint=checkpoint,evidence=link)
        for link in evidence])
    return checkpoint


def _initial_state(session, evaluation_id=None):
    steps=_descriptors(session)
    state={
        "status":"in_progress",
        "setup":{"started_at":None,"installation_duration_minutes":None,
                 "environment":{},"notes":"","extensions":{},"evidence_link_ids":[]},
        "steps":{s["key"]:{"status":"pending","values":{},"notes":"",
                           "duration_minutes":None,"extensions":{},
                           "schema_version":str(session.method_definition.version),
                           "evidence_link_ids":[]} for s in steps},
        "current_step":steps[0]["key"] if steps else None,
        "interactions":[],
        "measurements":{"human_total_minutes":None,"agent_total_minutes":None}
    }
    if evaluation_id is not None:
        state["evaluation_id"]=evaluation_id
    return state


def can_edit(actor,session):
    """One experimenter owns one active Run/session (UX-R05 §10.1).

    Only the account that created the session may append checkpoints or close it
    into a Run. Authorized co-workers keep read access and may create *separate*
    sessions for the same campaign, but can never concurrently write someone
    else's active experiment. The campaign owner is therefore no longer an
    implicit co-writer; a superuser retains the existing operational override.
    """
    return bool(actor.is_superuser or actor.pk == session.created_by_id)


def create(*, actor, campaign_id, data):
    if set(data)-{"test_case_id","guide_id","selected_participant_ids","evaluation_id",
                  "component_ids","settings","properties","configuration_version",
                  "pricing_selections"}:
        raise InvalidSession("Unsupported session creation fields")
    item=CatalogItem.objects.select_related("current_revision").filter(
        type_slug="campaign",public_id=campaign_id).first()
    if item is None or not item.current_revision_id:
        raise InvalidSession("Unknown Server campaign")
    snapshot=CampaignSnapshot.objects.select_related(
        "revision","method_definition","owner","guide","guide_revision"
    ).get(revision=item.current_revision)
    if snapshot.revision.properties.get("archived") or snapshot.revision.properties.get("status")!="in_progress":
        raise SessionConflict("Start the campaign before creating a Test Case session")
    if not (actor.is_superuser or snapshot.owner_id==actor.pk):
        # Contributors can work with sessions for other owners but cannot
        # change another person's draft; session remains owned by creator.
        if not actor.has_perm("auth.business_write"):
            raise SessionAccessDenied("Only a contributor can start a session")
    case=snapshot.case_pins.select_related("test_case__item").filter(
        test_case__item__public_id=data.get("test_case_id")).first()
    if case is None:
        raise InvalidSession("Test Case must be selected in the pinned campaign revision")
    guide_id=data.get("guide_id",snapshot.guide.public_id if snapshot.guide_id else None)
    if guide_id in (None,""):
        guide,guide_revision=None,None
    elif guide_id==(snapshot.guide.public_id if snapshot.guide_id else None):
        guide,guide_revision=snapshot.guide,snapshot.guide_revision
    else:
        guide=CatalogItem.objects.select_related("current_revision").filter(
            public_id=guide_id,type_slug="setup_guide").first()
        if guide is None or guide.current_revision_id is None:
            raise InvalidSession("Unknown Server Setup Guide")
        guide_revision=guide.current_revision
    participant_ids=data.get("selected_participant_ids",[])
    if not isinstance(participant_ids,list) or len(participant_ids)>64 or len(participant_ids)!=len(set(
            x for x in participant_ids if isinstance(x,str))):
        raise InvalidSession("Selected participant IDs must be unique")
    allowed=set(snapshot.participant_pins.values_list("participant__public_id",flat=True))
    if any(not isinstance(x,str) or x not in allowed for x in participant_ids):
        raise InvalidSession("Selected participants must belong to the pinned campaign snapshot")
    if snapshot.framework_id and not participant_ids:
        raise InvalidSession("Select at least one registered Framework participant")
    if not snapshot.framework_id and participant_ids:
        raise InvalidSession("Non-Framework sessions have no participants")
    from .individual_setup_services import prepare, save
    from .campaign_matrix_services import evaluation, prepared_for_session
    plan=snapshot.revision.properties.get("matrix_plan")
    evaluation_id=data.get("evaluation_id")
    planned=None
    if plan:
        if not isinstance(evaluation_id,str):
            raise InvalidSession("Select a planned evaluation in the campaign matrix")
        cell,planned=evaluation(plan,evaluation_id,data.get("test_case_id"))
        if not planned:
            raise InvalidSession("Evaluation is missing, deselected or waived")
        if planned["task_id"]!=case.test_case.task.item.public_id:
            raise InvalidSession("Evaluation Task differs from pinned Test Case")
    elif evaluation_id is not None:
        raise InvalidSession("This legacy campaign has no evaluation matrix")
    if planned:
        # Fixed, immutable revision references are loaded from the evaluated
        # configuration, not today's mutable current Model or Provider version.
        if planned["kind"]=="framework":
            prepared_for_session(snapshot,planned,data,participant_ids)
            prepared=prepare(snapshot,participant_ids,data)
        else:
            prepared=prepared_for_session(snapshot,planned,data,participant_ids)
    else:
        prepared=prepare(snapshot,participant_ids,data)
    # A Task-centred Campaign without a Framework cannot know its billable
    # components before the individual session setup is chosen. Preserve its
    # exact manually selected offer revisions on this immutable session.
    session_prices=[]
    if snapshot.revision.properties.get("pricing_policy")=="offer_revisions_v1":
        from .pricing_services import pricing_status, prepare_selections, readiness
        if snapshot.framework_id or snapshot.revision.properties.get("mode")=="solution_centred":
            if snapshot.framework_id:
                from .pricing_services import readiness
                required={"root:framework"}|{
                    pid+":"+kind for pid in participant_ids
                    for kind in ("model","provider","harness")
                }
                priced={pin.source_key:pin for pin in
                    snapshot.pricing_pins.select_related("offer_revision")}
                missing=sorted(required-set(priced))
                bad=(["Unselected source(s): "+", ".join(missing)] if missing else [])
                for key in sorted(required&set(priced)):
                    checked=readiness(priced[key].offer_revision)
                    if not checked["complete"]:
                        bad.extend(key+": "+msg for msg in checked["reasons"])
                if bad:
                    raise SessionConflict("Pricing incomplete for selected Framework "
                                          "participants: "+"; ".join(bad))
            else:
                check=pricing_status(snapshot)
                if not check["complete"]:
                    raise SessionConflict("Pricing incomplete; choose complete campaign "
                                          "tariff revisions: "+"; ".join(check["reasons"]))
            if "pricing_selections" in data:
                raise InvalidSession("Session tariff override forbidden for fixed campaign pricing")
        else:
            if prepared is None:
                raise SessionConflict("Pricing incomplete; choose the technical trio before session start")
            context={"components":[(kind,part[0],part[1])
                       for kind,part in prepared["parts"].items()],
                     "framework":None,"participants":[]}
            from .pricing_services import InvalidPricing
            try:
                session_prices=prepare_selections(data.get("pricing_selections"),context)
            except InvalidPricing as exc:
                raise InvalidSession(str(exc)) from exc
            required={"root:model","root:provider","root:harness"}
            actual={entry[0] for entry in session_prices}
            if actual != required:
                raise SessionConflict("Pricing incomplete; manually select an offer for "
                                      "each session Model/Provider/Harness")
            bad=[entry[0]+": "+"; ".join(readiness(entry[3])["reasons"])
                 for entry in session_prices if not readiness(entry[3])["complete"]]
            if bad:
                raise SessionConflict("Pricing incomplete: "+"; ".join(bad))

    descriptor=copy.deepcopy(snapshot.method_definition.json_schema)
    if not isinstance(descriptor,dict):
        raise InvalidSession("Unsupported experimental method schema")
    for _ in range(12):
        candidate=new_public_id("ses")
        try:
            with transaction.atomic():
                session=BenchmarkSession.objects.create(
                    public_id=candidate,campaign_snapshot=snapshot,case_pin=case,
                    guide=guide,guide_revision=guide_revision,
                    method_definition=snapshot.method_definition,method_descriptor=descriptor,
                    selected_participants=participant_ids,created_by=actor)
                save(session,prepared)
                SessionPricingPin.objects.bulk_create([
                    SessionPricingPin(session=session,source_key=key,component=component,
                                      offer=offer,offer_revision=rev)
                    for key,component,offer,rev in session_prices
                ])
                from .run_cost_services import contract as cost_contract
                gate=cost_contract(session)
                if gate is not None and not gate["complete"]:
                    raise SessionConflict("Pre-execution tariff incomplete: "+"; ".join(gate["reasons"]))
                _save(session,actor,"created",_initial_state(session,evaluation_id),1)
                return session
        except IntegrityError:
            if BenchmarkSession.objects.filter(public_id=candidate).exists():
                continue
            raise
    raise InvalidSession("Could not allocate a session identifier")


def append(*, actor, public_id, expected_revision, action, data, step_key=None):
    if not isinstance(expected_revision,str):
        raise InvalidSession("expected_revision is required")
    with transaction.atomic():
        session=BenchmarkSession.objects.select_for_update().select_related(
            "campaign_snapshot__revision__item","campaign_snapshot__owner",
            "case_pin__test_case__item").filter(public_id=public_id).first()
        if session is None:
            raise InvalidSession("Unknown Server session")
        if not can_edit(actor,session):
            raise SessionAccessDenied(
                "Only the experimenter who created this active Run may edit its session")
        current=_checkpoint(session)
        if expected_revision!=f"r{current.number:03d}":
            raise SessionConflict("Draft changed in another browser; reload before saving")
        state=copy.deepcopy(current.state)
        if action in ("pause","resume"):
            if data:
                raise InvalidSession("Lifecycle actions accept no additional fields")
            expected="in_progress" if action=="pause" else "paused"
            if state.get("status")!=expected:
                raise SessionConflict("Session lifecycle transition is not allowed")
            state["status"]="paused" if action=="pause" else "in_progress"
        elif state.get("status")!="in_progress":
            raise SessionConflict("Resume the paused session before recording more work")
        elif action=="setup":
            allowed={"started_at","installation_duration_minutes","environment",
                     "notes","extensions","evidence_link_ids"}
            if set(data)-allowed:
                raise InvalidSession("Unknown setup fields")
            setup=state["setup"]
            for key,value in data.items():
                if key=="started_at":value=_timestamp(value,key)
                elif key=="installation_duration_minutes":value=_minutes(value,key)
                elif key=="environment":value=_bounded_object(value,key)
                elif key=="extensions":value=_bounded_object(value,key)
                elif key=="notes":value=_text(value,key)
                elif key=="evidence_link_ids":
                    if not isinstance(value,list):raise InvalidSession("Evidence must be a list")
                setup[key]=value
        elif action=="step":
            if set(data)-{"status","values","notes","duration_minutes",
                          "extensions","evidence_link_ids","schema_version","current_step"}:
                raise InvalidSession("Unknown step fields")
            keys=[row["key"] for row in _descriptors(session)]
            if step_key not in keys:
                raise InvalidSession("Step is not in the session's original method version")
            step=state["steps"][step_key]
            for key,value in data.items():
                if key=="status" and value not in ("pending","in_progress","done"):
                    raise InvalidSession("Invalid step progress status")
                elif key=="values":
                    value=_bounded_object(value,key)
                    value=dict(step["values"],**value)  # Partial form writes preserve unknown extensions.
                elif key=="notes":value=_text(value,key)
                elif key=="duration_minutes":value=_minutes(value,key)
                elif key=="extensions":
                    value=dict(step["extensions"],**_bounded_object(value,key))
                elif key=="schema_version":value=_text(value,key,160,required=True)
                elif key=="current_step":
                    if value not in keys:raise InvalidSession("Current step is not in method")
                    state["current_step"]=value
                    continue
                step[key]=value
            state["current_step"]=step_key if "current_step" not in data else state["current_step"]
        elif action=="metering":
            from .run_cost_services import contract as cost_contract, decimal as price_decimal
            schema=cost_contract(session)
            if schema is None:
                raise InvalidSession("Legacy Runs do not have a pinned usage tariff")
            if not schema["complete"]:
                raise SessionConflict("Original tariff is not complete")
            allowed={(m["source_key"],m["meter"]) for m in schema["required_meters"]}
            if set(data)!={"consumption"} or not isinstance(data["consumption"],dict):
                raise InvalidSession("Consumption must be a source-keyed JSON object")
            recorded=copy.deepcopy(state.get("metering",{}))
            for source,values in data["consumption"].items():
                if not isinstance(source,str) or not isinstance(values,dict) or len(values)>32:
                    raise InvalidSession("Invalid source metering object")
                for meter,value in values.items():
                    if (source,meter) not in allowed:
                        raise InvalidSession("Meter is not required by the original tariff")
                    if value is None:
                        if source in recorded:recorded[source].pop(meter,None)
                    else:
                        from .run_cost_services import InvalidMeter
                        try:amount=price_decimal(value,source+"/"+meter)
                        except InvalidMeter as exc:raise InvalidSession(str(exc)) from exc
                        recorded.setdefault(source,{})[meter]=str(amount)
                if not recorded.get(source):recorded.pop(source,None)
            state["metering"]=recorded
        elif action=="results":
            # Durable incomplete result capture is independent of Run finality;
            # a missing required usage meter never discards experiment outputs.
            from .run_services import _metrics
            allowed={"outcome","quality_score","quality_evaluation",
                "information_utility_score","information_utility_evaluation",
                "tokens_count","tokens_multiplier","cost_mode","cost_eur",
                "human_review_minutes","human_correction_minutes",
                "produced_outputs","notes","extensions","evidence_link_ids"}
            if set(data)-allowed:
                raise InvalidSession("Unsupported results draft fields")
            draft=dict(state.get("results_draft",{}))
            draft.update(data)
            if len(json.dumps(draft,ensure_ascii=False,allow_nan=False))>65536:
                raise InvalidSession("Results draft exceeds maximum size")
            state["results_draft"]=draft
        elif action=="interaction":
            if set(data)-{"type","content","occurred_at","human_minutes","agent_minutes",
                          "participant_id","notes","extensions","evidence_link_ids","schema_version"}:
                raise InvalidSession("Unknown interaction fields")
            if len(state["interactions"])>=MAX_INTERACTIONS:
                raise InvalidSession("Maximum 500 interactions per draft")
            typ=data.get("type","human_prompt")
            if typ not in ("human_prompt","agent_response","tool_action","review","note","other"):
                raise InvalidSession("Unknown interaction type")
            content=_text(data.get("content"),"content",20000,required=True)
            participant=data.get("participant_id")
            if participant is not None and participant not in session.selected_participants:
                raise InvalidSession("Interaction participant must be selected for this session")
            record={
                "id":str(uuid7()),"order":len(state["interactions"]),
                "type":typ,"content":content,
                "occurred_at":_timestamp(data.get("occurred_at",timezone.now().isoformat()),"occurred_at"),
                "human_minutes":_minutes(data.get("human_minutes"),"human_minutes"),
                "agent_minutes":_minutes(data.get("agent_minutes"),"agent_minutes"),
                "participant_id":participant,
                "notes":_text(data.get("notes",""),"notes"),
                "extensions":_bounded_object(data.get("extensions",{}),"extensions"),
                "evidence_link_ids":data.get("evidence_link_ids",[]),
                "schema_version":_text(data.get("schema_version","1"),"schema_version",160,required=True),
            }
            state["interactions"].append(record)
        else:
            raise InvalidSession("Unknown session action")
        # Missing times remain null until the experimenter explicitly measures them.
        values=state["interactions"]
        state["measurements"]={
            "human_total_minutes":sum(x["human_minutes"] for x in values)
                if values and all(x["human_minutes"] is not None for x in values) else None,
            "agent_total_minutes":sum(x["agent_minutes"] for x in values)
                if values and all(x["agent_minutes"] is not None for x in values) else None,
        }
        _save(session,actor,action,state,current.number+1)
        return session


def _individual_setup(session):
    from .individual_setup_services import serialize as serialize_setup
    return serialize_setup(session)


def serialize(session, checkpoint=None, include_state=True):
    cp=checkpoint or _checkpoint(session)
    snap=session.campaign_snapshot
    pinned=session.case_pin
    result={
        "id":session.public_id,"uuid":str(session.pk),
        "revision":f"r{cp.number:03d}","checkpoint_id":str(cp.pk),
        "last_action":cp.action,"saved_at":cp.saved_at.isoformat(),
        "campaign_id":snap.revision.item.public_id,
        "campaign_revision":f"r{snap.revision.number:03d}",
        "campaign_revision_id":str(snap.revision_id),
        "test_case_id":pinned.test_case.item.public_id,
        "test_case_revision_id":str(pinned.revision_id),
        "method_version":session.method_definition.version,
        "method_definition_id":str(session.method_definition_id),
        "method_descriptor":session.method_descriptor,
        "guide_id":session.guide.public_id if session.guide_id else None,
        "guide_revision_id":str(session.guide_revision_id) if session.guide_revision_id else None,
        "selected_participant_ids":session.selected_participants,
        "evaluation_id":cp.state.get("evaluation_id"),
        "individual_setup":_individual_setup(session),
        "pricing_selections":[{
           "source_key":p.source_key,"component_id":p.component.public_id,
           "offer_id":p.offer.public_id,"offer_revision_id":str(p.offer_revision_id),
           "offer_revision":f"r{p.offer_revision.number:03d}"
        } for p in session.pricing_pins.select_related(
           "component","offer","offer_revision").order_by("source_key")],
        "pricing_source":"session" if session.pricing_pins.exists()
            else ("campaign" if snap.revision.properties.get("pricing_policy")=="offer_revisions_v1"
                  else "legacy_unclassified"),
        "metering":None,
        "created_by":session.created_by.get_username(),
        "created_at":session.created_at.isoformat(),
    }
    from .run_cost_services import metering_state
    result["metering"]=metering_state(session,cp.state)
    if include_state:
        result["state"]=cp.state
        result["evidence"]=[{"id":str(pin.evidence_id),
                            "sha256":pin.evidence.blob_id,"filename":pin.evidence.original_filename}
                            for pin in cp.evidence_pins.select_related("evidence").order_by("evidence_id")]
    return result
