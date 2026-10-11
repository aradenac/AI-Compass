"""FUT-12: read-only, fail-closed Engineer Task/AI Solution projection.

The publication selector remains the sole current measurement authority. There is
no numeric suitability scoring method in v1 (evaluation aggregation='none'); do
not invent means, rankings, productivity, entitlements, or Forecast outcomes.
"""
from collections import defaultdict
from django.db.models import Prefetch
from .models import (BenchmarkRun, CatalogItem, CatalogRevision, TaskNode,
                     MeasuredSolution, WorkloadProfile, WorkloadRevision,
                     UserEnvironmentRevision, DiscussionThread)
from .publication_services import effective_ids
from .run_lifecycle_services import state as run_state
from .environment_services import compose as compose_os
from .pricing_services import accessibility


MAX_TASKS = 500
MAX_RUNS = 500


class InvalidWorkspace(ValueError):
    pass


def _revision(rev):
    return {"id": str(rev.pk), "revision": "r%03d" % rev.number,
            "name": rev.display_name}


def _user_os(actor):
    rev = UserEnvironmentRevision.objects.filter(user=actor).order_by("-number").first()
    return {"configured": bool(rev), "available_os": rev.available_os if rev else None,
            "revision": "r%03d" % rev.number if rev else None}


def _task_profile(actor):
    """Only the requesting person's current linked profile; never disclose rates."""
    candidate = []
    for profile in WorkloadProfile.objects.filter(kind="person",
            revisions__linked_user=actor).distinct()[:51]:
        current = profile.revisions.order_by("-number").first()
        if current and current.linked_user_id == actor.pk:
            candidate.append((profile, current))
    if len(candidate) != 1:
        return {"status": "not_configured" if not candidate else "ambiguous",
                "relevant_task_ids": [], "source": "no_authorized_unique_person_profile"}
    from .workload_services import effective
    result = effective(candidate[0][0])
    return {"status": "configured", "source": "own_person_workload",
            "relevant_task_ids": [r["task_id"] for r in result["workloads"]
                                  if r["status"] not in ("excluded", "ambiguous", "zero")],
            "profile_revision_id": str(candidate[0][1].pk)}


def _tasks():
    nodes = list(TaskNode.objects.select_related(
        "item__current_revision", "parent__item").order_by("position", "item__public_id")[:MAX_TASKS+1])
    if len(nodes) > MAX_TASKS:
        raise InvalidWorkspace("Too many Tasks for unfiltered Engineer discovery")
    return [{"id": n.item.public_id, "name": n.item.current_revision.display_name,
             "revision_id": str(n.item.current_revision_id),
             "parent_id": n.parent.item.public_id if n.parent else None,
             "position": n.position,
             "description": n.item.current_revision.properties.get("description", ""),
             "criteria": n.item.current_revision.properties.get("criteria", "")}
            for n in nodes]


def _runs():
    ids = effective_ids(kind="individual")
    if len(ids) > MAX_RUNS:
        raise InvalidWorkspace("Too many active published Runs; narrow the discovery corpus")
    rows = list(BenchmarkRun.objects.filter(public_id__in=ids).select_related(
        "session__case_pin__test_case__task__item",
        "session__case_pin__test_case__item",
        "session__method_definition",
        "session__campaign_snapshot__revision__item",
        "session__guide__current_revision",
        "session__guide_revision__item",
        "solution__item__current_revision",
        "closing_checkpoint",
    ).order_by("created_at", "public_id"))
    # Fail closed if the selected Run is corrupted or has lost a source pin.
    return [run for run in rows if run.session.case_pin_id and
            run.session.case_pin.test_case.task_id]


def _components(run):
    pin = getattr(run.session, "individual_setup", None)
    if not pin:
        return None
    parts = []
    current = []
    for kind in ("model", "provider", "harness"):
        item = getattr(pin, kind)
        original = getattr(pin, kind+"_revision")
        latest = item.current_revision
        parts.append({"type": kind, "id": item.public_id,
                      "revision_id": str(original.pk),
                      "revision": "r%03d" % original.number,
                      "name": original.display_name,
                      "current_revision_id": str(latest.pk) if latest else None})
        if latest:
            current.append({"type": kind, "id": item.public_id,
                            "revision": "r%03d" % latest.number,
                            "properties": latest.properties})
    return parts, current


def _access(current):
    states = [{"id": c["id"], "type": c["type"],
               "state": accessibility(c["properties"])} for c in current]
    if len(states) != 3:
        status = "unknown"
    elif any(p["state"] == "not_accessible" for p in states):
        status = "not_accessible"
    elif any(p["state"] == "restricted" for p in states):
        status = "restricted"
    elif all(p["state"] == "accessible" for p in states):
        status = "accessible"
    else:
        status = "unknown"
    return {"status": status, "components": states,
            "personal_entitlement": "unknown_unverified",
            "grant_provisioned": False}


def _by_solution(run, os_profile):
    pins = _components(run)
    if pins is None:
        return {"status": "unknown", "supported_os": None, "access": {
            "status": "unknown", "personal_entitlement": "unknown_unverified",
            "grant_provisioned": False}, "components": []}
    original, current = pins
    compat = compose_os([p for p in current if p["type"] == "harness"],
                        os_profile["available_os"])
    return {"status": compat["status"], "supported_os": compat.get("supported_os"),
            "requires_os": compat.get("requires_os"),
            "reason": compat.get("reason"),
            "access": _access(current), "components": original}


def _run_groups(actor):
    profile = _user_os(actor)
    groups = defaultdict(list)
    for run in _runs():
        current = run_state(run)
        if current["status"] != "active":
            continue
        key = (run.session.case_pin.test_case.task.item.public_id,
               run.solution.item.public_id)
        groups[key].append((run, current))
    return groups, profile


def _candidates(actor):
    groups, profile = _run_groups(actor)
    output = defaultdict(list)
    for (task_id, solution_id), evidence in groups.items():
        first = evidence[0][0]
        configuration = _by_solution(first, profile)
        accepted = [x for x in evidence if x[1]["outcome"] == "accepted"]
        failed = [x for x in evidence if x[1]["outcome"] == "failed"]
        methods = {(str(x[0].session.method_definition_id),
                    x[0].session.method_definition.version) for x in evidence}
        # A failed-only or contradictory candidate is not a positive suggestion.
        condition = ("failed_only" if not accepted else "conflicting_evidence"
                     if failed else "mixed_methods" if len(methods) != 1
                     else "accepted_observed")
        access = configuration["access"]["status"]
        os_state = configuration["status"]
        suitability = ("supported_observation" if condition == "accepted_observed" and
                       access not in ("not_accessible", "restricted") and
                       os_state == "compatible" else
                       "other_os_observation" if condition == "accepted_observed" and
                       access not in ("not_accessible", "restricted") and
                       os_state == "other_os" else "unverified_or_not_suitable")
        distinct_cases = {x[0].session.case_pin.test_case.item.public_id for x in evidence}
        output[task_id].append({
            "solution_id": solution_id,
            "name": first.solution.item.current_revision.display_name,
            "task_id": task_id,
            "evidence_class": "measured",
            "outcome_status": condition,
            "suitability": suitability,
            "published_run_count": len(evidence),
            "accepted_run_count": len(accepted),
            "failed_run_count": len(failed),
            "observed_test_case_count": len(distinct_cases),
            "method_versions": [{"id": x, "version": y} for x,y in sorted(methods)],
            "scoring": {"policy": "descriptive_only_v1", "score": None,
                        "rank": None, "reason": "No validated aggregate scoring method registered"},
            "os": {k:v for k,v in configuration.items() if k != "components" and k != "access"},
            "enterprise_access": configuration["access"],
            "configuration": configuration["components"],
            "evidence_refs": [{"id": x[0].public_id,
                               "revision": x[1]["revision"],
                               "outcome": x[1]["outcome"],
                               "test_case_id": x[0].session.case_pin.test_case.item.public_id,
                               "test_case_revision_id": str(x[0].session.case_pin.revision_id),
                               "method_id": str(x[0].session.method_definition_id)}
                              for x in evidence],
        })
    # Stable deterministic display, never a fictitious numeric ranking.
    order = {"supported_observation": 0, "other_os_observation": 1,
             "unverified_or_not_suitable": 2}
    for items in output.values():
        items.sort(key=lambda x: (order[x["suitability"]],
                     x["name"].casefold(), x["solution_id"]))
    return output, profile


def workspace(actor, *, all_tasks=False, view="task"):
    if type(all_tasks) is not bool or view not in ("task", "tool"):
        raise InvalidWorkspace("Invalid Engineer discovery mode")
    tasks = _tasks()
    relevant = _task_profile(actor)
    candidates, os_profile = _candidates(actor)
    focus = set(relevant["relevant_task_ids"])
    # Ancestors provide context, not additional inferred user assignments.
    by_id = {t["id"]:t for t in tasks}
    visible = set(focus)
    for task_id in list(focus):
        parent = by_id.get(task_id, {}).get("parent_id")
        seen = set()
        while parent and parent in by_id and parent not in seen:
            seen.add(parent)
            visible.add(parent)
            parent = by_id[parent]["parent_id"]
    if all_tasks:
        visible = set(by_id)
    shown = [{**t, "relevant": t["id"] in focus,
              "configurations": candidates.get(t["id"], [])}
             for t in tasks if t["id"] in visible]
    # No global taxonomy implied as "personal" when profile is unknown.
    tools = defaultdict(list)
    for t in shown:
        for option in t["configurations"]:
            tools[option["solution_id"]].append({
                "task_id": t["id"], "task_name": t["name"],
                "relevant": t["relevant"], "observation": option})
    inverse = [{"solution_id": key, "name": related[0]["observation"]["name"],
                "tasks": related} for key, related in sorted(tools.items())]
    return {
        "mode": "engineer", "view": view, "scope": "active_published_only",
        "profile": relevant, "user_os": os_profile,
        "tasks": shown, "tools": inverse if view == "tool" else [],
        "all_tasks": all_tasks,
        "scoring_policy": "descriptive_only_v1",
        "theoretical": {"mixed_with_measured": False,
                        "discover_in": "/api/v1/results/explorer?kind=theoretical"},
        "message": ("No personal Task profile assigned: explore all Tasks explicitly"
                    if relevant["status"] != "configured" else None),
    }


def detail(actor, solution_id, *, task_id=None):
    if not isinstance(solution_id, str) or not solution_id.startswith("sol-") or len(solution_id)>120:
        raise InvalidWorkspace("Invalid measured Solution identifier")
    options, os_profile = _candidates(actor)
    found = [o for task, rows in options.items() for o in rows
             if o["solution_id"] == solution_id and
             (task_id is None or task == task_id)]
    if not found:
        return None
    if task_id is not None and (not isinstance(task_id, str) or not task_id.startswith("tsk-")):
        raise InvalidWorkspace("Invalid Task identifier")
    found.sort(key=lambda x:(x["task_id"], x["solution_id"]))
    current = next((x for x in found if x["task_id"] == task_id), found[0])
    refs = [r["id"] for r in current["evidence_refs"]]
    first = next((r for r in _runs() if r.public_id in refs), None)
    guide = {"status": "unavailable", "current": None, "historical": None,
             "user_guide": "not_registered"}
    if first and first.session.guide_revision_id:
        from .setup_recipe_services import from_revision, session_configuration
        from .setup_composition import SetupCompositionError
        session = first.session
        config = session_configuration(session, first.closing_checkpoint.state.get("setup", {}))
        try:
            historical = from_revision(session.guide_revision, config)
            guide["historical"] = {"source": _revision(session.guide_revision),
                                  "status": "tested_original",
                                  "sections": historical.get("sections", [])}
            latest = session.guide.current_revision if session.guide else None
            # Later unpublished draft guide revisions must not silently become
            # public "get started" instructions, even if recipe technically resolves.
            if latest and latest.properties.get("publication") == "published":
                composed = from_revision(latest, config)
                guide["current"] = {"source": _revision(latest),
                                    "ready": composed.get("ready", False),
                                    "sections": composed.get("sections", []) if composed.get("ready") else [],
                                    "missing": composed.get("missing", [])}
                guide["status"] = "applicable" if composed.get("ready") else "not_applicable"
            else:
                guide["status"] = "no_current_published_guide"
        except (SetupCompositionError, ValueError, KeyError, TypeError):
            guide["status"] = "unresolved_setup"
    from .recommendation_services import published_revision
    editorial = []
    related = CatalogItem.objects.filter(type_slug="recommendation").select_related(
        "current_revision").order_by("public_id")[:501]
    for row in related:
        pub = published_revision(row)
        if pub is None:
            continue
        from .models import RecommendationSnapshot
        snap = RecommendationSnapshot.objects.filter(revision=pub,
            solution__item__public_id=solution_id,
            task__item__public_id__in=[x["task_id"] for x in found]).first()
        if snap is None:
            continue
        # Safe descriptive editorial metadata only: never its private source pins.
        from .recommendation_services import serialize
        record = serialize(row, rev=pub, reader=True)
        if record:
            editorial.append({"id":record["id"], "task_id":record["task_id"],
                              "revision":record["revision"],
                              "decision":record["properties"].get("decision"),
                              "rationale":record["properties"].get("rationale", ""),
                              "limitations":record["properties"].get("limitations", ""),
                              "evidence_freshness":record["evidence_freshness"],
                              "eligible_for_current_suitability":record["eligible_for_current_suitability"],
                              "editorial_only": True})
    return {"id": solution_id, "name": current["name"], "task_id": current["task_id"],
            "overview": current, "other_tasks": [
                {"id":x["task_id"]} for x in found if x["task_id"] != current["task_id"]],
            "guide": guide, "editorial": editorial,
            "entitlement": "unknown_unverified",
            "feedback": {"context_id": solution_id,
                "access_interest": "discussion_only_not_an_entitlement_or_purchase",
                "request_status": "not_provisioned"},
            "historical_evidence": {"source": "immutable_run", "runs": current["evidence_refs"]},
            "current_applicability": current["os"],
            "user_os": os_profile}
