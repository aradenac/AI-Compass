"""FUT-08: immutable campaign evaluation planning, independent from measured evidence.

The JSON plan belongs to each immutable Campaign CatalogRevision. It is never
used to overwrite a Run, and the measured status is a separate derived view.
Old campaigns without a matrix retain their original method semantics.
"""
from copy import deepcopy
from datetime import datetime, timezone
from django.db import transaction
from .catalog_ids import new_public_id, uuid7
from .models import (BenchmarkSession, BenchmarkRun, CompositeBenchmarkRun,
                     CampaignSnapshot, CatalogRevision, TestCase)
from .campaign_services import InvalidCampaign, InvalidTransition, _case, _component, _task, modify

DECISIONS = {"selected", "not_selected", "waived"}
MAX_CONFIGS, MAX_CELLS = 128, 1024


def _unique(prefix, occupied):
    for _ in range(30):
        key = new_public_id(prefix)+"-"+uuid7().hex[-12:]
        if key not in occupied:
            occupied.add(key)
            return key
    raise InvalidCampaign("Unable to allocate an unused matrix identifier")


def _current(item):
    revision=item.current_revision
    return revision.properties.get("matrix_plan") or {
        "version": 1, "configurations": [], "cells": []
    }


def _checked_list(value, label, limit=200):
    if not isinstance(value, list) or len(value)>limit or any(
            not isinstance(x, str) or not x or len(x)>120 for x in value):
        raise InvalidCampaign(label+" must be a bounded list of identifiers")
    if len(value)!=len(set(value)):
        raise InvalidCampaign(label+" contains repeated identifiers")
    return value


def _configuration(actor, data, snapshot, occupied):
    if not isinstance(data, dict) or set(data)-{
        "action","task_id","kind","label","component_ids","configuration_version",
        "settings","participant_ids","test_case_ids"}:
        raise InvalidCampaign("Invalid matrix configuration declaration")
    task=_task(data.get("task_id"))
    kind=data.get("kind","individual")
    label=data.get("label","")
    if not isinstance(label,str) or not 1<=len(label.strip())<=160:
        raise InvalidCampaign("Configuration label is required")
    config={
        "id": _unique("evl",occupied), "task_id":task.item.public_id,
        "task_revision_id":str(task.item.current_revision_id),
        "label":label.strip(),"kind":kind,
    }
    if kind=="individual":
        components=data.get("component_ids")
        if not isinstance(components,dict) or set(components)!={"model","provider","harness"}:
            raise InvalidCampaign("Matrix configuration needs a complete Model/Provider/Harness trio")
        parts={k:_component(k,v) for k,v in components.items()}
        version=data.get("configuration_version","1")
        settings=data.get("settings",{})
        if not isinstance(version,str) or not 1<=len(version)<=160:
            raise InvalidCampaign("Invalid configuration version")
        if not isinstance(settings,dict) or len(str(settings))>32768:
            raise InvalidCampaign("Configuration settings must be a bounded object")
        config.update(component_ids={k:v.public_id for k,v in parts.items()},
                      component_revision_ids={k:str(v.current_revision_id) for k,v in parts.items()},
                      configuration_version=version,settings=settings)
    elif kind=="framework":
        if not snapshot.framework_id:
            raise InvalidCampaign("Framework configurations require a selected campaign Framework")
        ids=_checked_list(data.get("participant_ids"),"participant_ids",64)
        if not ids:
            raise InvalidCampaign("Framework configuration requires participants")
        available=set(snapshot.participant_pins.values_list("participant__public_id",flat=True))
        if not set(ids)<=available:
            raise InvalidCampaign("Framework participant not pinned to campaign")
        members={}
        for pin in snapshot.participant_pins.select_related("participant"):
            if pin.participant.public_id not in ids:
                continue
            members[pin.participant.public_id]={
                "model_revision_id":str(pin.model_revision_id),
                "provider_revision_id":str(pin.provider_revision_id),
                "harness_revision_id":str(pin.harness_revision_id),
                "configuration_version":pin.configuration_version,
                "settings":pin.settings,"properties":pin.properties,
            }
        config.update(participant_ids=ids,participant_snapshots=members,
                      framework_id=snapshot.framework.public_id,
                      framework_revision_id=str(snapshot.framework_revision_id))
    else:
        raise InvalidCampaign("Matrix kind must be individual or framework")
    case_ids=_checked_list(data.get("test_case_ids"),"test_case_ids")
    if not case_ids:
        raise InvalidCampaign("Add at least one Test Case assigned to this Task")
    for case_id in case_ids:
        if _case(case_id).task_id!=task.pk:
            raise InvalidCampaign("Every candidate Test Case must belong to its configuration Task")
    return config,case_ids


def apply(*,actor,item,expected_revision,operation):
    """Atomic optimistic edit; modifies same campaign revision engine as legacy UI."""
    if not isinstance(operation,dict) or set(operation)-{
        "action","task_id","kind","label","component_ids","configuration_version",
        "settings","participant_ids","test_case_ids","configuration_id",
        "evaluation_id","decision","reason"}:
        raise InvalidCampaign("Unknown evaluation-plan edit fields")
    with transaction.atomic():
        locked=item.__class__.objects.select_for_update(of=("self",)).select_related("current_revision").get(pk=item.pk)
        rev=locked.current_revision
        if expected_revision!=f"r{rev.number:03d}":
            from .catalog_services import RevisionConflict
            raise RevisionConflict("Campaign matrix changed; reload exact revision")
        if rev.properties["archived"] or rev.properties["status"] not in ("planned","in_progress"):
            raise InvalidTransition("Reopen campaign before changing evaluation plan")
        snap=CampaignSnapshot.objects.select_related("framework").get(revision=rev)
        plan=deepcopy(_current(locked))
        configs=plan["configurations"];cells=plan["cells"]
        action=operation.get("action")
        case_ids=set(snap.case_pins.values_list("test_case__item__public_id",flat=True))
        if action=="add_configuration":
            if len(configs)>=MAX_CONFIGS:
                raise InvalidCampaign("Too many matrix configurations")
            config,added=_configuration(actor,operation,snap,{c["id"] for c in configs})
            config["introduced_revision"]=f"r{rev.number+1:03d}"
            configs.append(config)
            existing={c["id"] for c in cells}|{c["id"] for c in configs}
            for cid in added:
                if len(cells)>=MAX_CELLS:raise InvalidCampaign("Matrix size limit exceeded")
                case_ids.add(cid)
                cells.append({"id":_unique("evl",existing),"configuration_id":config["id"],
                              "test_case_id":cid,"decision":"selected","history":[],
                              "introduced_revision":f"r{rev.number+1:03d}"})
        elif action=="add_cases":
            config=next((c for c in configs if c["id"]==operation.get("configuration_id")),None)
            if config is None:raise InvalidCampaign("Unknown Task/configuration association")
            added=_checked_list(operation.get("test_case_ids"),"test_case_ids")
            if not added:raise InvalidCampaign("Select eligible Test Cases")
            known={(c["configuration_id"],c["test_case_id"]) for c in cells}
            occupied={c["id"] for c in cells}|{c["id"] for c in configs}
            for cid in added:
                if _case(cid).task.item.public_id!=config["task_id"]:
                    raise InvalidCampaign("Test Case belongs to a different Task")
                # Adding a TC at Task level offers it to *each* configuration
                # associated with that Task; preserved decisions are unchanged.
                for peer in (c for c in configs if c["task_id"]==config["task_id"]):
                    key=(peer["id"],cid)
                    if key not in known:
                        if len(cells)>=MAX_CELLS:raise InvalidCampaign("Matrix size limit exceeded")
                        cells.append({"id":_unique("evl",occupied),
                                      "configuration_id":peer["id"],"test_case_id":cid,
                                      "decision":"selected","history":[],
                                      "introduced_revision":f"r{rev.number+1:03d}"})
                        known.add(key)
                case_ids.add(cid)
        elif action=="decide":
            cell=next((x for x in cells if x["id"]==operation.get("evaluation_id")),None)
            if cell is None:raise InvalidCampaign("Unknown evaluation cell")
            decision=operation.get("decision")
            if decision not in DECISIONS:raise InvalidCampaign("Unsupported matrix decision")
            reason=operation.get("reason","")
            if not isinstance(reason,str) or len(reason)>4000:
                raise InvalidCampaign("Decision reason must be text (max 4000)")
            if decision=="waived" and (cell["decision"]!="selected" or not reason.strip()):
                raise InvalidCampaign("Waiver requires a selected evaluation and a reason")
            if decision!="waived" and reason.strip():
                raise InvalidCampaign("Only a waiver accepts a reason")
            if decision==cell["decision"]:
                raise InvalidCampaign("No evaluation decision change")
            cell.setdefault("history",[]).append({
                "from":cell["decision"],"to":decision,
                "actor":actor.get_username(),"at":datetime.now(timezone.utc).isoformat(),
                "reason":reason.strip(),"source_revision":f"r{rev.number:03d}",
            })
            cell["decision"]=decision
            if decision=="waived":
                cell["waiver"] = cell["history"][-1]
            else:
                cell.pop("waiver",None)
        else:
            raise InvalidCampaign("Unknown evaluation-plan action")
        # Stable complete plan is stored on the next immutable CatalogRevision.
        # Includes linked Case revision pins, even when spanning multiple Tasks.
        payload={"expected_revision":expected_revision,
                 "properties":{"matrix_plan":plan}, "_trusted_matrix":True,
                 "test_case_ids":sorted(case_ids)}
        result,_=modify(actor=actor,public_id=locked.public_id,data=payload)
        return result


def evaluation(plan, ident, case_id):
    if not plan:return None,None
    cell=next((x for x in plan["cells"] if x["id"]==ident),None)
    if cell is None or cell["test_case_id"]!=case_id or cell["decision"]!="selected":
        return None,None
    cfg=next((c for c in plan["configurations"] if c["id"]==cell["configuration_id"]),None)
    return cell,cfg


def projection(item, revision):
    """Current observed attempts, separate from immutable plan decisions.

    Run links are explicit, and no older untagged/legacy session is misattributed
    to a matrix cell. Failed-DoD closed runs still count as *evaluated*.
    """
    plan=deepcopy(revision.properties.get("matrix_plan"))
    if not plan:
        return {"revision":f"r{revision.number:03d}","configured":False,
                "configurations":[],"cells":[],"summary":None}
    ids={c["id"] for c in plan["cells"]}
    grouped={key:{"in_progress":0,"runs":[]} for key in ids}
    sessions=BenchmarkSession.objects.filter(
        campaign_snapshot__revision__item=item).prefetch_related("checkpoints")
    session_ids={}
    for s in sessions:
        init=next((cp for cp in s.checkpoints.all() if cp.number==1),None)
        eid=init.state.get("evaluation_id") if init else None
        if eid in ids:
            session_ids[s.pk]=eid
            grouped[eid]["in_progress"]+=1
    for run in BenchmarkRun.objects.filter(session_id__in=session_ids).only(
            "public_id","session_id","outcome"):
        eid=session_ids[run.session_id]
        grouped[eid]["runs"].append({"id":run.public_id,"outcome":run.outcome,"kind":"individual"})
        grouped[eid]["in_progress"]-=1
    for run in CompositeBenchmarkRun.objects.filter(session_id__in=session_ids).only(
            "public_id","session_id","outcome"):
        eid=session_ids[run.session_id]
        grouped[eid]["runs"].append({"id":run.public_id,"outcome":run.outcome,"kind":"framework"})
        grouped[eid]["in_progress"]-=1
    totals={"candidates":len(ids),"not_selected":0,"waived":0,
            "pending":0,"in_progress":0,"evaluated":0,"measured_runs":0}
    for cell in plan["cells"]:
        runs=grouped[cell["id"]]["runs"]
        active=grouped[cell["id"]]["in_progress"]
        decision=cell["decision"]
        state=("not_selected" if decision=="not_selected" else
               "waived" if decision=="waived" else
               "evaluated" if runs else "in_progress" if active else "pending")
        cell["status"]=state
        cell["runs"]=runs
        cell["active_attempts"]=active
        totals[state]+=1
        totals["measured_runs"]+=len(runs)
    selected=totals["pending"]+totals["in_progress"]+totals["evaluated"]
    totals["selected_obligations"]=selected
    totals["outstanding"]=totals["pending"]+totals["in_progress"]
    totals["full_plan_complete"]=not totals["outstanding"]
    totals["experiment_coverage"]={"evaluated":totals["evaluated"],
                                    "selected_obligations":selected}
    plan["summary"]=totals
    plan["revision"]=f"r{revision.number:03d}"
    plan["configured"]=True
    return plan

def prepared_for_session(snapshot, config, data, participant_ids):
    """Resolve the selected exact revision pins, never silently repin to latest."""
    from .session_services import InvalidSession
    from .models import CatalogItem, CatalogRevision
    if config["kind"]=="framework":
        if not snapshot.framework_id or config.get("framework_id")!=snapshot.framework.public_id:
            raise InvalidSession("Framework configuration is not pinned to this campaign")
        if participant_ids!=config["participant_ids"]:
            raise InvalidSession("Selected Framework participants differ from the matrix plan")
        current={p.participant.public_id:p for p in snapshot.participant_pins.select_related("participant")}
        for public_id in participant_ids:
            pin=current.get(public_id)
            expected=config.get("participant_snapshots",{}).get(public_id)
            if pin is None or not expected or any(
                expected.get(kind+"_revision_id")!=str(getattr(pin,kind+"_revision_id"))
                for kind in ("model","provider","harness")
            ) or expected.get("configuration_version")!=pin.configuration_version or (
                expected.get("settings")!=pin.settings or expected.get("properties")!=pin.properties
            ):
                raise InvalidSession("Framework participant changed since the evaluation plan was pinned")
        if any(k in data for k in ("component_ids","settings","configuration_version","properties")):
            raise InvalidSession("Framework session setup is fixed by participant pins")
        return None
    if snapshot.framework_id:
        raise InvalidSession("Framework campaign requires its configured participant group")
    if participant_ids:
        raise InvalidSession("Individual matrix evaluation cannot select Framework participants")
    ids=config["component_ids"]
    if "component_ids" in data and data["component_ids"]!=ids:
        raise InvalidSession("Selected setup differs from pinned evaluation")
    if "settings" in data and data["settings"]!=config["settings"]:
        raise InvalidSession("Settings differ from pinned evaluation")
    if "configuration_version" in data and data["configuration_version"]!=config["configuration_version"]:
        raise InvalidSession("Configuration version differs from pinned evaluation")
    if data.get("properties",{})!={}:
        raise InvalidSession("Unplanned capabilities are not permitted in the pinned evaluation")
    parts={}
    for kind in ("model","provider","harness"):
        item=CatalogItem.objects.filter(type_slug=kind,public_id=ids[kind]).first()
        revision=CatalogRevision.objects.filter(
            item=item,pk=config["component_revision_ids"][kind]).first() if item else None
        if revision is None:
            raise InvalidSession("Evaluation's exact component revision is missing")
        parts[kind]=(item,revision)
    return {"parts":parts,"settings":config["settings"],"properties":{},
            "configuration_version":config["configuration_version"]}
