"""PLAT-22: reviewed, immutable recommendations citing only measured individual Runs.

An edit to a published recommendation appends a workgroup Draft, while ordinary
readers continue to see its *previous* published revision. Explicit unpublishing
withdraws that projection without deleting original publication or evidence.
"""
import copy
import json

from django.db import IntegrityError,transaction
from django.utils import timezone

from .activity_services import record_catalog_event
from .catalog_compat import compatibility_for_revision
from .catalog_ids import new_public_id
from .catalog_schemas import InvalidModel,validate_model
from .catalog_services import RevisionConflict,SchemaWriteBlocked,ExhaustedIds
from .models import (CatalogItem,CatalogRevision,ObjectTypeVersion,TaskNode,
                     MeasuredSolution,BenchmarkRun,EvaluationSnapshot,
                     RecommendationSnapshot,RecommendationRunPin)

KIND="recommendation"
STATES=("draft","in_review","published","unpublished")
DECISIONS=("recommended","conditional","not_recommended")
MAX_RUNS=40


class InvalidRecommendation(ValueError):
    pass


def _json(data,limit=40000):
    try:
        encoded=json.dumps(data,allow_nan=False,ensure_ascii=False)
    except (TypeError,ValueError) as exc:
        raise InvalidRecommendation("Invalid JSON object") from exc
    if len(encoded)>limit:raise InvalidRecommendation("Content too large")
    return copy.deepcopy(data)


def _properties(data,old=None):
    if not isinstance(data,dict):raise InvalidRecommendation("properties must be an object")
    if set(data)-{"decision","rationale","limitations","extensions"}:
        raise InvalidRecommendation("Review and publication fields are action-only")
    p=copy.deepcopy(old or {})
    p.update(copy.deepcopy(data))
    p.setdefault("state","draft")
    p.setdefault("decision","conditional")
    p.setdefault("rationale","")
    p.setdefault("limitations","")
    p.setdefault("extensions",{})
    p.setdefault("review_note","")
    p.setdefault("publication_note","")
    p["evidence_class"]="recommendation"
    if p["decision"] not in DECISIONS:raise InvalidRecommendation("Unsupported decision")
    for name,size in (("rationale",16000),("limitations",10000)):
        if not isinstance(p[name],str) or len(p[name])>size:
            raise InvalidRecommendation(name+" must be bounded text")
    if not p["rationale"].strip():raise InvalidRecommendation("Explicit rationale required")
    if not isinstance(p["extensions"],dict):raise InvalidRecommendation("Extensions must be an object")
    return _json(p)


def _source_task(identifier,old=None):
    if identifier is None and old:return old.task,old.task_revision
    if not isinstance(identifier,str) or not identifier.startswith("tsk-"):
        raise InvalidRecommendation("Use a real engineering Task ID")
    task=TaskNode.objects.select_related("item__current_revision").filter(
        item__public_id=identifier).first()
    if task is None:raise InvalidRecommendation("Unknown engineering Task")
    if old and old.task_id==task.pk:return old.task,old.task_revision
    return task,task.item.current_revision


def _source_solution(identifier,old=None):
    if identifier is None and old:return old.solution,old.solution_revision
    if not isinstance(identifier,str) or not identifier.startswith("sol-"):
        raise InvalidRecommendation("Use an actual measured individual Solution")
    solution=MeasuredSolution.objects.select_related("item__current_revision").filter(
        item__public_id=identifier).first()
    if solution is None:raise InvalidRecommendation("Unknown measured individual Solution")
    if old and old.solution_id==solution.pk:return old.solution,old.solution_revision
    return solution,solution.item.current_revision


def _run_refs(ids,task,solution,old=None):
    if ids is None and old is not None:
        return [p.run for p in old.run_pins.select_related("run").order_by("id")]
    if not isinstance(ids,list) or not 1<=len(ids)<=MAX_RUNS or len(ids)!=len(set(
            r for r in ids if isinstance(r,str))):
        raise InvalidRecommendation("Select 1–40 distinct original individual Runs")
    if any(not isinstance(r,str) or not r.startswith("run-") for r in ids):
        raise InvalidRecommendation("Run references must be permanent individual IDs")
    found={r.public_id:r for r in BenchmarkRun.objects.select_related(
        "session__case_pin__test_case","solution__item","solution_revision"
        ).filter(public_id__in=ids)}
    if len(found)!=len(ids):raise InvalidRecommendation("Missing or composite Run ID")
    ordered=[found[r] for r in ids]
    for r in ordered:
        if r.solution_id!=solution.pk or r.session.case_pin.test_case.task_id!=task.pk:
            raise InvalidRecommendation("Run must match the exact Task and individual Solution")
    return ordered


def _evaluation(reference,revision,run_ids,old=None):
    if reference is None and revision is None and old is not None:
        return old.evaluation
    if reference is None and revision is None:return None
    if reference is None:
        raise InvalidRecommendation("evaluation_id required when specifying evaluation_revision")
    if not isinstance(reference,str) or not reference.startswith("evl-"):
        raise InvalidRecommendation("Invalid Evaluation ID")
    item=CatalogItem.objects.select_related("current_revision").filter(
        public_id=reference,type_slug="evaluation").first()
    if item is None:raise InvalidRecommendation("Evaluation not found")
    if revision is None:
        rev=item.current_revision
    elif isinstance(revision,str) and revision.startswith("r") and revision[1:].isdigit():
        number=int(revision[1:])
        if revision!=f"r{number:03d}":raise InvalidRecommendation("Use exact r001 revision")
        rev=CatalogRevision.objects.filter(item=item,number=number).first()
    else:raise InvalidRecommendation("Invalid Evaluation revision")
    if rev is None:raise InvalidRecommendation("Evaluation revision not found")
    snapshot=EvaluationSnapshot.objects.filter(revision=rev).first()
    if snapshot is None:raise InvalidRecommendation("Evaluation snapshot missing")
    pinned=set(snapshot.individual_pins.values_list("run__public_id",flat=True))
    if not set(run_ids).issubset(pinned):
        raise InvalidRecommendation("Selected source Runs absent from exact Evaluation revision")
    return snapshot


def _inputs(data,old=None):
    task,task_revision=_source_task(data.get("task_id"),old)
    solution,solution_revision=_source_solution(data.get("solution_id"),old)
    runs=_run_refs(data.get("run_ids"),task,solution,old)
    evaluation=_evaluation(data.get("evaluation_id"),data.get("evaluation_revision"),
                           [r.public_id for r in runs],old)
    # Existing frozen evaluation is not preserved if the caller changes Runs.
    if old and "run_ids" in data and "evaluation_id" not in data and evaluation:
        existing={p.run_id for p in evaluation.individual_pins.all()}
        if not {r.id for r in runs}.issubset(existing):
            raise InvalidRecommendation("Changing Runs requires a new matching Evaluation revision")
    return task,task_revision,solution,solution_revision,runs,evaluation


def _write_snapshot(revision,inputs,reviewer=None,reviewed_at=None):
    task,task_revision,solution,solution_revision,runs,evaluation=inputs
    snap=RecommendationSnapshot.objects.create(
        revision=revision,task=task,task_revision=task_revision,
        solution=solution,solution_revision=solution_revision,evaluation=evaluation,
        reviewed_by=reviewer,reviewed_at=reviewed_at)
    RecommendationRunPin.objects.bulk_create([
        RecommendationRunPin(snapshot=snap,run=r) for r in runs
    ])
    return snap


def create(*,actor,data):
    if not isinstance(data,dict) or set(data)-{
            "name","task_id","solution_id","run_ids","evaluation_id",
            "evaluation_revision","properties"}:
        raise InvalidRecommendation("Unexpected recommendation fields")
    schema=ObjectTypeVersion.objects.filter(type_slug=KIND,version=1).first()
    if not schema:raise InvalidRecommendation("Recommendation schema unavailable")
    p=_properties(data.get("properties",{}))
    name=validate_model(data.get("name"),p,schema.json_schema)
    inputs=_inputs(data)
    for _ in range(12):
        code=new_public_id("rec")
        try:
            with transaction.atomic():
                item=CatalogItem.objects.create(type_slug=KIND,public_id=code)
                rev=CatalogRevision.objects.create(
                    item=item,number=1,schema_version=schema,
                    display_name=name,properties=p,created_by=actor)
                _write_snapshot(rev,inputs)
                item.current_revision=rev;item.save(update_fields=["current_revision"])
                record_catalog_event(item=item,revision=rev,actor=actor,action="created")
                return item
        except IntegrityError:
            if CatalogItem.objects.filter(public_id=code).exists():continue
            raise
    raise ExhaustedIds("Recommendation ID capacity exhausted")


def change(*,actor,identifier,data,action=None):
    if not isinstance(data,dict):raise InvalidRecommendation("Expected JSON object")
    with transaction.atomic():
        item=CatalogItem.objects.select_for_update(of=("self",)).select_related(
            "current_revision__schema_version").filter(
            type_slug=KIND,public_id=identifier).first()
        if item is None:raise InvalidRecommendation("Unknown recommendation")
        previous=item.current_revision
        if data.get("expected_revision")!=f"r{previous.number:03d}":
            raise RevisionConflict("Recommendation changed; reload its current revision")
        compatibility=compatibility_for_revision(item,previous)
        if compatibility["read_only"] or previous.schema_version.version!=1:
            raise SchemaWriteBlocked(compatibility)
        old=RecommendationSnapshot.objects.get(revision=previous)
        if action is None:
            if set(data)-{"expected_revision","name","task_id","solution_id","run_ids",
                         "evaluation_id","evaluation_revision","properties"}:
                raise InvalidRecommendation("Unsupported Recommendation edit")
            inputs=_inputs(data,old)
            props=_properties(data.get("properties",{}),previous.properties)
            props.update(state="draft",review_note="",publication_note="")
            name=validate_model(data.get("name",previous.display_name),
                                props,previous.schema_version.json_schema)
            reviewer=None;reviewed_at=None
            event="revised"
        else:
            if action=="submit":
                if set(data)!={"expected_revision"} or previous.properties["state"]!="draft":
                    raise InvalidRecommendation("Only an unchanged draft can be submitted")
                props=copy.deepcopy(previous.properties)
                props["state"]="in_review"
                reviewer=None;reviewed_at=None;event="submitted"
            elif action=="publish":
                if set(data)!={"expected_revision","review_note"} or previous.properties["state"]!="in_review":
                    raise InvalidRecommendation("Only a submitted revision can be reviewed/published")
                note=data.get("review_note")
                if not isinstance(note,str) or not note.strip() or len(note)>10000:
                    raise InvalidRecommendation("Reviewer justification required")
                props=copy.deepcopy(previous.properties)
                props.update(state="published",review_note=note.strip(),
                             publication_note="Approved by one authorized reviewer")
                reviewer=actor;reviewed_at=timezone.now();event="published"
            elif action=="unpublish":
                if set(data)!={"expected_revision","review_note"}:
                    raise InvalidRecommendation("Unpublication requires one explicit review note")
                note=data.get("review_note")
                if not isinstance(note,str) or not note.strip() or len(note)>10000:
                    raise InvalidRecommendation("Unpublication justification required")
                if published_revision(item) is None:
                    raise InvalidRecommendation("No live publication exists to withdraw")
                props=copy.deepcopy(previous.properties)
                props.update(state="unpublished",review_note=note.strip(),
                             publication_note="Explicitly withdrawn")
                reviewer=actor;reviewed_at=timezone.now();event="unpublished"
            else:
                raise InvalidRecommendation("Unknown recommendation action")
            inputs=_inputs({},old);name=previous.display_name
        rev=CatalogRevision.objects.create(
            item=item,number=previous.number+1,schema_version=previous.schema_version,
            display_name=name,properties=props,created_by=actor)
        _write_snapshot(rev,inputs,reviewer,reviewed_at)
        item.current_revision=rev;item.save(update_fields=["current_revision"])
        record_catalog_event(item=item,revision=rev,actor=actor,action=event)
        return item


def published_revision(item):
    """Visible until explicit withdrawal, including during later editing/review."""
    latest=CatalogRevision.objects.filter(item=item,properties__state__in=[
        "published","unpublished"]).order_by("-number").first()
    if latest is None or latest.properties["state"]!="published":
        return None
    return latest


def visible_revision(item,reader):
    return published_revision(item) if reader else item.current_revision


def _new_evidence(item,revision,snap):
    # Immutable accepted/failed observations after publication are never
    # auto-included in the recommendation, auto-published or relabeled.
    if not revision or revision.properties.get("state")!="published":
        return {"review_needed":False,"reason":None,"new_run_ids":[],
                "contradictory_run_ids":[]}
    cited=set(snap.run_pins.values_list("run_id",flat=True))
    records=BenchmarkRun.objects.filter(
        solution=snap.solution,
        session__case_pin__test_case__task=snap.task,
        created_at__gt=revision.created_at,
    ).order_by("created_at","id")[:101]
    newer=[r for r in records if r.pk not in cited]
    return {
        "review_needed":bool(newer),
        "reason":"new_measured_evidence" if newer else None,
        "new_run_ids":[r.public_id for r in newer[:100]],
        "contradictory_run_ids":[r.public_id for r in newer[:100] if r.outcome=="failed"],
    }


def serialize(item,rev=None,reader=False):
    rev=rev or visible_revision(item,reader)
    if rev is None:return None
    if reader:
        public=published_revision(item)
        if public is None or rev.properties["state"]!="published" or rev.number>public.number:
            return None
    snap=RecommendationSnapshot.objects.select_related(
        "task__item","solution__item","evaluation__revision__item","reviewed_by").get(revision=rev)
    pinned=list(snap.run_pins.select_related("run__session__method_definition").order_by("id"))
    links=[]
    for entry in pinned:
        run=entry.run
        links.append({
            "id":run.public_id,"uuid":str(run.pk),"kind":"individual",
            "outcome":run.outcome,"metrics":run.metrics,
            "method_id":str(run.session.method_definition_id),
            "experimental_method_version":run.session.method_definition.version,
            "evidence":[{"id":str(p.evidence_id),"sha256":p.evidence.blob_id}
                        for p in run.evidence_pins.select_related("evidence").order_by("id")],
        })
    alert=_new_evidence(item,rev,snap)
    return {
        "id":item.public_id,"revision":f"r{rev.number:03d}","revision_id":str(rev.pk),
        "name":rev.display_name,"properties":rev.properties,
        "state":rev.properties["state"],"evidence_class":"recommendation",
        "task_id":snap.task.item.public_id,"task_revision_id":str(snap.task_revision_id),
        "solution_id":snap.solution.item.public_id,
        "solution_revision_id":str(snap.solution_revision_id),
        "evaluation_id":snap.evaluation.revision.item.public_id if snap.evaluation else None,
        "evaluation_revision":f"r{snap.evaluation.revision.number:03d}" if snap.evaluation else None,
        "evaluation_revision_id":str(snap.evaluation_id) if snap.evaluation else None,
        "run_refs":links,"reviewed_by":snap.reviewed_by.get_username() if snap.reviewed_by else None,
        "reviewed_at":snap.reviewed_at.isoformat() if snap.reviewed_at else None,
        "created_by":rev.created_by.get_username(),
        "created_at":rev.created_at.isoformat(),
        **alert,
    }


def list_records(actor,task_id=None,solution_id=None):
    reader=not (actor.has_perm("auth.business_write") or
                actor.has_perm("auth.publication_review"))
    rows=CatalogItem.objects.filter(type_slug=KIND).select_related(
        "current_revision__created_by").order_by("created_at","public_id")
    items=[]
    for item in rows[:501]:
        payload=serialize(item,reader=reader)
        if payload is None:continue
        if task_id and payload["task_id"]!=task_id:continue
        if solution_id and payload["solution_id"]!=solution_id:continue
        items.append(payload)
    if len(items)>500:raise InvalidRecommendation("Too many recommendations; narrow filters")
    return items
