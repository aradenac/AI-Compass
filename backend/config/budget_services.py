"""FUT-16: source-pinned, auditable pilot/rollout/active-capacity budgets.

Counts follow effective DAP workloads and current manual external entitlement
verification; consumption follows published Run meter observations or explicitly
qualified theoretical usage. Pricing reuses the FUT-05/FUT-09 line contract
including tier calculations, in native currencies. No purchasing, IAM or wallet.
"""
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from uuid import UUID

from django.db import IntegrityError, transaction

from .catalog_ids import new_public_id
from .models import (BudgetPlan, BudgetRevision, BenchmarkRun, CatalogItem,
                     CatalogRevision, DeploymentTarget, ForecastSnapshot)
from .opportunity_services import _profile, _forecast, candidates
from .workload_services import effective
from .deployment_services import status as deployment_status
from .publication_services import effective_ids
from .run_lifecycle_services import state as run_state
from .run_cost_services import _pins as run_pins, _tiers, decimal as meter_decimal
from .pricing_services import readiness

ALGORITHM = "dap-resource-v1"
MAX_ITEMS = 30
MAX_RUNS = 250
D0 = Decimal("0")


class InvalidBudget(ValueError):
    pass


class StaleBudget(InvalidBudget):
    pass


def num(value, name, top="1000000000000"):
    try:
        n = meter_decimal(value, name)
    except ValueError as exc:
        raise InvalidBudget(str(exc)) from exc
    if n > Decimal(top):
        raise InvalidBudget(name + " exceeds capacity bounds")
    return n


def fmt(n):
    return format(n.normalize(), "f")


def cash(n):
    return format(n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def months_for(period, months):
    if period in ("month", "seat_month"):
        return Decimal(months)
    if period in ("year", "seat_year"):
        return Decimal((months + 11) // 12)
    if period == "one_off":
        return Decimal(1)
    raise InvalidBudget("Unknown pinned fixed-charge period")


def _inputs(data):
    if not isinstance(data, dict) or set(data) != {"profile_id", "plan"}:
        raise InvalidBudget("Select exactly profile_id and plan")
    profile = _profile(data["profile_id"])
    plan = data["plan"]
    if not isinstance(plan, dict) or set(plan) - {
            "name", "start_date", "period_months", "margin_pct",
            "include_active", "items"}:
        raise InvalidBudget("Unknown resource plan field")
    name = plan.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
        raise InvalidBudget("Plan needs a 1..160-character name")
    start = plan.get("start_date", date.today().isoformat())
    if not isinstance(start, str) or len(start) != 10:
        raise InvalidBudget("Explicit YYYY-MM-DD start date required")
    try:
        date.fromisoformat(start)
    except ValueError as exc:
        raise InvalidBudget("Invalid start_date") from exc
    months = plan.get("period_months", 3)
    if type(months) is not int or not 1 <= months <= 24:
        raise InvalidBudget("Budget period must be 1..24 months")
    margin = num(plan.get("margin_pct", "0"), "margin_pct", "200")
    active = plan.get("include_active", False)
    if type(active) is not bool:
        raise InvalidBudget("include_active must be boolean")
    items = plan.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise InvalidBudget("Select between 1 and 30 explicit candidates/targets")
    normalized, seen = [], set()
    for row in items:
        if not isinstance(row, dict) or row.get("purpose") not in ("pilot", "rollout"):
            raise InvalidBudget("Each item has pilot or rollout purpose")
        purpose = row["purpose"]
        allowed = ({"purpose", "task_id", "candidate_id", "pilot_headcount",
                    "offer_pins", "meter_overrides"} if purpose == "pilot" else
                   {"purpose", "target_id"})
        if set(row) - allowed:
            raise InvalidBudget("Unexpected input in " + purpose + " resource item")
        if purpose == "pilot":
            task, candidate, headcount = (row.get("task_id"),
                                           row.get("candidate_id"),
                                           row.get("pilot_headcount"))
            if not isinstance(task, str) or not task.startswith("tsk-"):
                raise InvalidBudget("Pilot requires a real Task")
            if not isinstance(candidate, str) or not candidate.startswith("fct-"):
                raise InvalidBudget("Pilot must select a theoretical Forecast")
            if type(headcount) is not int or not 1 <= headcount <= 100000:
                raise InvalidBudget("Pilot headcount must be a positive integer")
            if headcount > effective(profile)["headcount"]:
                raise InvalidBudget("Pilot headcount exceeds selected population")
            pins = row.get("offer_pins", [])
            if not isinstance(pins, list) or len(pins) > 16:
                raise InvalidBudget("Pilot offers must be bounded")
            for pin in pins:
                if not isinstance(pin, dict) or set(pin) != {
                        "source_key", "offer_id", "offer_revision_id"}:
                    raise InvalidBudget("A pilot price pin requires exact offer revision")
            override = row.get("meter_overrides", {})
            if not isinstance(override, dict) or len(override) > 16:
                raise InvalidBudget("Pilot assumptions must be source/meter keyed")
            for key, meters in override.items():
                if not isinstance(key, str) or not isinstance(meters, dict) or len(meters) > 24:
                    raise InvalidBudget("Invalid pilot source/meter assumptions")
                for meter, value in meters.items():
                    if not isinstance(meter, str):
                        raise InvalidBudget("Invalid meter")
                    num(value, "qualified meter assumption")
            entry = {"purpose": "pilot", "task_id": task,
                     "candidate_id": candidate, "pilot_headcount": headcount,
                     "offer_pins": pins, "meter_overrides": override}
            identity = task
        else:
            target_id = row.get("target_id")
            if not isinstance(target_id, str) or not target_id.startswith("dpt-"):
                raise InvalidBudget("Rollout needs a deliberately selected target")
            target = DeploymentTarget.objects.filter(public_id=target_id,
                                                      population=profile).first()
            if not target or target.kind != "benchmark":
                raise InvalidBudget("Rollout requires a measured target in this population")
            entry = {"purpose": "rollout", "target_id": target_id}
            identity = target.task.item.public_id
        if identity in seen:
            raise InvalidBudget("Same Task cannot be funded twice in one plan")
        seen.add(identity)
        normalized.append(entry)
    if len(json.dumps(plan, ensure_ascii=False, allow_nan=False)) > 24000:
        raise InvalidBudget("Resource request too large")
    return profile, {"name": name.strip(), "start_date": start,
        "period_months": months, "margin_pct": fmt(margin),
        "include_active": active, "items": normalized}


def _source(item):
    """Resolve CURRENT published facts, pin their original immutable versions."""
    if item["purpose"] == "pilot":
        forecast = _forecast(item["candidate_id"], item["task_id"])
        if forecast is None:
            raise InvalidBudget("Forecast must remain published with valid watch sources")
        snap = forecast["snap"]
        components = {"root:" + k: (getattr(snap, k), getattr(snap, k + "_revision_id"))
                      for k in ("model", "provider", "harness")}
        pins = []
        seen = set()
        for selection in item["offer_pins"]:
            key = selection["source_key"]
            if key not in components or key in seen:
                raise InvalidBudget("Unmatched or duplicate pilot billable source")
            seen.add(key)
            offer = CatalogItem.objects.filter(
                public_id=selection["offer_id"], type_slug="pricing_offer").first()
            try:
                uid = UUID(selection["offer_revision_id"])
            except (TypeError, ValueError, AttributeError) as exc:
                raise InvalidBudget("Invalid pinned pricing revision ID") from exc
            rev = CatalogRevision.objects.filter(pk=uid, item=offer).first() if offer else None
            if not rev or rev.properties.get("component_id") != components[key][0].public_id:
                raise InvalidBudget("Offer revision does not price the pinned component")
            pins.append((key, offer, rev))
        source = forecast["ref"]
        forecast_metrics = forecast["metrics"]
        # The Forecast's 'tokens' is a total, NEVER a fabricated split.
        observations = item["meter_overrides"]
        maturity = "forecast_qualified_manual_usage" if observations else "forecast_no_exact_meters"
        return components, pins, observations, source, maturity, forecast_metrics
    target = DeploymentTarget.objects.select_related(
        "population", "task__item", "candidate").get(public_id=item["target_id"])
    if (target.kind != "benchmark" or target.population_id is None or
            target.candidate.type_slug != "solution"):
        raise InvalidBudget("No valid measured deployment target")
    dep = deployment_status(target, private=False)
    if dep["status"] != "selected":
        raise InvalidBudget("Retired target cannot start a new rollout budget")
    task_id = target.task.item.public_id
    run_ids = effective_ids(kind="individual")
    if len(run_ids) > MAX_RUNS:
        raise InvalidBudget("Measured corpus exceeds bounded budget query")
    runs = list(BenchmarkRun.objects.filter(
        public_id__in=run_ids, solution__item=target.candidate,
        session__case_pin__test_case__task=target.task
    ).select_related("session__individual_setup", "session__campaign_snapshot").order_by("public_id"))
    if not runs or len(runs) > MAX_RUNS:
        raise InvalidBudget("Rollout requires a published measured Run")
    states = [run_state(r) for r in runs]
    if any(s["status"] != "active" or s["outcome"] != "accepted" for s in states):
        raise InvalidBudget("Withdrawn/rejected measured evidence is not billable evidence")
    comparable = {(str(r.session.case_pin.test_case_id),
                   str(r.session.method_definition_id),
                   json.dumps(r.session.method_descriptor, sort_keys=True))
                  for r in runs}
    if len(comparable) != 1:
        raise InvalidBudget("Incomparable Test Cases cannot share meter estimates")
    ref_pins, reading = None, []
    for r in runs:
        chosen = run_pins(r.session)
        if chosen is None:
            chosen = []
        pin_tuple = [(p.source_key, p.offer.public_id, str(p.offer_revision_id))
                     for p in chosen]
        if ref_pins is None:
            ref_pins = pin_tuple
        elif pin_tuple != ref_pins:
            raise InvalidBudget("Incompatible measured pricing contracts; choose comparable Runs")
        reading.append(r.closing_checkpoint.state.get("metering", {}))
    pins = [(p.source_key, p.offer, p.offer_revision) for p in run_pins(runs[0].session) or []]
    components = {"root:" + k: (getattr(runs[0].session.individual_setup, k),
                 getattr(runs[0].session.individual_setup, k + "_revision_id"))
                  for k in ("model", "provider", "harness")}
    # For a measured series every required meter must be observed in ALL Runs.
    meter_keys = {(k, m) for obs in reading for k, v in obs.items() for m in v}
    averages = {}
    for key, meter in meter_keys:
        values = [v.get(key, {}).get(meter) for v in reading]
        if all(x is not None for x in values):
            averages.setdefault(key, {})[meter] = fmt(
                sum(num(x, "observed meter") for x in values) / Decimal(len(values)))
    source = {"kind": "measured", "target_id": target.public_id,
              "target_revision_id": dep["revision_id"],
              "runs": [{"id": r.public_id, "revision_id": s["revision_id"]}
                       for r, s in zip(runs, states)]}
    return components, pins, averages, source, "published_measured_usage", {}


def _line_prices(buckets, money_totals, gaps, months):
    quantities, charges = [], []
    for key, entry in sorted(buckets.items()):
        prop, line = entry["properties"], entry["line"]
        amount = entry["quantity"]
        seats = entry["seats"]
        currency = prop["currency"]
        result = None
        if line["charge_type"] == "variable":
            if amount is None:
                gaps.append("unmeasured:" + entry["source"] + "/" + line["meter"])
            elif line.get("conditions"):
                gaps.append("conditional_tariff:" + entry["source"] + "/" + line["charge_id"])
            elif line.get("rate") is None and line["family"] != "tiered":
                gaps.append("negotiated_tariff:" + entry["source"] + "/" + line["charge_id"])
            else:
                try:
                    result = (_tiers(amount, line) if line["family"] == "tiered" else
                              amount / num(line["unit_size"], "price unit size") *
                              num(line["rate"], "price rate"))
                except ValueError as exc:
                    gaps.append("unpriceable:" + str(exc))
            quantities.append({"billing_owner": prop["billing_owner"],
                "offer_id": entry["offer_id"],
                "offer_revision_id": entry["offer_revision_id"],
                "source_key": entry["source"], "charge_id": line["charge_id"],
                "meter": line["meter"], "credit_namespace": line.get("provider_credit_namespace"),
                "quantity": fmt(amount) if amount is not None else None,
                "unit": line["meter"], "evidence": entry["evidence"]})
        elif line["charge_type"] == "fixed":
            if line.get("conditions"):
                gaps.append("conditional_fixed_tariff:" + entry["source"])
            else:
                count = months_for(line["period"], months)
                if line["period"].startswith("seat_"):
                    count *= seats
                result = num(line["rate"], "fixed tariff") * count
        elif line["charge_type"] == "unknown":
            gaps.append("unknown_tariff:" + entry["source"] + "/" + line["charge_id"])
        if result is not None:
            money_totals[currency][line["charge_type"]] += result
        if line["charge_type"] in ("variable", "fixed", "unknown"):
            charges.append({"source_key": entry["source"],
                "billing_owner": prop["billing_owner"], "offer_id": entry["offer_id"],
                "offer_revision_id": entry["offer_revision_id"],
                "charge_id": line["charge_id"], "charge_type": line["charge_type"],
                "native_currency": currency, "amount": cash(result) if result is not None else None,
                "meter": line.get("meter"), "period": line.get("period"),
                "seats": seats if line["charge_type"] == "fixed" else None,
                "source": entry["evidence"]})
    return quantities, charges


def project(profile, plan):
    """Live current eligibility; old BudgetRevision.projection remains frozen."""
    workload = effective(profile)
    by_task = {r["task_id"]: r for r in workload["workloads"]}
    headcount = workload["headcount"]
    months, margin = plan["period_months"], Decimal(plan["margin_pct"])
    buckets = {}
    segments, gaps = [], []
    tasks = set()
    for item in plan["items"]:
        if item["purpose"] == "pilot":
            task_id = item["task_id"]
            person_count = item["pilot_headcount"]
            allocations = [("pilot", person_count)]
            target = None
        else:
            target = DeploymentTarget.objects.select_related(
                "population", "task__item", "candidate").get(public_id=item["target_id"])
            if target.population_id != profile.pk:
                raise InvalidBudget("Foreign population target")
            task_id = target.task.item.public_id
            latest = deployment_status(target, private=False)
            ready, activated = latest["ready_count"], latest["activated_count"]
            # Only NOT access-ready people need rollout entitlements. Active
            # capacity is separate and never counted in rollout.
            allocations = [("rollout", headcount - ready)]
            if plan["include_active"]:
                allocations.append(("active", activated))
        if task_id in tasks:
            raise InvalidBudget("Duplicate Task in plan")
        tasks.add(task_id)
        work = by_task.get(task_id)
        if not work or work["status"] not in ("resolved", "zero") or work["overlaps_ancestor_task"]:
            gaps.append("unresolved_or_overlapping_workload:" + task_id)
            frequency = None
        else:
            frequency = num(work["annual_occurrences"], "annual Task frequency")
        components, pins, observations, source, maturity, metrics = _source(item)
        selected = {k for k, _, _ in pins}
        for key in components:
            if key not in selected:
                gaps.append("unselected_offer:" + task_id + "/" + key)
        for purpose, count in allocations:
            base = (frequency * Decimal(count) * Decimal(months) /
                    Decimal(12) * (Decimal(1) + margin / Decimal(100))
                    if frequency is not None else None)
            segments.append({"purpose": purpose, "task_id": task_id,
                "candidate_id": item.get("candidate_id", target.candidate.public_id if target else None),
                "headcount": count, "estimated_task_occurrences": fmt(base) if base is not None else None,
                "evidence_class": maturity, "source": source,
                "profile_revision_id": workload["revision_id"],
                "workload_sources": work.get("sources") if work else [],
                "distribution": "uniform_monthly_assumption_not_observed",
                "pilot_total_tokens_hint": metrics.get("tokens") if item["purpose"] == "pilot" else None})
            for key, offer, rev in pins:
                ready = readiness(rev, as_of=plan["start_date"])
                if not ready["complete"]:
                    gaps.extend("offer:" + task_id + "/" + key + ":" + x for x in ready["reasons"])
                for line in rev.properties.get("lines", []):
                    if line["charge_type"] == "free":
                        continue
                    namespace = line.get("provider_credit_namespace") if line.get("meter") == "provider_credits" else None
                    # Deduplicate one invoice for cumulative Model+Provider
                    # references and across Tasks; never deduplicate different
                    # participant namespaces into generic shared credits.
                    invoice = (rev.properties["billing_owner"], offer.public_id,
                               str(rev.pk), line["charge_id"], namespace or "")
                    same_owner = (rev.properties["billing_owner"], line["charge_id"],
                                  namespace or "")
                    for old_key in buckets:
                        if (old_key[0], old_key[3], old_key[4]) == same_owner and old_key != invoice:
                            gaps.append("ambiguous_overlapping_invoice:" + line["charge_id"])
                    entry = buckets.setdefault(invoice, {"properties": rev.properties,
                        "offer_id": offer.public_id, "offer_revision_id": str(rev.pk),
                        "line": line, "quantity": D0 if base is not None else None,
                        "seats": 0, "source": key, "evidence": []})
                    if line["charge_type"] == "fixed":
                        # Seat counts across distinct non-overlapping Tasks of
                        # the SAME population are capacity, not summed invoices.
                        entry["seats"] = max(entry["seats"], count)
                    elif line["charge_type"] == "variable":
                        val = observations.get(key, {}).get(line["meter"])
                        if base is None or val is None:
                            entry["quantity"] = None
                        elif entry["quantity"] is not None:
                            entry["quantity"] += base * num(val, "per-Task meter observation")
                    entry["evidence"].append({"task_id": task_id, "purpose": purpose,
                        "source": source, "headcount": count,
                        "meter_source": ("explicit_qualified_assumption" if item["purpose"] == "pilot"
                                         else "published_run_metering")})
        # Overlap between explicit child and ancestor Task selections is not
        # safe even when they have different configurations.
    from .models import TaskNode
    parents = {t.item.public_id: t.parent for t in TaskNode.objects.select_related("item", "parent__item")}
    for task in tasks:
        current = parents.get(task)
        while current:
            if current.item.public_id in tasks:
                gaps.append("parent_child_double_count:" + task)
            current = current.parent
    money = defaultdict(lambda: {"fixed": D0, "variable": D0})
    quantities, charges = _line_prices(buckets, money, gaps, months)
    amounts = {currency: {"fixed": cash(value["fixed"]), "variable": cash(value["variable"]),
                          "total": cash(value["fixed"] + value["variable"])}
               for currency, value in sorted(money.items())}
    return {"algorithm": ALGORITHM, "purpose": "decision_support_not_invoice",
        "plan_name": plan["name"], "start_date": plan["start_date"],
        "period_months": months, "margin_pct": plan["margin_pct"],
        "source_freshness": "current_eligibility_and_published_meters",
        "profile_id": profile.public_id, "profile_revision_id": workload["revision_id"],
        "segments": segments, "quantities": quantities, "charges": charges,
        "amounts_by_native_currency": amounts, "gaps": sorted(set(gaps)),
        "ready_for_request": not gaps, "no_fx_wallet_iam_or_procurement": True,
        "sensitive_person_rates_excluded": True}


def preview(data):
    profile, plan = _inputs(data)
    return project(profile, plan)


@transaction.atomic
def create(actor, data):
    profile, plan = _inputs(data)
    frozen = project(profile, plan)
    for _ in range(12):
        ident = new_public_id("bdg")
        try:
            with transaction.atomic():
                budget = BudgetPlan.objects.create(
                    public_id=ident, profile=profile, created_by=actor)
                BudgetRevision.objects.create(
                    budget=budget, number=1, assumptions=plan,
                    projection=frozen, created_by=actor)
                return budget
        except IntegrityError:
            if BudgetPlan.objects.filter(public_id=ident).exists():
                continue
            raise
    raise InvalidBudget("Unable to reserve resource budget identity")


@transaction.atomic
def revise(actor, budget, expected_revision, plan):
    item = BudgetPlan.objects.select_for_update().get(pk=budget.pk)
    old = item.revisions.order_by("-number").first()
    if expected_revision != "r%03d" % old.number:
        raise StaleBudget("Budget changed; reload before revising")
    _, normalized = _inputs({"profile_id": item.profile.public_id, "plan": plan})
    projection = project(item.profile, normalized)
    BudgetRevision.objects.create(
        budget=item, number=old.number + 1, assumptions=normalized,
        projection=projection, created_by=actor)
    return item


def serialize(budget, revision=None, current=True):
    rev = revision or budget.revisions.order_by("-number").first()
    doc = {"id": budget.public_id, "profile_id": budget.profile.public_id,
        "revision": "r%03d" % rev.number, "revision_id": str(rev.pk),
        "created_at": rev.created_at.isoformat(),
        "created_by": rev.created_by.get_username(),
        "plan": rev.assumptions, "snapshot": rev.projection,
        "source_frozen": True}
    if current and revision is None:
        try:
            now = project(budget.profile, rev.assumptions)
            doc["current"] = now
            doc["source_changed"] = now != rev.projection
        except InvalidBudget as exc:
            doc["current"] = None
            doc["source_changed"] = True
            doc["current_unavailable_reason"] = str(exc)
    return doc
