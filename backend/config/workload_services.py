"""DAP-01: append-only workload assumptions and deterministic inheritance.

No population productivity monitoring and no economic conclusions. Unknown is
None, an explicit zero is Decimal(0), and conflicting parent sources are NOT
added. All data are confidential and only served by planning capability APIs.
"""
from decimal import Decimal, InvalidOperation
import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .catalog_ids import new_public_id
from .models import WorkloadProfile, WorkloadRevision, WorkloadAllocation, TaskNode

KINDS = ("role", "specialty", "person", "cohort")
MAX_TASKS = 500


class InvalidWorkload(ValueError):
    pass


class StaleWorkload(InvalidWorkload):
    pass


def _decimal(value, *, field, upper, digits=2):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise InvalidWorkload(field + " must be a decimal number or null")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise InvalidWorkload("Invalid " + field) from error
    if not number.is_finite() or number < 0 or number > upper or number.as_tuple().exponent < -digits:
        raise InvalidWorkload(field + " must be nonnegative, finite and <= " + str(upper))
    return number


def _get_parent(identifier, kind):
    if identifier is None:
        return None
    if not isinstance(identifier, str):
        raise InvalidWorkload("Invalid " + kind + " reference")
    profile = WorkloadProfile.objects.filter(public_id=identifier, kind=kind).first()
    if profile is None or not profile.revisions.exists():
        raise InvalidWorkload("Referenced " + kind + " profile does not exist")
    return profile


def _parse(kind, data):
    if kind not in KINDS or not isinstance(data, dict):
        raise InvalidWorkload("Unsupported workload profile")
    allowed = {"name", "role_id", "specialty_id", "linked_user_id", "headcount",
               "hourly_rate_eur", "notes", "workloads"}
    if set(data) - allowed:
        raise InvalidWorkload("Unexpected workload input keys")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
        raise InvalidWorkload("Name must be 1..160 characters")
    notes = data.get("notes", {})
    if not isinstance(notes, dict) or len(json.dumps(notes, ensure_ascii=False)) > 4000:
        raise InvalidWorkload("Notes must be a bounded JSON object")
    if kind in {"role", "specialty"} and any(data.get(x) is not None
                                              for x in ("role_id", "specialty_id", "linked_user_id")):
        raise InvalidWorkload("Role and specialty templates cannot inherit people or profiles")
    if kind == "role" and data.get("specialty_id") is not None:
        raise InvalidWorkload("Role cannot inherit specialty")
    role = _get_parent(data.get("role_id"), "role") if kind in {"person", "cohort"} else None
    specialty = _get_parent(data.get("specialty_id"), "specialty") if kind in {"person", "cohort"} else None
    linked_user = None
    if data.get("linked_user_id") is not None:
        if kind != "person" or type(data["linked_user_id"]) is not int:
            raise InvalidWorkload("Only a person may link an existing account ID")
        linked_user = get_user_model().objects.filter(pk=data["linked_user_id"]).first()
        if linked_user is None:
            raise InvalidWorkload("Linked account does not exist")
    headcount = data.get("headcount", 1)
    if type(headcount) is not int or not 1 <= headcount <= 100000:
        raise InvalidWorkload("Headcount must be an integer from 1 to 100000")
    if kind != "cohort" and headcount != 1:
        raise InvalidWorkload("Only cohorts can aggregate multiple persons")
    rate = _decimal(data.get("hourly_rate_eur"), field="hourly_rate_eur",
                    upper=Decimal("10000000"))
    if kind == "cohort" and linked_user:
        raise InvalidWorkload("Cohorts cannot reference individual accounts")
    workloads = data.get("workloads", [])
    if not isinstance(workloads, list) or len(workloads) > MAX_TASKS:
        raise InvalidWorkload("Invalid number of Task workloads")
    ids = [r.get("task_id") if isinstance(r, dict) else None for r in workloads]
    if any(not isinstance(k, str) or not k.startswith("tsk-") for k in ids) or len(set(ids)) != len(ids):
        raise InvalidWorkload("Invalid/duplicate Task identifiers")
    tasks = {node.item.public_id: node for node in TaskNode.objects.select_related("item").filter(
        item__public_id__in=ids)}
    if set(tasks) != set(ids):
        raise InvalidWorkload("Workloads must reference existing Tasks")
    allocations = []
    for row in workloads:
        if set(row) - {"task_id", "annual_occurrences", "baseline_human_hours", "excluded"}:
            raise InvalidWorkload("Unsupported workload line property")
        excluded = row.get("excluded", False)
        if type(excluded) is not bool:
            raise InvalidWorkload("excluded must be boolean")
        amount = _decimal(row.get("annual_occurrences"), field="annual_occurrences",
                          upper=Decimal("9999999999"))
        baseline = _decimal(row.get("baseline_human_hours"), field="baseline_human_hours",
                            upper=Decimal("999999"))
        if excluded and (amount is not None or baseline is not None):
            raise InvalidWorkload("Excluded lines must not provide frequencies or hours")
        allocations.append((tasks[row["task_id"]], amount, baseline, excluded))
    return {"name": name.strip(), "role": role, "specialty": specialty,
            "linked_user": linked_user, "headcount": headcount, "hourly_rate_eur": rate,
            "notes": notes, "workloads": allocations}


def _append(profile, actor, data):
    previous = profile.revisions.order_by("-number").first()
    rev = WorkloadRevision.objects.create(
        profile=profile, number=1 if previous is None else previous.number + 1,
        name=data["name"], role=data["role"], specialty=data["specialty"],
        linked_user=data["linked_user"], headcount=data["headcount"],
        hourly_rate_eur=data["hourly_rate_eur"], notes=data["notes"], created_by=actor)
    WorkloadAllocation.objects.bulk_create([
        WorkloadAllocation(revision=rev, task=task, annual_occurrences=frequency,
                           baseline_human_hours=hours, excluded=excluded)
        for task, frequency, hours, excluded in data["workloads"]
    ])
    return rev


@transaction.atomic
def create_profile(*, actor, kind, data):
    validated = _parse(kind, data)
    for _ in range(12):
        public_id = new_public_id("wlp")
        try:
            with transaction.atomic():
                profile = WorkloadProfile.objects.create(kind=kind, public_id=public_id)
                _append(profile, actor, validated)
                return profile
        except IntegrityError:
            if WorkloadProfile.objects.filter(public_id=public_id).exists():
                continue
            raise
    raise InvalidWorkload("Could not allocate a unique planning identifier")


@transaction.atomic
def revise_profile(*, actor, public_id, expected_revision, data):
    profile = WorkloadProfile.objects.select_for_update().filter(public_id=public_id).first()
    if profile is None:
        raise InvalidWorkload("Unknown planning profile")
    previous = profile.revisions.order_by("-number").first()
    if previous is None or expected_revision != f"r{previous.number:03d}":
        raise StaleWorkload("Planning profile changed; reload before revising")
    validated = _parse(profile.kind, data)
    _append(profile, actor, validated)
    return profile


def latest(profile):
    return profile.revisions.order_by("-number").first()


def serialize_revision(rev):
    return {
        "revision": f"r{rev.number:03d}", "revision_id": str(rev.id),
        "name": rev.name, "role_id": rev.role.public_id if rev.role else None,
        "specialty_id": rev.specialty.public_id if rev.specialty else None,
        "linked_user_id": rev.linked_user_id, "headcount": rev.headcount,
        "hourly_rate_eur": str(rev.hourly_rate_eur) if rev.hourly_rate_eur is not None else None,
        "notes": rev.notes, "created_at": rev.created_at.isoformat(),
        "created_by": rev.created_by.get_username(),
        "workloads": [
            {"task_id": allocation.task.item.public_id,
             "annual_occurrences": str(allocation.annual_occurrences)
                                   if allocation.annual_occurrences is not None else None,
             "baseline_human_hours": str(allocation.baseline_human_hours)
                                     if allocation.baseline_human_hours is not None else None,
             "excluded": allocation.excluded}
            for allocation in rev.allocations.select_related("task__item").order_by("task__item__public_id")
        ],
    }


def serialize_profile(profile):
    rev = latest(profile)
    result = serialize_revision(rev)
    result.update({"id": profile.public_id, "kind": profile.kind,
                   "uuid": str(profile.pk)})
    return result


def _allocation_map(rev):
    return {
        x.task.item.public_id: {"task_id": x.task.item.public_id,
            "annual_occurrences": str(x.annual_occurrences)
                                  if x.annual_occurrences is not None else None,
            "baseline_human_hours": str(x.baseline_human_hours)
                                    if x.baseline_human_hours is not None else None,
            "excluded": x.excluded, "revision_id": str(rev.id),
            "profile_id": rev.profile.public_id}
        for x in rev.allocations.select_related("task__item")
    }


def effective(profile):
    """One row per unique Task, never inherited summation across templates."""
    rev = latest(profile)
    sources = []
    if rev.role:
        sources.append(("role", latest(rev.role)))
    if rev.specialty:
        sources.append(("specialty", latest(rev.specialty)))
    entries = {}
    for source_kind, parent in sources:
        for task_id, row in _allocation_map(parent).items():
            entries.setdefault(task_id, []).append((source_kind, row))
    for task_id, row in _allocation_map(rev).items():
        entries[task_id] = [("explicit", row)]  # replaces, never adds
    # A parent+child Task are separate possible descriptions of same work;
    # flag but do not create a fabricated roll-up.
    task_nodes = {n.item.public_id: n for n in TaskNode.objects.select_related("item", "parent__item")}
    results = []
    for task_id, candidates in sorted(entries.items()):
        source, chosen = candidates[0]
        ambiguous = False
        if source != "explicit" and len(candidates) > 1:
            ambiguous = any((
                c["annual_occurrences"], c["baseline_human_hours"], c["excluded"]
            ) != (chosen["annual_occurrences"], chosen["baseline_human_hours"], chosen["excluded"])
                            for _, c in candidates[1:])
        frequency = chosen["annual_occurrences"] if not ambiguous and not chosen["excluded"] else None
        hours = chosen["baseline_human_hours"] if not ambiguous and not chosen["excluded"] else None
        status = ("excluded" if chosen["excluded"] else
                  "ambiguous" if ambiguous else
                  "unknown" if frequency is None else
                  "zero" if Decimal(frequency) == 0 else "resolved")
        ancestors = set()
        node = task_nodes.get(task_id)
        while node and node.parent_id:
            node = node.parent
            ancestors.add(node.item.public_id)
        results.append({
            "task_id": task_id, "task_name": task_nodes[task_id].item.current_revision.display_name,
            "annual_occurrences": frequency,
            "annual_person_occurrences": (str(Decimal(frequency) * rev.headcount)
                                          if frequency is not None else None),
            "baseline_human_hours": hours, "status": status,
            "source": source if not ambiguous else "conflicting_templates",
            "sources": [{"kind": k, "profile_id": x["profile_id"],
                         "revision_id": x["revision_id"]} for k, x in candidates],
            "overlaps_ancestor_task": bool(ancestors & entries.keys()),
        })
    rate = next(({"rate_eur": str(row.hourly_rate_eur), "profile_id": row.profile.public_id,
                  "revision_id": str(row.id)}
                 for row in [rev] + [p for _, p in sources]
                 if row.hourly_rate_eur is not None), None)
    return {"id": profile.public_id, "revision_id": str(rev.id),
            "headcount": rev.headcount, "hourly_rate_source": rate,
            "workloads": results,
            "warnings": [
                "Ambiguous role/specialty frequencies require an explicit override"
                if any(x["status"] == "ambiguous" for x in results) else None,
                "Parent and descendant Tasks overlap; totals must not sum both"
                if any(x["overlaps_ancestor_task"] for x in results) else None,
            ],
            "annual_gain_eur": None, "gain_reason": "No measured/forecast effort and pricing inputs yet"}
