"""FUT-15: manual, auditable deployment targeting; no IAM/provisioning side effects.

A target pins one Task/configuration and one planning population. Its beneficiaries
are explicitly named pseudo-identities (optional person profiles, no account needed).
Only *current*, independently verified external access, setup and confirmed use
qualify as activated. Historical revision/event rows are never changed.
"""
from uuid import UUID
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model

from .catalog_ids import new_public_id
from .environment_services import compose
from .models import (BenchmarkRun, CatalogItem, CatalogRevision, DeploymentTarget,
                     DeploymentRevision, DeploymentEvent, OpportunityScenario,
                     TaskNode, WorkloadProfile, UserEnvironmentRevision)
from .opportunity_services import candidates, InvalidOpportunity
from .pricing_services import accessibility
from .publication_services import effective_ids
from .setup_recipe_services import from_revision
from .setup_composition import SetupCompositionError
from .workload_services import effective, latest

MAX_SEATS = 100
COMPONENT_TYPES = ("model", "provider", "harness", "framework")
STAGES = ("requested", "approved", "rejected", "provisioned", "verified", "revoked")
NEXT = {None: {"requested"}, "requested": {"approved", "rejected", "revoked"},
        "approved": {"provisioned", "rejected", "revoked"},
        "provisioned": {"verified", "revoked"},
        "verified": {"revoked"}, "rejected": {"requested"},
        "revoked": {"requested"}}


class InvalidDeployment(ValueError):
    pass


class StaleDeployment(InvalidDeployment):
    pass


def _id(value, prefix):
    return isinstance(value, str) and len(value) <= 120 and value.startswith(prefix + "-")


def _revision_id(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except (ValueError, TypeError, AttributeError):
        return None


def _source(kind, candidate, task):
    """Read exact immutable technical pins, never let the requester self-certify them."""
    if (task.item.public_id, kind, candidate.public_id) not in {
        (x["task_id"], x["kind"], x["candidate_id"]) for x in candidates()
    }:
        raise InvalidDeployment("Candidate is not a currently published Task option")
    if kind == "benchmark":
        rows = BenchmarkRun.objects.filter(
            public_id__in=effective_ids(kind="individual"),
            solution__item=candidate, session__case_pin__test_case__task=task
        ).select_related("session__individual_setup", "session__guide_revision").order_by("public_id")
        run = rows.first()
        if run is None or not hasattr(run.session, "individual_setup"):
            raise InvalidDeployment("No pinned measured configuration")
        snap = run.session.individual_setup
        source = {"type": "measured_run", "id": run.public_id,
                  "revision_id": str(run.solution_revision_id)}
        guide = run.session.guide_revision_id
    else:
        from .models import ForecastSnapshot
        forecast = ForecastSnapshot.objects.select_related(
            "revision__item").filter(revision=candidate.current_revision, task=task).first()
        if forecast is None:
            raise InvalidDeployment("No pinned theoretical configuration")
        snap = forecast
        source = {"type": "forecast", "id": candidate.public_id,
                  "revision_id": str(forecast.revision_id)}
        guide = None
    components = []
    for k in ("model", "provider", "harness"):
        item = getattr(snap, k)
        rev = getattr(snap, k + "_revision_id")
        components.append({"id": item.public_id, "type": k, "revision_id": str(rev)})
    return components, source, str(guide) if guide else None


def _selection(population, supplied, components, source, default_guide):
    if not isinstance(supplied, dict) or set(supplied) - {
        "seats", "guide_revision_id", "status"}:
        raise InvalidDeployment("Select beneficiaries, optional pinned guide and status only")
    state = supplied.get("status", "selected")
    if state not in ("selected", "retired"):
        raise InvalidDeployment("Invalid target lifecycle status")
    seats = supplied.get("seats")
    if not isinstance(seats, list) or not 1 <= len(seats) <= MAX_SEATS:
        raise InvalidDeployment("Explicit beneficiary list required (1..100 seats)")
    headcount = effective(population)["headcount"]
    if len(seats) > headcount:
        raise InvalidDeployment("Beneficiary count exceeds population headcount")
    keys, people, normalized = set(), set(), []
    for row in seats:
        if not isinstance(row, dict) or set(row) - {"key", "person_profile_id", "available_os"}:
            raise InvalidDeployment("Invalid beneficiary")
        key = row.get("key")
        if (not isinstance(key, str) or not 1 <= len(key) <= 64 or
                not all(x.isalnum() or x in "-_" for x in key) or key in keys):
            raise InvalidDeployment("Seat identifier must be unique, 1..64 safe characters")
        keys.add(key)
        ident = row.get("person_profile_id")
        if ident is not None:
            person = WorkloadProfile.objects.filter(public_id=ident, kind="person").first()
            if person is None or ident in people:
                raise InvalidDeployment("Seat person must be an existing unique person profile")
            if population.kind == "person" and population.pk != person.pk:
                raise InvalidDeployment("Person target cannot include another individual")
            people.add(ident)
        elif population.kind == "person":
            raise InvalidDeployment("Person scope must use its own person profile")
        os = row.get("available_os")
        if os is not None:
            from .environment_services import validate_os, InvalidEnvironment
            try:
                os = validate_os(os)
            except InvalidEnvironment as exc:
                raise InvalidDeployment(str(exc)) from exc
        normalized.append({"key": key, "person_profile_id": ident, "available_os": os})
    selected_guide = supplied.get("guide_revision_id", default_guide)
    if selected_guide is not None:
        revision = CatalogRevision.objects.select_related("item").filter(
            pk=_revision_id(selected_guide), item__type_slug="setup_guide").first()
        if revision is None:
            raise InvalidDeployment("Guide must reference a real immutable guide revision")
        selected_guide = str(revision.pk)
    return {"status": state, "seats": normalized, "components": components,
            "source": source, "guide_revision_id": selected_guide}


@transaction.atomic
def create(actor, data):
    if not isinstance(data, dict) or set(data) - {
        "profile_id", "task_id", "kind", "candidate_id", "scenario_id", "selection"
    } or not {"profile_id", "task_id", "kind", "candidate_id", "selection"} <= set(data):
        raise InvalidDeployment("Explicit population, Task, candidate and beneficiaries required")
    profile = WorkloadProfile.objects.filter(public_id=data["profile_id"]).first() if _id(
        data["profile_id"], "wlp") else None
    task = TaskNode.objects.select_related("item").filter(
        item__public_id=data["task_id"]).first() if _id(data["task_id"], "tsk") else None
    kind = data["kind"]
    candidate = CatalogItem.objects.filter(public_id=data["candidate_id"],
        type_slug="measured_solution" if kind == "benchmark" else "forecast").first() if (
            kind in ("benchmark", "forecast") and isinstance(data["candidate_id"], str)) else None
    # Measured Solution CatalogItem type is "solution", not a fabricated alias.
    if kind == "benchmark" and candidate is None:
        candidate = CatalogItem.objects.filter(public_id=data["candidate_id"],
                                               type_slug="solution").first()
    if not all((profile, task, candidate)):
        raise InvalidDeployment("Unknown population, Task or typed candidate")
    components, source, guide = _source(kind, candidate, task)
    origin = None
    scenario_id = data.get("scenario_id")
    if scenario_id is not None:
        if not _id(scenario_id, "opp"):
            raise InvalidDeployment("Invalid opportunity identity")
        scenario = OpportunityScenario.objects.filter(
            public_id=scenario_id, profile=profile).first()
        if scenario is None:
            raise InvalidDeployment("Scenario and target population must match")
        origin = scenario.snapshots.order_by("-number").first()
        if not any(c["task_id"] == data["task_id"] and c["kind"] == kind and
                   c["candidate_id"] == data["candidate_id"]
                   for c in origin.assumptions["choices"]):
            raise InvalidDeployment("Target must be deliberately selected in originating scenario")
    selection = _selection(profile, data["selection"], components, source, guide)
    if DeploymentTarget.objects.filter(population=profile, task=task,
            candidate=candidate, kind=kind).exists():
        raise InvalidDeployment("An existing target must be revised, not duplicated")
    for _ in range(12):
        public_id = new_public_id("dpt")
        try:
            with transaction.atomic():
                target = DeploymentTarget.objects.create(
                    public_id=public_id, population=profile, task=task, candidate=candidate,
                    kind=kind, origin=origin, created_by=actor)
                DeploymentRevision.objects.create(
                    target=target, number=1, selection=selection, created_by=actor)
                return target
        except IntegrityError:
            if DeploymentTarget.objects.filter(public_id=public_id).exists():
                continue
            raise InvalidDeployment("Conflicting target identity or population selection")
    raise InvalidDeployment("Cannot reserve a deployment identity")


def latest_revision(target):
    return target.revisions.order_by("-number").first()


@transaction.atomic
def revise(actor, target, expected, supplied):
    target = DeploymentTarget.objects.select_for_update().get(pk=target.pk)
    previous = latest_revision(target)
    if expected != "r%03d" % previous.number:
        raise StaleDeployment("Reload the target before editing")
    components = previous.selection["components"]
    source = previous.selection["source"]
    selection = _selection(target.population, supplied, components, source,
                           previous.selection["guide_revision_id"])
    # Every revision begins without previously asserted setup/use claims.
    # Existing access events remain traceable but may not silently certify a new scope.
    return DeploymentRevision.objects.create(
        target=target, number=previous.number + 1, selection=selection, created_by=actor)


def _seat_user(seat):
    ident = seat["person_profile_id"]
    if not ident:
        return None, False
    person = WorkloadProfile.objects.filter(public_id=ident, kind="person").first()
    if not person:
        return None, False
    row = latest(person)
    if not row or not row.linked_user_id:
        return None, False
    user = get_user_model().objects.filter(pk=row.linked_user_id).first()
    return user, bool(user and not user.is_active)


def _os(seat):
    user, disabled = _seat_user(seat)
    if disabled:
        return None, True
    if user:
        env = UserEnvironmentRevision.objects.filter(user=user).order_by("-number").first()
        return env.available_os if env else None, False
    return seat["available_os"], False


def _events(target, rev, key):
    """Exact revision journal only: later edits cannot inherit old verification."""
    rows = target.events.filter(target_revision=rev, seat_key=key).order_by("created_at", "id")
    status, setup, first_used = {}, False, False
    for row in rows:
        if row.component_id:
            status[row.component.public_id] = row.action
        elif row.action in ("setup_verified", "setup_revoked"):
            setup = row.action == "setup_verified"
        elif row.action in ("first_use", "first_use_revoked"):
            first_used = row.action == "first_use"
    return status, setup, first_used


def seat_readiness(target, rev, seat):
    status, setup, first_used = _events(target, rev, seat["key"])
    problems = []
    available, disabled = _os(seat)
    if disabled:
        problems.append("linked_account_disabled")
    if available is None:
        problems.append("user_os_unknown")
    parts, context = [], {}
    for part in rev.selection["components"]:
        item = CatalogItem.objects.select_related("current_revision").filter(
            public_id=part["id"], type_slug=part["type"]).first()
        pinned = CatalogRevision.objects.filter(
            pk=_revision_id(part["revision_id"]), item=item).first() if item else None
        if not pinned or not item.current_revision_id:
            problems.append("source_component_missing")
            continue
        if accessibility(item.current_revision.properties) in ("not_accessible", "unknown"):
            problems.append("enterprise_access_unverified:" + item.public_id)
        if status.get(item.public_id) != "verified":
            problems.append("entitlement_unverified:" + item.public_id)
        parts.append({"type": item.type_slug, "id": item.public_id,
                      "revision": "r%03d" % pinned.number, "properties": pinned.properties})
        context[item.type_slug] = item.public_id
        context[item.type_slug + "_revision_id"] = str(pinned.pk)
    os_fit = compose(parts, available) if available else compose(parts, None)
    if os_fit["status"] != "compatible":
        problems.append("environment_" + os_fit["status"])
    guide_id = rev.selection.get("guide_revision_id")
    guide = CatalogRevision.objects.filter(pk=_revision_id(guide_id),
                                           item__type_slug="setup_guide").first() if guide_id else None
    if not guide:
        problems.append("guide_not_pinned")
    else:
        if available:
            context["os"] = os_fit.get("matching_os", [None])[0]
        try:
            guide_result = from_revision(guide, context)
            if not guide_result["ready"]:
                problems.append("setup_recipe_incomplete")
        except (SetupCompositionError, ValueError, TypeError):
            problems.append("setup_recipe_invalid")
    if not setup:
        problems.append("setup_not_verified")
    if rev.selection["status"] != "selected":
        problems.append("target_retired")
    ready = not problems
    return {"key": seat["key"], "person_profile_id": seat["person_profile_id"],
            "entitlements": status, "os": os_fit["status"], "setup_verified": setup,
            "ready": ready, "first_use_confirmed": first_used,
            "activated": ready and first_used, "blockers": sorted(set(problems))}


def status(target, *, private=True):
    rev = latest_revision(target)
    rows = [seat_readiness(target, rev, s) for s in rev.selection["seats"]]
    result = {"id": target.public_id, "profile_id": target.population.public_id,
        "task_id": target.task.item.public_id, "candidate_id": target.candidate.public_id,
        "kind": target.kind, "revision": "r%03d" % rev.number,
        "revision_id": str(rev.id), "status": rev.selection["status"],
        "origin_snapshot_id": str(target.origin_id) if target.origin_id else None,
        "source": rev.selection["source"], "components": rev.selection["components"],
        "guide_revision_id": rev.selection["guide_revision_id"],
        "selected_count": len(rows), "activated_count": sum(s["activated"] for s in rows),
        "ready_count": sum(s["ready"] for s in rows),
        "population_headcount": effective(target.population)["headcount"],
        "derived_at_read_time": True}
    if private:
        result["beneficiaries"] = rows
        result["events"] = [{"id": str(e.id), "seat_key": e.seat_key,
            "component_id": e.component.public_id if e.component else None,
            "action": e.action, "reference": e.evidence_reference,
            "actor": e.actor.get_username(), "at": e.created_at.isoformat()}
            for e in target.events.select_related("actor", "component").order_by("created_at", "id")[:1000]]
    return result


@transaction.atomic
def record(actor, target, payload):
    if not isinstance(payload, dict) or set(payload) != {
        "expected_revision", "seat_key", "component_id", "action", "evidence_reference"}:
        raise InvalidDeployment("Exact target revision, seat, component, action and reference required")
    target = DeploymentTarget.objects.select_for_update().get(pk=target.pk)
    rev = latest_revision(target)
    if payload["expected_revision"] != "r%03d" % rev.number:
        raise StaleDeployment("Target changed; reload before recording an action")
    if rev.selection["status"] != "selected":
        raise InvalidDeployment("Retired target cannot record new access or use")
    seat = next((s for s in rev.selection["seats"] if s["key"] == payload["seat_key"]), None)
    if seat is None:
        raise InvalidDeployment("Unknown beneficiary")
    action, component_id = payload["action"], payload["component_id"]
    reference = payload["evidence_reference"]
    if (not isinstance(reference, str) or len(reference) > 300 or
            action not in STAGES + ("setup_verified", "setup_revoked", "first_use", "first_use_revoked")):
        raise InvalidDeployment("Invalid manual action or bounded verification reference")
    component, component_rev = None, None
    previous, setup, first = _events(target, rev, seat["key"])
    if action in STAGES:
        pinned = next((c for c in rev.selection["components"] if c["id"] == component_id), None)
        if not pinned:
            raise InvalidDeployment("Action must name one pinned external component")
        if action not in NEXT.get(previous.get(component_id), set()):
            raise InvalidDeployment("Invalid external entitlement transition")
        component = CatalogItem.objects.get(public_id=component_id)
        component_rev = CatalogRevision.objects.get(pk=_revision_id(pinned["revision_id"]),
                                                     item=component)
    else:
        if component_id is not None:
            raise InvalidDeployment("Setup and usage are separate from component grants")
        state = seat_readiness(target, rev, seat)
        if action == "setup_verified":
            # Do not let setup attestation bypass OS/guide applicability.
            blockers = [x for x in state["blockers"] if x not in (
                "setup_not_verified",)]
            if blockers:
                raise InvalidDeployment("Setup cannot be verified: " + ", ".join(blockers))
            if setup:
                raise InvalidDeployment("Setup already verified")
        elif action == "first_use":
            if not state["ready"] or first:
                raise InvalidDeployment("First use requires verified environment, every entitlement and setup")
        elif action == "setup_revoked" and not setup:
            raise InvalidDeployment("Setup is not verified")
        elif action == "first_use_revoked" and not first:
            raise InvalidDeployment("First use is not confirmed")
    if action in ("verified", "setup_verified", "first_use") and len(reference.strip()) < 8:
        raise InvalidDeployment("Verification requires a non-secret evidence reference (8..300 characters)")
    return DeploymentEvent.objects.create(
        target=target, target_revision=rev, seat_key=seat["key"],
        beneficiary=WorkloadProfile.objects.filter(public_id=seat["person_profile_id"]).first()
                    if seat["person_profile_id"] else None,
        component=component, component_revision=component_rev, action=action,
        evidence_reference=reference.strip(), actor=actor)


def verified_count(profile, task_id, kind, candidate_id):
    """The only input to live DAP activation; historical snapshots stay frozen."""
    target = DeploymentTarget.objects.filter(
        population=profile, task__item__public_id=task_id,
        kind=kind, candidate__public_id=candidate_id).first()
    if target is None:
        return 0
    return status(target, private=False)["activated_count"]
