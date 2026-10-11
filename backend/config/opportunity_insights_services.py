"""FUT-14: read-only Management Insights projection over FUT-13 economic authority.

The scenario's stored revision is historical truth; live cells are computed solely
via opportunity_services.project(). This module never stores or invents finance.
All endpoints must enforce auth.planning_view BEFORE querying protected sources.
"""
from collections import defaultdict
from decimal import Decimal
from django.utils import timezone

from .models import OpportunityScenario, TaskNode
from . import opportunity_services as core

ROW_LIMIT = 16
COLUMN_LIMIT = 12
TASK_MAX = 2000
ALTERNATIVE_LIMIT = 150

SLICES = ("activated_potential_eur", "benchmarked_opportunity_eur",
          "forecast_opportunity_eur")


def _scenario(identifier, profile):
    if not identifier:
        return None
    if not isinstance(identifier, str) or len(identifier) > 120 or not identifier.startswith("opp-"):
        raise core.InvalidOpportunity("Invalid scenario identity")
    scenario = OpportunityScenario.objects.filter(public_id=identifier, profile=profile).first()
    if scenario is None:
        raise core.InvalidOpportunity("Scenario is not owned by the selected population")
    return scenario


def _snapshot(scenario, revision):
    if not scenario:
        if revision is not None:
            raise core.InvalidOpportunity("A historical revision needs a saved scenario")
        return None
    if revision is None:
        return scenario.snapshots.order_by("-number").first()
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise core.InvalidOpportunity("Invalid scenario revision")
    snap = scenario.snapshots.filter(number=revision).first()
    if snap is None:
        raise core.InvalidOpportunity("Unknown original immutable scenario revision")
    return snap


def _task_nodes():
    nodes = list(TaskNode.objects.select_related("item__current_revision",
            "parent__item").order_by("position", "item__public_id")[:TASK_MAX + 1])
    if len(nodes) > TASK_MAX:
        raise core.InvalidOpportunity("Taxonomy exceeds bounded discovery limit")
    return [{
        "id": node.item.public_id,
        "name": node.item.current_revision.display_name,
        "revision_id": str(node.item.current_revision_id),
        "parent_id": node.parent.item.public_id if node.parent else None,
        "position": node.position,
    } for node in nodes]


def _slice_totals(projection):
    return {key: projection["totals"][key] for key in SLICES}


def _cell(task_id, candidate, result, chosen):
    if result is None:
        return None  # truly uncovered cell: no amount, no fake icon
    status = result["status"]
    economics = result.get("economic") or {}
    raw = economics.get("annual_eur")
    positive = status == "quantified_annual_potential" and raw is not None
    value = Decimal(raw) if raw is not None else None
    # One maturity/deployment icon only; intensity never encodes status.
    maturity = ("B" if result["evidence_class"] == "measured" else "F")
    if status == "unquantifiable":
        maturity = "?"
    return {
        "task_id": task_id, "candidate_id": candidate["candidate_id"],
        "kind": candidate["kind"], "selected": chosen,
        "status": status, "reason_codes": result["reasons"],
        "annual_eur": raw, "intensity_eur": str(value) if positive and value > 0 else None,
        "maturity": maturity, "evidence_class": result["evidence_class"],
        "coverage": result.get("measured_sample_size", 0),
        "confidence": result.get("confidence"), "calculation_available": raw is not None,
    }


def _safe_int(value, label):
    if isinstance(value, bool):
        raise core.InvalidOpportunity(label + " must be numeric")
    try:
        result = int(value)
        if str(result) != str(value):
            raise ValueError
        return result
    except (TypeError, ValueError) as exc:
        raise core.InvalidOpportunity("Invalid " + label) from exc


def heatmap(*, profile_id, scenario_id=None, revision=None,
            row_page=0, column_page=0, row_size=ROW_LIMIT, column_size=COLUMN_LIMIT):
    profile = core._profile(profile_id)
    row_page = _safe_int(row_page, "row page")
    column_page = _safe_int(column_page, "column page")
    row_size = _safe_int(row_size, "row size")
    column_size = _safe_int(column_size, "column size")
    if row_page < 0 or column_page < 0 or not 1 <= row_size <= ROW_LIMIT or not 1 <= column_size <= COLUMN_LIMIT:
        raise core.InvalidOpportunity("Out-of-range matrix page/window")
    scenario = _scenario(scenario_id, profile)
    snap = _snapshot(scenario, revision)
    is_historical = revision is not None
    # Frozen revisions contain only the original selected portfolio, not today's
    # global candidates or a back-filled historical comparison universe.
    suggestions = [] if is_historical else core.candidates()
    chosen = {c["task_id"]: c for c in snap.assumptions["choices"]} if snap else {}
    if is_historical:
        suggestions = [{
            "task_id": row["task_id"], "candidate_id": row["candidate_id"],
            "kind": row["kind"], "name": row["candidate_id"],
            "label": "Original saved candidate; no retroactive addition",
        } for row in snap.projection["cells"]]
    all_columns = {}
    for option in suggestions:
        key = (option["kind"], option["candidate_id"])
        all_columns.setdefault(key, {"kind": option["kind"], "id": option["candidate_id"],
                                    "name": option["name"], "label": option["label"]})
    # Keep saved choices visible even when a Run or Forecast has been withdrawn.
    if snap and not is_historical:
        for option in chosen.values():
            key = (option["kind"], option["candidate_id"])
            all_columns.setdefault(key, {"kind": option["kind"], "id": option["candidate_id"],
                                        "name": option["candidate_id"],
                                        "label": "Selected, evidence currently unavailable"})
    columns = sorted(all_columns.values(), key=lambda c: (c["kind"], c["name"].casefold(), c["id"]))
    tasks = _task_nodes()
    # A consistent taxonomy order is computed once; no browser-side fake
    # summation of parent and child opportunities is permitted.
    by_parent = defaultdict(list)
    for node in tasks:
        by_parent[node["parent_id"]].append(node)
    ordered = []
    seen = set()
    def walk(parent, depth):
        if depth > 100:
            return
        for row in by_parent[parent]:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            ordered.append({**row, "depth": depth})
            walk(row["id"], depth + 1)
    walk(None, 0)
    # Orphans/cycles are reported but never traversed recursively without bound.
    for row in tasks:
        if row["id"] not in seen:
            ordered.append({**row, "depth": 0, "orphaned": True})
    task_window = ordered[row_page * row_size:(row_page + 1) * row_size]
    col_window = columns[column_page * column_size:(column_page + 1) * column_size]
    visible_task_ids = {x["id"] for x in task_window}
    visible_column_ids = {(x["kind"], x["id"]) for x in col_window}
    eligible = {(x["task_id"], x["kind"], x["candidate_id"]): x for x in suggestions
                if x["task_id"] in visible_task_ids and
                (x["kind"], x["candidate_id"]) in visible_column_ids}
    selected_cells = {}
    if snap:
        frozen = snap.projection if is_historical else core.project(profile, snap.assumptions)
        selected_cells = {(c["task_id"], c["kind"], c["candidate_id"]): c
                          for c in frozen["cells"]}
    else:
        frozen = None
    cells = []
    for key, candidate in eligible.items():
        if key in selected_cells:
            result = selected_cells[key]
        elif is_historical:
            continue
        else:
            # Single Task/candidate = the exact existing FUT-13 formula, not
            # an aggregation of competing alternative benefits. Up to 192
            # actual candidates are computed; no dense cross product.
            result = core.project(profile, {
                "name": "Unselected analytical comparison",
                "benchmark_weight": "0.8", # no mixing without an explicit link
                "choices": [{"task_id": key[0], "kind": key[1], "candidate_id": key[2]}]
            })["cells"][0]
        cells.append(_cell(key[0], candidate, result, key in selected_cells))
    # Include selected withdrawal/missing candidates as unquantifiable even if
    # no longer in today's public candidate listing (subject to selected scope).
    for key, result in selected_cells.items():
        if key[0] in visible_task_ids and (key[1], key[2]) in visible_column_ids and key not in eligible:
            candidate = {"task_id": key[0], "kind": key[1], "candidate_id": key[2]}
            cells.append(_cell(key[0], candidate, result, True))
    return {
        "scope": "authorized_planning_only", "profile_id": profile.public_id,
        "scenario_id": scenario.public_id if scenario else None,
        "revision": "r%03d" % snap.number if snap else None,
        "historical": is_historical,
        "period": "annual", "currency": "EUR",
        "source_freshness": "frozen_as_of_snapshot" if is_historical else "current_effective_published",
        "computed_at": snap.created_at.isoformat() if is_historical else timezone.now().isoformat(),
        "row_page": row_page, "column_page": column_page,
        "row_size": row_size, "column_size": column_size,
        "total_rows": len(ordered), "total_columns": len(columns),
        "rows": task_window, "columns": col_window,
        "cells": cells, "total_cells": len(cells),
        "legend": {"unit": "EUR/year", "intensity_breakpoints_eur": ["0","1000","10000","100000"],
                   "color_semantics": "positive_economic_amount_only",
                   "zero_and_negative": "unshaded_with_text", "unknown": "unshaded",
                   "maturity_icons": {"B": "accepted measured source",
                                      "F": "published theoretical Forecast",
                                      "?": "source incomplete/unquantifiable"}},
        "chosen_scenario": frozen if snap else None,
        "selected_choices": list(chosen.values()) if snap else [],
        "note": "Unselected cells are alternative projections and NEVER added to portfolio totals; historical mode shows frozen selected cells only.",
    }


def insights(*, profile_id, scenario_id=None, revision=None):
    profile = core._profile(profile_id)
    scenario = _scenario(scenario_id, profile)
    snap = _snapshot(scenario, revision)
    if not snap:
        return {"profile_id": profile.public_id, "scenario_id": None,
                "portfolio": None, "snapshots": [], "suggestion_policy": "comparison_only_no_qualified_global_ranking",
                "period": "annual", "empty": "Choose a saved scenario to view portfolio totals"}
    if revision is None:
        portfolio = core.project(profile, snap.assumptions)
    else:
        portfolio = snap.projection
    history_rows = list(scenario.snapshots.order_by("number"))
    history = []
    previous = None
    for row in history_rows:
        projection = row.projection
        point = {
            "revision": "r%03d" % row.number,
            "revision_number": row.number,
            "revision_id": str(row.pk),
            "date": row.created_at.isoformat(),
            "annual_slices": _slice_totals(projection),
            "total_eur": projection["totals"]["positive_modeled_total_eur"],
            "original_algorithm": row.algorithm,
            "source_frozen": True,
            "profile_revision_id": projection.get("profile_revision_id"),
        }
        if previous is not None:
            point["delta_eur"] = core.money(Decimal(point["total_eur"]) -
                                           Decimal(previous["total_eur"]))
            point["slice_delta_eur"] = {
                key: core.money(Decimal(point["annual_slices"][key]) -
                                Decimal(previous["annual_slices"][key])) for key in SLICES}
            point["possible_change_factors"] = delta_factors(
                previous["projection"], projection,
                previous["assumptions"], row.assumptions)
        else:
            point["delta_eur"] = None
            point["slice_delta_eur"] = None
            point["possible_change_factors"] = ["initial_snapshot"]
        history.append(point)
        previous = {"total_eur": point["total_eur"],
                    "annual_slices": point["annual_slices"],
                    "projection": projection, "assumptions": row.assumptions}
    return {
        "profile_id": profile.public_id, "scenario_id": scenario.public_id,
        "revision": "r%03d" % snap.number,
        "historical": revision is not None,
        "portfolio": portfolio,
        "as_of": snap.created_at.isoformat() if revision is not None else timezone.now().isoformat(),
        "source_changed_since_snapshot": portfolio != snap.projection if revision is None else False,
        "snapshots": history,
        "period": "annual", "currency": "EUR",
        "interpretation": "prospective_labor_value_not_realized_cash_savings",
        "suggestion_policy": "economic_comparison_only_no_qualified_global_ranking",
    }


def delta_factors(before, after, old_assumptions, new_assumptions):
    """Transparent source categories; never claim unproven precise causation."""
    factors = []
    if old_assumptions != new_assumptions:
        factors.append("scenario_selection_or_weight_changed")
    if before.get("profile_revision_id") != after.get("profile_revision_id"):
        factors.append("workload_revision_changed")
    def refs(doc, field):
        return [(x["task_id"], x.get(field)) for x in doc.get("cells", [])]
    if refs(before,"measured_reference") != refs(after,"measured_reference"):
        factors.append("measured_run_revision_or_eligibility_changed")
    if refs(before,"forecast_reference") != refs(after,"forecast_reference"):
        factors.append("forecast_source_revision_or_eligibility_changed")
    if _slice_totals(before) != _slice_totals(after):
        factors.append("modeled_slice_values_changed")
    if not factors:
        factors.append("no_detected_material_change")
    return factors


def explain(*, profile_id, scenario_id, task_id, kind, candidate_id, revision=None):
    """Progressive tree of authorized aggregate factors, exact revision refs.

    Historical selection is resolved only from the stored immutable snapshot.
    No fallback to today's source if an old reference is withdrawn.
    """
    profile = core._profile(profile_id)
    scenario = _scenario(scenario_id, profile)
    snap = _snapshot(scenario, revision)
    if not scenario or not snap:
        raise core.InvalidOpportunity("Select a saved scenario to inspect source lineage")
    projection = (snap.projection if revision is not None else
                  core.project(profile, snap.assumptions))
    cell = next((r for r in projection["cells"]
                 if r["task_id"] == task_id and r["kind"] == kind and
                 r["candidate_id"] == candidate_id), None)
    if cell is None:
        raise core.InvalidOpportunity("Candidate is not selected in the original scenario revision")
    work = cell.get("source_workload") or {}
    original = cell.get("measured_reference") or {}
    theory = cell.get("forecast_reference") or {}
    return {
        "scenario_id": scenario.public_id, "revision": "r%03d" % snap.number,
        "as_of": snap.created_at.isoformat() if revision is not None else timezone.now().isoformat(),
        "historical": revision is not None,
        "breadcrumbs": [{"type": "scenario", "id": scenario.public_id},
                        {"type": "task", "id": task_id},
                        {"type": kind, "id": candidate_id}],
        "summary": {"status": cell["status"], "reasons": cell["reasons"],
                    "annual_eur": (cell.get("economic") or {}).get("annual_eur"),
                    "slices": cell.get("slices"), "evidence_class": cell["evidence_class"]},
        "branches": [
            {"type": "formula", "label": "Annual economic calculation",
             "factors": {"algorithm": projection["algorithm"],
                         "expression": (cell.get("economic") or {}).get("formula"),
                         "inputs": cell.get("economic"), "blend_weight": projection["benchmark_weight"],
                         "rate_source": "authorized_planning_only"}},
            {"type": "workload", "label": "Effective role/person/cohort workload",
             "factors": work, "original_revision_id": work.get("profile_revision_id")},
            {"type": "benchmark", "label": "Original measured Run revisions",
             "factors": original, "refs": original.get("run_revisions", [])},
            {"type": "forecast", "label": "Pinned theoretical Forecast and Watch evidence",
             "factors": theory},
            {"type": "tariff", "label": "Recorded marginal EUR reference",
             "factors": {"basis": cell.get("cost_basis"),
                         "recorded_cost": (cell.get("economic") or {}).get(
                             "marginal_reference_ai_cost_eur"),
                         "current_supplier_quote_verified": False}},
            {"type": "deployment", "label": "Entitlement and first use",
             "factors": {"status": projection["activation_status"],
                         "verified_activated_users": 0,
                         "evidence": "Not available until FUT-15"}},
        ],
        "source_warning": ("Immutable as-of projection; source may have since been withdrawn"
                           if revision is not None else
                           "Current authoritative active-published read at inspection time"),
    }


def suggestions(*, profile_id, max_items=40):
    """Safe economic ordering of *alternatives*; never an unsupported AI score."""
    profile = core._profile(profile_id)
    limit = _safe_int(max_items, "suggestion limit")
    if not 1 <= limit <= 40:
        raise core.InvalidOpportunity("Suggestion limit must be 1..40")
    candidates = core.candidates()
    workload = core.effective(profile) if hasattr(core, "effective") else None
    relevant = {r["task_id"] for r in workload["workloads"]} if workload else set()
    choices = [c for c in candidates if c["task_id"] in relevant]
    if len(choices) > ALTERNATIVE_LIMIT:
        # Explicitly bounded, not a silent partial winner list.
        raise core.InvalidOpportunity("Too many relevant alternatives for source-backed suggestions")
    entries = []
    for option in choices:
        cell = core.project(profile, {"name": "Unselected economic comparison",
            "choices": [{"task_id": option["task_id"], "kind": option["kind"],
                         "candidate_id": option["candidate_id"]}],
            "benchmark_weight": "0.8"})["cells"][0]
        monetary = (cell.get("economic") or {}).get("annual_eur")
        entries.append({
            "task_id": option["task_id"], "candidate_id": option["candidate_id"],
            "kind": option["kind"], "name": option["name"], "status": cell["status"],
            "annual_eur": monetary,
            "evidence_class": cell["evidence_class"],
            "confidence": cell.get("confidence"),
            "source_refs": {"measured": cell.get("measured_reference"),
                            "forecast": cell.get("forecast_reference")},
            "not_selected": True, "deployment_started": False,
            "reason": ("Published measured observation; economic comparison only"
                       if option["kind"] == "benchmark"
                       else "Published theoretical hypothesis; not measured"),
        })
    # Measured sources before theoretical, then positive quantified reference;
    # incomplete/negative candidates retained but never shown as winners.
    entries.sort(key=lambda x: (
        0 if x["kind"] == "benchmark" else 1,
        0 if x["status"] == "quantified_annual_potential" else 1,
        -Decimal(x["annual_eur"]) if x["annual_eur"] is not None else Decimal("0"),
        x["task_id"], x["candidate_id"],
    ))
    return {"profile_id": profile.public_id,
            "sort_policy": "descriptive_evidence_maturity_then_annual_economic_potential_v1",
            "not": "quality_ranking_or_approved_deployment",
            "total_candidates": len(entries),
            "suggestions": entries[:limit]}
