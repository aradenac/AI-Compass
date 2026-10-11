"""FUT-10: immutable selected-Run publication decisions on campaign revisions.

Publication is NOT the current campaign status: reopening and drafting preserve the
last explicit, immutable publication. Only the latest publish/revoke event is
effective. All eligibility is calculated from persisted Server Run/session pins.
"""
from django.db import transaction

from .catalog_services import RevisionConflict
from .models import BenchmarkRun, CompositeBenchmarkRun, CatalogItem, CatalogRevision
from .campaign_services import InvalidCampaign, InvalidTransition, modify
from .setup_recipe_services import from_revision, session_configuration
from .setup_composition import SetupCompositionError

MAX_SELECTED = 200


def can_preview(user):
    return (user.has_perm("auth.business_write") or
            user.has_perm("auth.publication_review"))


def _events(item=None, upto=None):
    query = CatalogRevision.objects.filter(
        item__type_slug="campaign", properties__has_key="publication_event")
    if item is not None:
        query = query.filter(item=item)
    if upto is not None:
        query = query.filter(number__lte=upto)
    return query.order_by("-number")


def latest(item, upto=None):
    """Return latest immutable decision, including an explicit revocation."""
    rev = _events(item, upto).first()
    if rev is None:
        return None
    event = rev.properties.get("publication_event")
    if not isinstance(event, dict) or event.get("kind") not in ("publish", "revoke"):
        return None  # malformed old records never become public evidence
    return {"campaign_revision": "r%03d" % rev.number,
            "campaign_revision_id": str(rev.pk),
            "reviewed_by": rev.created_by.get_username(),
            "reviewed_at": rev.created_at.isoformat(), **event}


def effective(item, upto=None):
    event = latest(item, upto)
    return event if event is not None and event["kind"] == "publish" else None


def published_membership_ids(campaign=None, kind=None):
    """Single effective membership authority for all read-side consumers.

    Only newest decision per campaign counts; a revoke masks older snapshots.
    No Run is inferred published from campaign status or from a matrix cell.
    """
    query = _events()
    if campaign:
        query = query.filter(item__public_id=campaign)
    seen = set()
    ids = set()
    for rev in query.only("item_id", "properties", "number").order_by("item_id", "-number"):
        if rev.item_id in seen:
            continue
        seen.add(rev.item_id)
        event = rev.properties.get("publication_event", {})
        if event.get("kind") != "publish":
            continue
        for pin in event.get("runs", []):
            if isinstance(pin, dict) and pin.get("kind") in ("individual", "composite"):
                if kind is None or pin["kind"] == kind:
                    if isinstance(pin.get("id"), str):
                        ids.add(pin["id"])
    return ids


def effective_ids(campaign=None, kind=None):
    """Shared CURRENT published selector, including Run-level withdrawals."""
    from .run_lifecycle_services import effective_ids as valid
    return valid(campaign=campaign, kind=kind)


def active_manifest(item):
    """Public effective subset; immutable as-published history stays unchanged."""
    from .run_lifecycle_services import state, lookup
    base = effective(item)
    if base is None:
        return None
    ids = effective_ids(item.public_id)
    visible = []
    excluded = []
    for pin in base.get("runs", []):
        if pin["id"] not in ids:
            excluded.append({"status": "withdrawn"})
        else:
            run = lookup(pin["id"])
            if run is None:
                # Orphaned provenance is never silently public.
                excluded.append({"status": "unresolved"})
                continue
            current = state(run)
            visible.append({**pin, "effective_revision": current["revision"],
                            "effective_outcome": current["outcome"]})
    return {**base, "runs": visible, "withdrawn": excluded,
            "active_run_count": len(visible), "as_published_run_count": len(base["runs"]),
            "effective_selection": True}


def _all_runs(item):
    individual = BenchmarkRun.objects.filter(
        session__campaign_snapshot__revision__item=item).select_related(
            "session__campaign_snapshot__revision",
            "session__guide_revision__item", "session__case_pin__test_case__item",
            "session__method_definition", "closing_checkpoint",
            "solution_revision", "solution__item")
    composite = CompositeBenchmarkRun.objects.filter(
        session__campaign_snapshot__revision__item=item).select_related(
            "session__campaign_snapshot__revision",
            "session__guide_revision__item", "session__case_pin__test_case__item",
            "session__method_definition", "closing_checkpoint",
            "framework_revision", "framework")
    return list(individual[:MAX_SELECTED + 501]), list(composite[:MAX_SELECTED + 501])


def _assess(run, kind):
    """Validate original, exact historical setup rather than current guide head."""
    from .run_lifecycle_services import state as run_state
    current = run_state(run)
    session = run.session
    errors = []
    if run.outcome not in ("accepted", "failed"):
        errors.append("not_a_final_outcome")
    if run.closing_checkpoint.state.get("status") != "closed":
        errors.append("missing_closed_checkpoint")
    if not run.result.get("produced_outputs"):
        errors.append("missing_result_artifacts")
    if not isinstance(run.metrics, dict) or run.metrics.get("cost_mode") not in (
            "amount", "flat_rate", "unknown"):
        errors.append("incomplete_measurement")
    # A tariff-selected Run has already passed exact metering on close; do not
    # manufacture missing meters or read prices from a later mutable offer.
    if session.pricing_pins.exists() and not run.metrics.get("reference_cost"):
        errors.append("missing_pinned_tariff_calculation")

    matrix = session.campaign_snapshot.revision.properties.get("matrix_plan") or {}
    evaluation_id = run.provenance.get("evaluation_id")
    if matrix:
        cell = next((c for c in matrix.get("cells", [])
                     if c.get("id") == evaluation_id), None)
        if cell is None or cell.get("decision") != "selected" or (
                cell.get("test_case_id") != session.case_pin.test_case.item.public_id):
            errors.append("not_a_selected_matrix_evaluation")
    elif evaluation_id is not None:
        errors.append("unresolved_matrix_evaluation")

    guide = None
    try:
        configuration = session_configuration(
            session, run.closing_checkpoint.state.get("setup", {}))
        guide = from_revision(session.guide_revision, configuration,
                              require_wiring=bool(session.campaign_snapshot.framework_id))
        # An empty nominal recipe does not document an actual setup.
        if not guide.get("ready") or not any(
                section.get("text") or section.get("url")
                for section in guide.get("sections", [])):
            errors.append("setup_recipe_not_adequate")
    except (SetupCompositionError, ValueError, TypeError, KeyError):
        errors.append("setup_recipe_not_adequate")

    reference = guide.get("recipe") if guide else None
    pin = {
        "id": run.public_id, "kind": kind,
        "effective_revision": current["revision"],
        "effective_revision_id": current["revision_id"],
        "run_uuid": str(run.pk),
        "session_id": session.public_id,
        "closing_checkpoint_id": str(run.closing_checkpoint_id),
        "campaign_source_revision_id": str(session.campaign_snapshot_id),
        "test_case_id": session.case_pin.test_case.item.public_id,
        "test_case_revision_id": str(session.case_pin.revision_id),
        "method_definition_id": str(session.method_definition_id),
        "outcome": current["outcome"],
        "guide": reference,
        "guide_module_pins": run.provenance.get("setup_composition", {}).get(
            "module_pins", []),
        "pricing_offer_revision_ids": sorted(str(p.offer_revision_id)
            for p in session.pricing_pins.all()),
        "evaluation_id": evaluation_id,
        "solution_revision_id": (str(run.solution_revision_id)
                                 if kind == "individual" else None),
        "framework_revision_id": (str(run.framework_revision_id)
                                  if kind == "composite" else None),
    }
    return pin, errors


def candidates(item):
    individuals, composites = _all_runs(item)
    rows = []
    for kind, runs in (("individual", individuals), ("composite", composites)):
        for run in runs:
            pin, errors = _assess(run, kind)
            rows.append({"id": run.public_id, "kind": kind,
                         "outcome": run.outcome, "eligible": not errors,
                         "blockers": errors, "test_case_id": pin["test_case_id"],
                         "guide": pin["guide"]})
    return sorted(rows, key=lambda r: (r["id"], r["kind"]))


def review(item, run_ids):
    if not isinstance(run_ids, list) or not (1 <= len(run_ids) <= MAX_SELECTED):
        raise InvalidCampaign("Select between 1 and 200 completed Run IDs")
    if any(not isinstance(x, str) or not x.startswith("run-") or len(x) > 120
           for x in run_ids) or len(set(run_ids)) != len(run_ids):
        raise InvalidCampaign("Run IDs must be unique permanent Server identifiers")
    individuals, composites = _all_runs(item)
    found = {run.public_id: (run, kind) for kind, rows in (
        ("individual", individuals), ("composite", composites)) for run in rows}
    if set(run_ids) - set(found):
        raise InvalidCampaign("Selected Run does not belong to this campaign")
    pins = []
    from .run_lifecycle_services import state
    for ident in run_ids:
        run, kind = found[ident]
        pin, errors = _assess(run, kind)
        if state(run)["status"] == "withdrawn":\n            errors.append("run_withdrawn")
        if errors:
            raise InvalidTransition(ident + " cannot be published: " + ", ".join(errors))
        pins.append(pin)
    return pins


def _coverage(item):
    from .campaign_matrix_services import projection
    current = item.current_revision
    matrix = projection(item, current)
    counts = matrix.get("summary")
    if counts is None:
        return {"plan": "legacy", "planned_test_cases":
                current.campaign_snapshot.case_pins.count()}
    return {"plan": "matrix", "candidates": counts["candidates"],
            "selected_obligations": counts["selected_obligations"],
            "evaluated": counts["evaluated"], "pending": counts["pending"],
            "in_progress": counts["in_progress"], "waived": counts["waived"],
            "not_selected": counts["not_selected"],
            "full_plan_complete": counts["full_plan_complete"]}


@transaction.atomic
def publish(*, actor, public_id, expected_revision, run_ids, removal_reason=""):
    item = CatalogItem.objects.select_for_update(of=("self",)).select_related(
        "current_revision").get(public_id=public_id, type_slug="campaign")
    current = item.current_revision
    if expected_revision != "r%03d" % current.number:
        raise RevisionConflict("Campaign changed; reload before publishing")
    if current.properties.get("status") != "under_review":
        raise InvalidTransition("Close the campaign for review before publishing")
    if current.properties.get("archived"):
        raise InvalidTransition("Cannot publish an archived campaign")
    from .run_lifecycle_services import state, lookup\n    pins = review(item, run_ids)\n    if any(state(lookup(ident))["status"] != "active" for ident in run_ids):\n        raise InvalidTransition("A withdrawn Run cannot be republished")
    previous = effective(item)
    old = set(x["id"] for x in previous["runs"]) if previous else set()
    removed = old - set(run_ids)
    if removed and (not isinstance(removal_reason, str) or
                    not removal_reason.strip() or len(removal_reason) > 2000):
        raise InvalidCampaign("Explain explicit removal of previously published Runs")
    if not isinstance(removal_reason, str) or len(removal_reason) > 2000:
        raise InvalidCampaign("Removal reason must be text (max 2000)")
    event = {"kind": "publish", "runs": pins,
             "coverage": _coverage(item), "removal_reason": removal_reason.strip(),
             "replaces_revision": previous["campaign_revision_id"] if previous else None}
    changed, _ = modify(actor=actor, public_id=public_id,
                        data={"expected_revision": expected_revision,
                              "_publication_event": event}, action="publish")
    return changed


@transaction.atomic
def revoke(*, actor, public_id, expected_revision):
    item = CatalogItem.objects.select_for_update(of=("self",)).select_related(
        "current_revision").get(public_id=public_id, type_slug="campaign")
    if effective(item) is None:
        raise InvalidTransition("No effective publication to withdraw")
    return modify(actor=actor, public_id=public_id,
                  data={"expected_revision": expected_revision,
                        "_publication_event": {"kind": "revoke", "runs": []}},
                  action="unpublish" if item.current_revision.properties["status"]=="published"
                  else "revoke_publication")[0]
