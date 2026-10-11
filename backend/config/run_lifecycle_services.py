"""FUT-11 — one authoritative current-effective Run lifecycle, no raw mutation.

r001 is the original immutable Run. r002+ are immutable amendments attached to
the existing Catalog audit stream. Historical snapshots never point to an
amendment implicitly. Current projections consume state() and effective_ids().
"""
import copy
import json
import math

from django.db import transaction

from .activity_services import record_catalog_event
from .catalog_services import RevisionConflict
from .models import BenchmarkRun, CompositeBenchmarkRun, RunAmendment


class InvalidAmendment(ValueError):
    pass


SCORES = frozenset(("quality_score", "information_utility_score"))
NUMBERS = frozenset(("installation_minutes", "interaction_human_minutes",
                     "interaction_agent_minutes", "human_review_minutes",
                     "human_correction_minutes", "cost_eur"))
COUNTERS = frozenset(("tokens_count", "tokens_multiplier"))
PATCH = SCORES | NUMBERS | COUNTERS
MULTIPLIERS = (1, 10, 100, 1000, 1000000)


def _kind(run):
    return "individual" if isinstance(run, BenchmarkRun) else "composite"


def _query(run):
    if isinstance(run, BenchmarkRun):
        return RunAmendment.objects.filter(individual_run=run)
    return RunAmendment.objects.filter(composite_run=run)


def lookup(identifier):
    if not isinstance(identifier, str) or not identifier.startswith("run-") or len(identifier)>120:
        return None
    row = BenchmarkRun.objects.select_related(
        "session__campaign_snapshot__revision__item",
        "session__campaign_snapshot__revision").filter(public_id=identifier).first()
    if row is None:
        row = CompositeBenchmarkRun.objects.select_related(
            "session__campaign_snapshot__revision__item",
            "session__campaign_snapshot__revision").filter(public_id=identifier).first()
    return row


def last(run):
    return _query(run).order_by("-number").first()


def state(run, *, amendment=None):
    """Current effective declared data, with original immutable facts accessible separately."""
    entry = amendment if amendment is not None else last(run)
    withdrawn = bool(entry and entry.action == "withdrawn")
    return {
        "revision": "r%03d" % (entry.number if entry else 1),
        "revision_id": str(entry.pk) if entry else str(run.pk),
        "status": "withdrawn" if withdrawn else "active",
        "outcome": entry.outcome if entry else run.outcome,
        "metrics": copy.deepcopy(entry.metrics if entry else run.metrics),
        "reason": entry.reason if entry else None,
        "amended_at": entry.created_at.isoformat() if entry else None,
    }


def decorate(run, payload):
    current = state(run)
    payload.update({
        "revision": current["revision"],
        "effective_status": current["status"],
        "outcome": current["outcome"],
        "metrics": current["metrics"],
        "amended_at": current["amended_at"],
    })
    # Private callers may inspect raw_session_state independently. No historical
    # raw checkpoint is reinterpreted as a corrected source.
    return payload


def effective_ids(campaign=None, kind=None):
    """Authoritative current measured membership; revocations are read-through.

    All current read models and access guards must use this same function.
    A withdrawn Run disappears immediately from active results without editing
    the historical Campaign publication revision.
    """
    from .publication_services import published_membership_ids
    ids = published_membership_ids(campaign=campaign, kind=kind)
    if not ids:
        return set()
    withdrawn_individual = set(RunAmendment.objects.filter(
        individual_run__public_id__in=ids, action="withdrawn"
    ).values_list("individual_run__public_id", flat=True))
    withdrawn_composite = set(RunAmendment.objects.filter(
        composite_run__public_id__in=ids, action="withdrawn"
    ).values_list("composite_run__public_id", flat=True))
    # Terminal withdrawal: correction after withdrawal is rejected. Existing
    # historical withdraw records continue to invalidate public membership.
    return ids - withdrawn_individual - withdrawn_composite


def _checked_metrics(current, patch, run, observations=None):
    if not isinstance(patch, dict) or not patch or set(patch) - PATCH:
        raise InvalidAmendment("Nonempty declared metrics_patch with supported fields required")
    out = copy.deepcopy(current)
    for key, value in patch.items():
        if key == "tokens_count":
            if value is not None and (type(value) is not int or value < 0 or value > 10**12):
                raise InvalidAmendment("tokens_count must be a bounded integer or null")
        elif key == "tokens_multiplier":
            if type(value) is not int or value not in MULTIPLIERS:
                raise InvalidAmendment("Invalid token multiplier")
        elif value is not None and (type(value) not in (int, float) or not math.isfinite(value)
                                   or value < 0 or value > (100 if key in SCORES else 10**9)):
            raise InvalidAmendment(key + " must be a finite nonnegative bounded number or null")
        out[key] = value
    count = out.get("tokens_count")
    multiple = out.get("tokens_multiplier", 1)
    if count is None and multiple != 1:
        raise InvalidAmendment("Unknown tokens require multiplier 1")
    if count is not None and count * multiple > 10**12:
        raise InvalidAmendment("Token total exceeds limit")
    out["tokens_total"] = count * multiple if count is not None else None
    times = [out.get(k) for k in ("installation_minutes", "interaction_human_minutes",
                                  "human_review_minutes", "human_correction_minutes")]
    out["human_total_minutes"] = sum(times) if all(x is not None for x in times) else None
    from .run_cost_services import contract, quote, InvalidMeter, MissingMeter
    existing_contract = contract(run.session)
    if existing_contract is not None:
        if "cost_eur" in patch:
            raise InvalidAmendment("Tariff cost is derived from original pinned offers")
        if observations is not None:
            try:
                quoted = quote(run.session, observations)
            except (MissingMeter, InvalidMeter) as exc:
                raise InvalidAmendment(str(exc)) from exc
            out["reference_cost"] = quoted
            values = quoted["variable_reference_by_currency"]
            if not quoted["variable_charges"]:
                out.update(cost_mode="flat_rate",cost_eur=None)
            elif set(values) == {"EUR"}:
                out.update(cost_mode="amount",cost_eur=float(values["EUR"]))
            else:
                out.update(cost_mode="unknown",cost_eur=None)
    elif observations is not None:
        raise InvalidAmendment("Legacy Runs have no pinned tariff meter contract")
    if "cost_eur" in patch and out.get("cost_mode") != "amount":
        raise InvalidAmendment("Only an original amount-cost Run can have a corrected EUR amount")
    if out.get("cost_mode") == "amount" and (
            type(out.get("cost_eur")) not in (int,float) or
            not math.isfinite(out["cost_eur"]) or out["cost_eur"] < 0):
        raise InvalidAmendment("Known amount-cost requires a nonnegative EUR value")
    # No replacement of trace, evidence, setup, DoD or method. This is only
    # supersession of declared quantitative measurements.
    if len(json.dumps(out, allow_nan=False, ensure_ascii=False)) > 65536:
        raise InvalidAmendment("Corrected metrics exceed 64 KiB")
    return out


@transaction.atomic
def change(*, actor, identifier, expected_revision, action, reason,
           metrics_patch=None, observations=None, outcome=None):
    run = lookup(identifier)
    if run is None:
        raise InvalidAmendment("Unknown original Run")
    # Lock original permanent Run to serialize amendment writes. No update to
    # that Run is executed, and its immutability trigger remains in force.
    klass = type(run)
    run = klass.objects.select_for_update(of=("self",)).get(pk=run.pk)
    from .publication_services import published_membership_ids
    if identifier not in published_membership_ids():
        raise InvalidAmendment("Only a published Run can be corrected or withdrawn")
    previous = last(run)
    number = previous.number if previous else 1
    if expected_revision != "r%03d" % number:
        raise RevisionConflict("Run revision changed; reload before correction/withdrawal")
    if previous and previous.action == "withdrawn":
        raise InvalidAmendment("Withdrawn Run is terminal; publish a new Run instead")
    if action not in ("corrected", "withdrawn"):
        raise InvalidAmendment("Unsupported Run lifecycle action")
    if not isinstance(reason, str) or not 8 <= len(reason.strip()) <= 2000:
        raise InvalidAmendment("A meaningful reason (8–2000 characters) is mandatory")
    if action == "withdrawn":
        if metrics_patch is not None or observations is not None or outcome is not None:
            raise InvalidAmendment("Withdrawal cannot silently rewrite measurements")
        amended = state(run)
        metrics, final_outcome = amended["metrics"], amended["outcome"]
    else:
        if outcome is not None and outcome not in ("accepted", "failed"):
            raise InvalidAmendment("DoD must be accepted or failed")
        if metrics_patch is None and observations is None and outcome is None:
            raise InvalidAmendment("No changes supplied")
        amended = state(run)
        metrics = (_checked_metrics(amended["metrics"], metrics_patch or {}, run, observations)
                   if metrics_patch is not None else copy.deepcopy(amended["metrics"]))
        if metrics_patch is None and observations is not None:
            # An explicit metering-only correction uses the same tariff path.
            metrics = _checked_metrics(amended["metrics"], {"tokens_count":
                amended["metrics"].get("tokens_count")}, run, observations)
        final_outcome = outcome or amended["outcome"]
        metrics["outcome"] = final_outcome
        if metrics == amended["metrics"] and final_outcome == amended["outcome"]:
            raise InvalidAmendment("No effective change")
    camp = run.session.campaign_snapshot.revision.item
    event = record_catalog_event(
        item=camp, revision=camp.current_revision, actor=actor,
        action="run_corrected" if action == "corrected" else "run_withdrawn")
    amendment = RunAmendment.objects.create(
        individual_run=run if isinstance(run, BenchmarkRun) else None,
        composite_run=run if isinstance(run, CompositeBenchmarkRun) else None,
        number=number + 1, action=action, outcome=final_outcome,
        metrics=metrics, reason=reason.strip(), created_by=actor, audit_event=event)
    return amendment


def history(run):
    result = [{"revision": "r001", "revision_id": str(run.pk),
               "action": "original", "outcome": run.outcome,
               "metrics": run.metrics, "reason": None,
               "by": run.recorded_by.get_username(),
               "at": run.created_at.isoformat()}]
    for amend in _query(run).select_related("created_by", "audit_event").order_by("number"):
        result.append({
            "revision": "r%03d" % amend.number, "revision_id": str(amend.pk),
            "action": amend.action, "outcome": amend.outcome,
            "metrics": amend.metrics, "reason": amend.reason,
            "by": amend.created_by.get_username(), "at": amend.created_at.isoformat(),
            "audit_event_id": str(amend.audit_event_id),
        })
    return result
