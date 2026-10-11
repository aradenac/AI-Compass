"""FUT-13: versioned and source-reconstructible prospective DAP economics.

No fabricated productivity, activation, access rights, forecasting certainty,
tariff or currency conversion. One explicitly chosen alternative per Task.
All source values and snapshots are privileged planning-only records.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json

from django.db import IntegrityError, transaction

from .catalog_ids import new_public_id
from .models import (BenchmarkRun, CatalogItem, ForecastSnapshot, OpportunityScenario,
                     OpportunitySnapshot, WorkloadProfile)
from .publication_services import effective_ids
from .run_lifecycle_services import state as run_state
from .workload_services import effective

ALGORITHM = "dap-opportunity-v1"
D0 = Decimal("0")
D100 = Decimal("100")
CENT = Decimal("0.01")
MAX_CHOICES = 100
MAX_RUNS = 500


class InvalidOpportunity(ValueError):
    pass


class StaleOpportunity(InvalidOpportunity):
    pass


def decimal(value, label, maximum="1000000000000"):
    if isinstance(value, bool) or not isinstance(value,(str,int,Decimal)):
        raise InvalidOpportunity(label+" must be an explicit finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidOpportunity(label+" is not decimal") from exc
    if not result.is_finite() or result < 0 or result > Decimal(maximum):
        raise InvalidOpportunity(label+" out of bounds")
    return result


def money(value):
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def _metric(value, label):
    if value is None:
        return None
    try:
        return decimal(str(value),label)
    except InvalidOpportunity:
        return None


def _inputs(data):
    if not isinstance(data,dict) or set(data)!={"name","choices","benchmark_weight"}:
        raise InvalidOpportunity("Scenario requires name, choices and explicit benchmark_weight")
    name=data["name"]
    if not isinstance(name,str) or not 1<=len(name.strip())<=160:
        raise InvalidOpportunity("Scenario name must be 1..160 characters")
    choices=data["choices"]
    if not isinstance(choices,list) or not 1<=len(choices)<=MAX_CHOICES:
        raise InvalidOpportunity("Select 1..100 explicit Task/configuration alternatives")
    ids=set()
    for c in choices:
        if not isinstance(c,dict) or set(c)-{"task_id","kind","candidate_id","forecast_id"}:
            raise InvalidOpportunity("Unknown choice field")
        if set(c)<{"task_id","kind","candidate_id"}:
            raise InvalidOpportunity("Task, candidate type and ID are required")
        task=c["task_id"]
        kind=c["kind"]
        ident=c["candidate_id"]
        if not isinstance(task,str) or not task.startswith("tsk-") or len(task)>120:
            raise InvalidOpportunity("Expected real Task ID")
        if kind not in ("benchmark","forecast") or not isinstance(ident,str) or len(ident)>120:
            raise InvalidOpportunity("Invalid candidate kind or ID")
        if not ident.startswith("sol-" if kind=="benchmark" else "frc-"):
            # The forecast HRID prefix is resolved by the persisted record too.
            if kind=="benchmark" or not ident.startswith("for-"):
                raise InvalidOpportunity("Candidate ID must match its evidence class")
        if "forecast_id" in c and (kind!="benchmark" or
                not isinstance(c["forecast_id"],str) or not
                c["forecast_id"].startswith(("frc-","for-"))):
            raise InvalidOpportunity("Only measured candidates may link a theoretical Forecast")
        if task in ids:
            raise InvalidOpportunity("Each Task may have exactly one scenario candidate")
        ids.add(task)
    w=decimal(data["benchmark_weight"],"benchmark_weight",maximum="1")
    if w<=Decimal("0.5") or w>=D100/D100:
        raise InvalidOpportunity("Choose a benchmark weight > 0.5 and < 1")
    if len(json.dumps(data,allow_nan=False,ensure_ascii=False))>20000:
        raise InvalidOpportunity("Scenario selection is too large")
    return {"name":name.strip(),"choices":choices,"benchmark_weight":str(w)}


def _forecast(ident, task_id):
    item=CatalogItem.objects.select_related("current_revision").filter(
        type_slug="forecast", public_id=ident).first()
    if not item or not item.current_revision_id or (
            item.current_revision.properties.get("status")!="published"):
        return None
    snap=ForecastSnapshot.objects.filter(
        revision=item.current_revision,task__item__public_id=task_id).select_related(
            "revision","model","provider","harness").first()
    if not snap:
        return None
    rev=item.current_revision
    return {"item":item,"snap":snap,
            "ref":{"kind":"forecast","id":ident,"revision_id":str(rev.pk),
                   "revision":f"r{rev.number:03d}", "task_id":task_id,
                   "task_revision_id":str(snap.task_revision_id)},
            "metrics":rev.properties.get("predicted_metrics",{}),
            "properties":rev.properties}


def _forecast_values(record, baseline):
    if record is None:
        return None, ["forecast_unpublished_revoked_or_not_linked"]
    metrics=record["metrics"]
    expected=_metric(metrics.get("human_minutes"),"forecast human minutes")
    cost=_metric(metrics.get("ai_cost_eur"),"forecast marginal AI cost")
    chance=_metric(metrics.get("acceptance_probability"),"forecast acceptance probability")
    missing=[]
    if expected is None:missing.append("forecast_human_minutes_missing")
    if cost is None:missing.append("forecast_usage_cost_missing")
    if chance is None or chance>D100:missing.append("forecast_acceptance_probability_missing")
    failed=None
    if chance is not None and chance<D100:
        failed=_metric(record["properties"].get("assumptions",{}).get(
            "failure_recovery_human_minutes"),"forecast failed recovery minutes")
        if failed is None:missing.append("forecast_failure_recovery_time_missing")
    if missing:return None,missing
    # An unsuccessful attempt consumes the full baseline AND stated recovery;
    # do not credit it with the successful assisted-time saving.
    p=chance/D100
    hours=p*(expected/Decimal(60))+(D100-chance)/D100*(baseline+failed/Decimal(60)
                                                       if failed is not None else baseline)
    return {"hours":hours,"cost":cost,"evidence":"theoretical",
            "source":record["ref"],
            "confidence":record["properties"].get("confidence","unknown"),
            "assumptions":{"acceptance_probability":str(chance),
                           "failed_recovery_minutes":str(failed) if failed is not None else None}},[]


def _measured(ident,task_id):
    ids=effective_ids(kind="individual")
    if len(ids)>MAX_RUNS:
        raise InvalidOpportunity("Published Run corpus exceeds bounded planning query")
    runs=list(BenchmarkRun.objects.filter(public_id__in=ids,
        solution__item__public_id=ident,
        session__case_pin__test_case__task__item__public_id=task_id).select_related(
            "session__case_pin__test_case__item", "session__method_definition",
            "session__individual_setup", "solution__item").order_by("public_id"))
    if not runs:return None,["no_current_published_run_for_task_solution"]
    if len(runs)>MAX_RUNS:
        raise InvalidOpportunity("Published candidate corpus too large")
    states=[(run,run_state(run)) for run in runs]
    if any(x["status"]!="active" for _,x in states):
        return None,["withdrawn_run_in_evidence"]
    if any(x["outcome"]!="accepted" for _,x in states):
        return None,["failed_or_conflicting_DOD_no_positive_gain"]
    # No arbitrary aggregation of incomparable Test Cases or methods.
    comparable={(str(r.session.case_pin.test_case_id),
                 str(r.session.method_definition_id),
                 json.dumps(r.session.method_descriptor,sort_keys=True)) for r,_ in states}
    if len(comparable)!=1:
        return None,["multiple_incomparable_methods_or_test_cases"]
    minutes=[_metric(x["metrics"].get("human_total_minutes"),"observed human minutes")
             for _,x in states]
    costs=[_metric(x["metrics"].get("cost_eur"),"observed variable reference cost")
           for _,x in states]
    if any(v is None for v in minutes):
        return None,["measured_human_effort_missing"]
    if any(v is None for v in costs):
        return None,["measured_marginal_tariff_or_cost_missing"]
    n=Decimal(len(states))
    m=sum(minutes,D0)/n
    c=sum(costs,D0)/n
    refs=[{"kind":"measured","id":r.public_id,"revision":v["revision"],
           "revision_id":v["revision_id"],"task_id":task_id,
           "test_case_id":r.session.case_pin.test_case.item.public_id,
           "test_case_revision_id":str(r.session.case_pin.revision_id),
           "method_id":str(r.session.method_definition_id),
           "method_version":r.session.method_definition.version,
           "pricing_reference":"declared_run_marginal_cost_eur"}
          for r,v in states]
    pin=runs[0].session.individual_setup
    return {"hours":m/Decimal(60),"cost":c,"evidence":"measured",
            "run_refs":refs,"sample_size":len(refs),"pin":pin,
            "source":{"kind":"published_measured_solution","id":ident,
                      "run_revisions":refs},
            "confidence":"limited_case_coverage_not_a_quality_score"},[]


def _same_configuration(forecast,measured):
    if forecast is None or measured is None:return False
    a=forecast["snap"]
    b=measured["pin"]
    return all(getattr(a,k+"_revision_id")==getattr(b,k+"_revision_id")
               for k in ("model","provider","harness")) and a.configuration==b.settings


def _quantified(baseline, frequency, rate, assisted_hours, usage_cost):
    per=(baseline-assisted_hours)*rate-usage_cost
    return {"per_occurrence_eur":money(per),
            "annual_eur":money(per*frequency),
            "annual_occurrences":str(frequency),
            "baseline_human_hours":str(baseline),
            "assisted_human_hours":str(assisted_hours),
            "valuation_eur_per_hour":str(rate),
            "marginal_reference_ai_cost_eur":str(usage_cost),
            "formula":"annual_occurrences * ((baseline_hours - expected_assisted_hours) * hourly_rate_eur - variable_cost_eur)"}


def allocate_slices(per_occurrence, annual_per_person, headcount,
                    verified_headcount, kind):
    """A mathematical partition, NOT an authorization of deployment evidence.

    Production calls always pass verified_headcount=0 until FUT-15 supplies
    authenticated entitlement AND confirmed first-use source records.
    """
    if (type(headcount)!=int or type(verified_headcount)!=int or
            not 0<=verified_headcount<=headcount):
        raise InvalidOpportunity("Verified activation must be a bounded population subset")
    if kind not in ("measured","theoretical"):
        raise InvalidOpportunity("Only measured or theoretical source classes can be allocated")
    per=decimal(per_occurrence,"per occurrence reference value")
    frequency=decimal(annual_per_person,"annual person task frequency")
    annual=per*frequency
    return {
        "activated_potential_eur":money(annual*verified_headcount),
        "benchmarked_opportunity_eur":money(
            annual*(headcount-verified_headcount) if kind=="measured" else D0),
        "forecast_opportunity_eur":money(
            annual*(headcount-verified_headcount) if kind=="theoretical" else D0),
        "verified_headcount":verified_headcount,"remaining_headcount":headcount-verified_headcount,
    }


def project(profile, assumptions):
    """Every API read computes current effective evidence, not stale cache."""
    selection=_inputs(assumptions)
    workload=effective(profile)
    available={r["task_id"]:r for r in workload["workloads"]}
    rate_source=workload["hourly_rate_source"]
    rate=(_metric(rate_source["rate_eur"],"labor rate") if rate_source else None)
    headcount=workload["headcount"]
    cells=[]
    amounts={"activated_potential_eur":D0, "benchmarked_opportunity_eur":D0,
             "forecast_opportunity_eur":D0}
    missing_count=0
    for c in selection["choices"]:
        task_id=c["task_id"]
        wr=available.get(task_id)
        reasons=[]
        if not wr:reasons.append("task_not_in_selected_workload")
        else:
            if wr["status"] not in ("resolved","zero"):
                reasons.append("workload_"+wr["status"])
            if wr["overlaps_ancestor_task"]:
                reasons.append("overlapping_parent_descendant_workloads")
        if rate is None:reasons.append("labor_rate_unknown")
        base=_metric(wr["baseline_human_hours"],"baseline") if wr else None
        freq=_metric(wr["annual_occurrences"],"frequency") if wr else None
        if base is None:reasons.append("baseline_human_hours_unknown")
        if freq is None:reasons.append("annual_frequency_unknown")
        measured=None;forecast=None
        if c["kind"]=="benchmark":
            measured,errors=_measured(c["candidate_id"],task_id)
            reasons+=errors
            if c.get("forecast_id"):
                forecast=_forecast(c["forecast_id"],task_id)
                if not forecast:reasons.append("linked_forecast_not_currently_published")
        else:
            forecast=_forecast(c["candidate_id"],task_id)
            if not forecast:reasons.append("forecast_not_currently_published")
        reference=None
        measured_calc=None
        predicted_calc=None
        kind="measured" if c["kind"]=="benchmark" else "theoretical"
        if not reasons:
            if measured:
                measured_calc=_quantified(base,freq,rate,measured["hours"],measured["cost"])
                reference=(measured["hours"],measured["cost"])
            if forecast:
                expected,problems=_forecast_values(forecast,base)
                if problems:
                    # A linked optional forecast may be incomplete; the
                    # benchmark still yields a non-blended source-proven estimate.
                    if not measured:reasons+=problems
                else:
                    predicted_calc=_quantified(base,freq,rate,expected["hours"],expected["cost"])
                    if not measured:
                        reference=(expected["hours"],expected["cost"])
                    elif _same_configuration(forecast,measured):
                        w=Decimal(selection["benchmark_weight"])
                        reference=(w*measured["hours"]+(1-w)*expected["hours"],
                                   w*measured["cost"]+(1-w)*expected["cost"])
                    else:
                        reasons.append("forecast_not_comparable_to_measured_setup")
        value=None
        partition=None
        if not reasons and reference is not None:
            value=_quantified(base,freq*headcount,rate,*reference)
            # Internally use signed per-occurrence value for no hidden clipping.
            signed=(base-reference[0])*rate-reference[1]
            if signed < 0:
                # Negative values remain a separate, explicit loss line; they
                # are not labelled an opportunity or activated positive value.
                partition=None
            else:
                partition=allocate_slices(signed,freq,headcount,0,kind)
                for field in amounts:
                    amounts[field]+=Decimal(partition[field])
        else:
            missing_count+=1
        cells.append({
            "task_id":task_id,"candidate_id":c["candidate_id"],"kind":c["kind"],
            "evidence_class":kind,"measured_reference":measured["source"] if measured else None,
            "forecast_reference":forecast["ref"] if forecast else None,
            "measured_economics":measured_calc,"theoretical_economics":predicted_calc,
            "blended":bool(measured_calc and predicted_calc and
                            forecast and measured and _same_configuration(forecast,measured)),
            "confidence":(measured["confidence"] if measured else
                forecast["properties"].get("confidence") if forecast else "unknown"),
            "status":("unquantifiable" if reasons else
                      "negative_reference_gain" if partition is None else
                      "quantified_annual_potential"),
            "reasons":sorted(set(reasons)),"economic":value,
            "slices":partition,
            "source_workload":({"profile_id":profile.public_id,
                               "profile_revision_id":str(workload["revision_id"]),
                               "workload":wr,"rate_source":rate_source} if wr else None),
            "cost_basis":"pinned_run_declared_marginal_eur_or_published_forecast_estimate",
        })
    total=sum(amounts.values(),D0)
    return {"algorithm":ALGORITHM,"scenario_name":selection["name"],
            "profile_id":profile.public_id,
            "profile_revision_id":workload["revision_id"],
            "population_kind":profile.kind,"headcount":headcount,
            "benchmark_weight":selection["benchmark_weight"],
            "currency":"EUR", "period":"annual",
            "interpretation":"prospective_labor_value_not_realized_cash_savings",
            "activation_status":"unverified_no_FUT15_access_or_first_use_records",
            "aggregation":"positive_only_slices_negative_gains_reported_separately",
            "totals":{**{k:money(v) for k,v in amounts.items()},
                      "positive_modeled_total_eur":money(total)},
            "unquantifiable_count":missing_count,
            "negative_count":sum(c["status"]=="negative_reference_gain" for c in cells),
            "cells":cells,
            "source_freshness":"effective_published_read_time",
            "personal_rates_restricted":True}


def _profile(identifier):
    if not isinstance(identifier,str) or not identifier.startswith("wlp-"):
        raise InvalidOpportunity("Select one existing planning population")
    profile=WorkloadProfile.objects.filter(public_id=identifier).first()
    if profile is None:raise InvalidOpportunity("Unknown planning population")
    return profile


@transaction.atomic
def create(actor, data):
    if not isinstance(data,dict) or set(data)!={"profile_id","scenario"}:
        raise InvalidOpportunity("Profile and scenario are required")
    profile=_profile(data["profile_id"])
    assumptions=_inputs(data["scenario"])
    result=project(profile,assumptions)
    for _ in range(12):
        public_id=new_public_id("opp")
        try:
            with transaction.atomic():
                entry=OpportunityScenario.objects.create(profile=profile,public_id=public_id)
                OpportunitySnapshot.objects.create(
                    scenario=entry,number=1,assumptions=assumptions,
                    projection=result,created_by=actor)
                return entry
        except IntegrityError:
            if OpportunityScenario.objects.filter(public_id=public_id).exists():continue
            raise
    raise InvalidOpportunity("Cannot reserve planning scenario identity")


@transaction.atomic
def revise(actor, ident, expected, data):
    if not isinstance(data,dict) or set(data)!={"scenario"}:
        raise InvalidOpportunity("Only explicit scenario selections can be revised")
    item=OpportunityScenario.objects.select_for_update(of=("self",)).filter(
        public_id=ident).first()
    if item is None:raise InvalidOpportunity("Unknown opportunity scenario")
    prev=item.snapshots.order_by("-number").first()
    if expected != f"r{prev.number:03d}":
        raise StaleOpportunity("Scenario changed; reload before revising")
    assumptions=_inputs(data["scenario"])
    projection=project(item.profile,assumptions)
    OpportunitySnapshot.objects.create(
        scenario=item,number=prev.number+1,assumptions=assumptions,
        projection=projection,created_by=actor)
    return item


def serialize(item, *, current=False, revision=None):
    snap=revision or item.snapshots.order_by("-number").first()
    result={"id":item.public_id,"profile_id":item.profile.public_id,
            "revision":f"r{snap.number:03d}",
            "revision_id":str(snap.pk),
            "created_at":snap.created_at.isoformat(),"created_by":snap.created_by.get_username(),
            "scenario":snap.assumptions,"snapshot":snap.projection,
            "algorithm":snap.algorithm}
    if current:
        now=project(item.profile,snap.assumptions)
        result["current"]=now
        result["source_changed"]=now!=snap.projection
    return result
