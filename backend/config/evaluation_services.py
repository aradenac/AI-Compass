"""PLAT-21: immutable, attributable interpretations over exact original measured runs.

Evaluations never create scores or mutate source Run, Forecast or Solution entities.
"""
import copy
import json

from django.db import IntegrityError,transaction

from .activity_services import record_catalog_event
from .catalog_compat import compatibility_for_revision
from .catalog_ids import new_public_id
from .catalog_schemas import validate_model,InvalidModel
from .catalog_services import RevisionConflict,SchemaWriteBlocked,ExhaustedIds
from .models import (CatalogItem,CatalogRevision,ObjectTypeVersion,EvaluationSnapshot,
                     EvaluationIndividualRunPin,EvaluationCompositeRunPin,
                     BenchmarkRun,CompositeBenchmarkRun)

ALLOWED_METRICS=("quality_score","information_utility_score","cost_eur",
                 "tokens_total","human_total_minutes","interaction_agent_minutes")
MAX_RUNS=40


class InvalidEvaluation(ValueError):
    pass


def _method(version):
    if type(version) is not int or version!=1:
        raise InvalidEvaluation("Only supported scoring method version 1 is available")
    row=ObjectTypeVersion.objects.filter(type_slug="evaluation_scoring_method",version=version).first()
    if row is None or row.json_schema.get("aggregation")!="none":
        raise InvalidEvaluation("Unsupported evaluation scoring descriptor")
    return row


def _config(config):
    if not isinstance(config,dict):
        raise InvalidEvaluation("scoring_config must be a JSON object")
    if set(config)-{"selected_metrics","comparison_basis","extensions"}:
        raise InvalidEvaluation("Unknown scoring configuration keys")
    selected=config.get("selected_metrics",list(ALLOWED_METRICS))
    if (not isinstance(selected,list) or not selected or len(selected)>len(ALLOWED_METRICS)
            or len(set(str(x) for x in selected))!=len(selected)
            or any(x not in ALLOWED_METRICS for x in selected)):
        raise InvalidEvaluation("Select distinct supported measured metric names")
    basis=config.get("comparison_basis","descriptive_only")
    if basis!="descriptive_only":
        raise InvalidEvaluation("Only descriptive evaluation is implemented (no scoring algorithm)")
    ext=config.get("extensions",{})
    if not isinstance(ext,dict):
        raise InvalidEvaluation("Extensions must be an object")
    candidate={"selected_metrics":selected,"comparison_basis":basis,"extensions":copy.deepcopy(ext)}
    if len(json.dumps(candidate,allow_nan=False,ensure_ascii=False))>12000:
        raise InvalidEvaluation("Scoring config too large")
    return candidate


def _read_inputs(ids):
    if not isinstance(ids,list) or not 1<=len(ids)<=MAX_RUNS:
        raise InvalidEvaluation("Select 1 to 40 exact measured Run IDs")
    if any(not isinstance(s,str) or not s.startswith("run-") or len(s)>120 for s in ids):
        raise InvalidEvaluation("Expected permanent Run IDs")
    if len(set(ids))!=len(ids):
        raise InvalidEvaluation("Duplicate Run IDs are not allowed")
    individual={r.public_id:r for r in BenchmarkRun.objects.select_related(
        "session__method_definition","session__case_pin__test_case__item",
        "session__campaign_snapshot__revision__item","solution__item","closing_checkpoint"
    ).filter(public_id__in=ids)}
    composite={r.public_id:r for r in CompositeBenchmarkRun.objects.select_related(
        "session__method_definition","session__case_pin__test_case__item",
        "session__campaign_snapshot__revision__item","framework","closing_checkpoint"
    ).filter(public_id__in=ids)}
    result=[]
    for order,identifier in enumerate(ids):
        if identifier in individual and identifier in composite:
            raise InvalidEvaluation("Ambiguous permanent Run ID; contact maintainer")
        row=individual.get(identifier) or composite.get(identifier)
        if row is None:raise InvalidEvaluation("One or more real Server Run IDs are missing")
        kind="individual" if identifier in individual else "composite"
        result.append((order,kind,row))
    return result


def _context(kind,run):
    session=run.session
    return {
        "kind":kind,"run_id":run.public_id,
        "run_uuid":str(run.pk),
        "closing_checkpoint":str(run.closing_checkpoint_id),
        "campaign_id":session.campaign_snapshot.revision.item.public_id,
        "campaign_revision_id":str(session.campaign_snapshot_id),
        "test_case_id":session.case_pin.test_case.item.public_id,
        "test_case_revision_id":str(session.case_pin.revision_id),
        "experimental_method_id":str(session.method_definition_id),
        "experimental_method_version":session.method_definition.version,
        "experimental_method_descriptor":copy.deepcopy(session.method_descriptor),
        "solution_id":run.solution.item.public_id if kind=="individual" else None,
        "framework_id":run.framework.public_id if kind=="composite" else None,
        "outcome":run.outcome,
        "metrics":copy.deepcopy(run.metrics),
        "provenance":copy.deepcopy(run.provenance),
    }


def _comparability(inputs,config):
    methods={(r.session.method_definition_id,
              json.dumps(r.session.method_descriptor,sort_keys=True)) for _,_,r in inputs}
    missing=set()
    for _,_,run in inputs:
        for field in config["selected_metrics"]:
            # Cost may be flat-rate or unknown, not a fake 0.
            if run.metrics.get(field) is None:missing.add(field)
    mixed=len(methods)>1
    unknown=bool(missing)
    status=("mixed_methods_and_incomplete_metrics" if mixed and unknown else
            "mixed_methods" if mixed else "incomplete_metrics" if unknown else "comparable")
    return status,sorted(missing)


def _properties(data,inputs,config,old=None):
    if not isinstance(data,dict) or set(data)-{"assessment","notes","limitations","extensions"}:
        raise InvalidEvaluation("Unsupported interpretation properties")
    props=copy.deepcopy(old or {})
    props.update(copy.deepcopy(data))
    props.setdefault("assessment","inconclusive")
    props.setdefault("notes","")
    props.setdefault("limitations","")
    props.setdefault("extensions",{})
    if props["assessment"] not in ("supported","unsupported","inconclusive"):
        raise InvalidEvaluation("Invalid assessment")
    for key,limit in (("notes",20000),("limitations",10000)):
        if not isinstance(props[key],str) or len(props[key])>limit:
            raise InvalidEvaluation(key+" must be bounded text")
    if not isinstance(props["extensions"],dict):
        raise InvalidEvaluation("extensions must be an object")
    status,missing=_comparability(inputs,config)
    props.update(comparability=status,missing_fields=missing,evidence_class="interpretation")
    try:
        if len(json.dumps(props,allow_nan=False,ensure_ascii=False))>40000:
            raise InvalidEvaluation("Interpretation too large")
    except (TypeError,ValueError) as error:
        raise InvalidEvaluation("Interpretation properties must be JSON") from error
    return props


def _pins(snapshot,inputs):
    EvaluationIndividualRunPin.objects.bulk_create([
        EvaluationIndividualRunPin(
            snapshot=snapshot,run=row,method_definition=row.session.method_definition,
            position=order,input_context=_context(kind,row))
        for order,kind,row in inputs if kind=="individual"])
    EvaluationCompositeRunPin.objects.bulk_create([
        EvaluationCompositeRunPin(
            snapshot=snapshot,run=row,method_definition=row.session.method_definition,
            position=order,input_context=_context(kind,row))
        for order,kind,row in inputs if kind=="composite"])


def _base(data,previous=None):
    if not isinstance(data,dict):
        raise InvalidEvaluation("Expected evaluation JSON object")
    allowed={"name","run_ids","scoring_method_version","scoring_config","properties"}
    if set(data)-allowed:raise InvalidEvaluation("Unsupported evaluation fields")
    if previous is None and "run_ids" not in data:
        raise InvalidEvaluation("run_ids are required")
    run_ids=data.get("run_ids") if "run_ids" in data else [p["run_id"] for p in _ordered(previous)]
    inputs=_read_inputs(run_ids)
    version=data.get("scoring_method_version",
                     previous.scoring_method.version if previous else 1)
    method=_method(version)
    config=_config(data.get("scoring_config",previous.scoring_config if previous else {}))
    return inputs,method,config


def create(*,actor,data):
    schema=ObjectTypeVersion.objects.filter(type_slug="evaluation",version=1).first()
    if schema is None:raise InvalidEvaluation("Missing evaluation schema")
    inputs,method,config=_base(data)
    props=_properties(data.get("properties",{}),inputs,config)
    name=validate_model(data.get("name"),props,schema.json_schema)
    for _ in range(12):
        candidate=new_public_id("evl")
        try:
            with transaction.atomic():
                item=CatalogItem.objects.create(type_slug="evaluation",public_id=candidate)
                revision=CatalogRevision.objects.create(
                    item=item,number=1,schema_version=schema,
                    display_name=name,properties=props,created_by=actor)
                snapshot=EvaluationSnapshot.objects.create(
                    revision=revision,scoring_method=method,scoring_config=config)
                _pins(snapshot,inputs)
                item.current_revision=revision
                item.save(update_fields=["current_revision"])
                record_catalog_event(item=item,revision=revision,actor=actor,action="created")
                return item
        except IntegrityError:
            if CatalogItem.objects.filter(public_id=candidate).exists():continue
            raise
    raise ExhaustedIds("Evaluation identity exhausted")


def _ordered(snapshot):
    individuals=[{"position":p.position,"run_id":p.run.public_id,"context":p.input_context,
                  "method_id":str(p.method_definition_id),"kind":"individual"}
                 for p in snapshot.individual_pins.select_related("run").all()]
    composites=[{"position":p.position,"run_id":p.run.public_id,"context":p.input_context,
                 "method_id":str(p.method_definition_id),"kind":"composite"}
                for p in snapshot.composite_pins.select_related("run").all()]
    return sorted(individuals+composites,key=lambda x:x["position"])


def revise(*,actor,identifier,expected_revision,data):
    with transaction.atomic():
        item=CatalogItem.objects.select_for_update(of=("self",)).select_related(
            "current_revision__schema_version").filter(type_slug="evaluation",
                                                        public_id=identifier).first()
        if item is None:raise InvalidEvaluation("Unknown Evaluation")
        old=item.current_revision
        if expected_revision!=f"r{old.number:03d}":
            raise RevisionConflict("Evaluation changed; reload")
        compat=compatibility_for_revision(item,old)
        if compat["read_only"] or old.schema_version.version!=1:
            raise SchemaWriteBlocked(compat)
        previous=EvaluationSnapshot.objects.get(revision=old)
        inputs,method,config=_base(data,previous)
        props=_properties(data.get("properties",{}),inputs,config,old.properties)
        name=validate_model(data.get("name",old.display_name),props,old.schema_version.json_schema)
        rev=CatalogRevision.objects.create(item=item,number=old.number+1,
            schema_version=old.schema_version,display_name=name,
            properties=props,created_by=actor)
        snap=EvaluationSnapshot.objects.create(
            revision=rev,scoring_method=method,scoring_config=config)
        _pins(snap,inputs)
        item.current_revision=rev
        item.save(update_fields=["current_revision"])
        record_catalog_event(item=item,revision=rev,actor=actor,action="revised")
        return item


def serialize(item,rev=None):
    rev=rev or item.current_revision
    snap=EvaluationSnapshot.objects.select_related("scoring_method").get(revision=rev)
    return {
        "id":item.public_id,"revision":f"r{rev.number:03d}","revision_id":str(rev.pk),
        "name":rev.display_name,"properties":rev.properties,"evidence_class":"interpretation",
        "scoring_method":{"id":str(snap.scoring_method_id),
                          "version":snap.scoring_method.version,
                          "descriptor":snap.scoring_method.json_schema},
        "scoring_config":snap.scoring_config,
        "inputs":_ordered(snap),
        "created_by":rev.created_by.get_username(),
        "created_at":rev.created_at.isoformat(),
    }
