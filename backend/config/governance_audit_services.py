"""FUT-17: one read-only governance projection over actual committed domain histories.

No second write-side event stream, synthetic audit backfill, navigation tracking or
privilege escalation. Existing atomic CatalogAuditEvent and domain-specific
immutable rows are authoritative. Each producer joins SOURCES, not a new recorder.
"""
from datetime import datetime
from uuid import UUID

from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware

from .models import (
    CatalogAuditEvent, CatalogRevision, CampaignSnapshot, TaskStructureRevision,
    RunAmendment, BenchmarkRun, CompositeBenchmarkRun, UserAccessAuditEvent,
    DataHealthEvent, WorkloadRevision, OpportunitySnapshot, BudgetRevision,
    DeploymentRevision, DeploymentEvent, SessionCheckpoint, UserEnvironmentRevision,
)

PAGE_SIZE = 25
MAX_ROWS = 500
SAFE_TYPES = frozenset({
    "model", "provider", "harness", "framework", "task", "test_case",
    "campaign", "setup_guide", "ai_solution", "evaluation",
    "recommendation", "pricing_offer",
})
SAFE_PROPS = frozenset({
    "publication", "status", "enterprise_accessibility", "mode",
    "release_channel", "version", "objective", "phase", "configuration_version",
})
RUN_METRICS = frozenset({
    "tokens_count", "tokens_multiplier", "tokens_total", "cost_eur",
    "installation_minutes", "interaction_human_minutes",
    "interaction_agent_minutes", "human_review_minutes",
    "human_correction_minutes", "human_total_minutes",
    "quality_score", "information_utility_score",
})
ACCESS_FIELDS = frozenset({"roles", "active", "sessions_revoked"})
SOURCES = {
    "catalog": (CatalogAuditEvent, "created_at", "actor__username"),
    "access": (UserAccessAuditEvent, "created_at", "actor__username"),
    "health": (DataHealthEvent, "created_at", "actor__username"),
    "run": (BenchmarkRun, "created_at", "recorded_by__username"),
    "composite_run": (CompositeBenchmarkRun, "created_at", "recorded_by__username"),
    "session": (SessionCheckpoint, "saved_at", "actor__username"),
    "workload": (WorkloadRevision, "created_at", "created_by__username"),
    "opportunity": (OpportunitySnapshot, "created_at", "created_by__username"),
    "budget": (BudgetRevision, "created_at", "created_by__username"),
    "deployment_revision": (DeploymentRevision, "created_at", "created_by__username"),
    "deployment_event": (DeploymentEvent, "created_at", "actor__username"),
    "environment": (UserEnvironmentRevision, "created_at", None),
}


class InvalidAudit(ValueError):
    pass


class HiddenAudit(PermissionError):
    pass


def allowed_sources(user):
    sources = set(SOURCES) - {"access", "environment"}
    if user.has_perm("auth.users_manage"):
        sources.update(("access", "environment"))
    return sources


def _actor(user):
    return user.get_username() if user else None


def catalog_summary(event):
    """One authoritative catalog-event adapter, also used by Workgroup Activity."""
    return {
        "id": str(event.id), "occurred_at": event.created_at.isoformat(),
        "actor": _actor(event.actor),
        "actor_roles_at_event": None, "business_unit": None,
        "operation": event.action, "object_type": event.item.type_slug,
        "object_id": event.item.public_id,
        "object_name": event.revision.display_name,
        "revision": "r%03d" % event.revision.number,
        "revision_id": str(event.revision_id),
        "outcome": "succeeded",
    }


def _meta(source, row):
    if source == "catalog":
        result = catalog_summary(row)
        amendment = getattr(row, "run_amendment", None)
        if amendment:
            run = amendment.individual_run or amendment.composite_run
            result.update(object_type="run", object_id=run.public_id,
                          object_name=None,
                          revision="r%03d" % amendment.number,
                          revision_id=str(amendment.pk))
        return result
    if source == "access":
        return {"id": str(row.id), "occurred_at": row.created_at.isoformat(),
            "actor": _actor(row.actor), "operation": row.action,
            "object_type": "access", "object_id": "user:" + str(row.subject_id),
            "object_name": None, "revision": None, "revision_id": None}
    if source == "health":
        return {"id": str(row.id), "occurred_at": row.created_at.isoformat(),
            "actor": _actor(row.actor), "operation": row.action,
            "object_type": "health", "object_id": row.issue.public_id,
            "object_name": None, "revision": None, "revision_id": None}
    if source in ("run", "composite_run"):
        return {"id": str(row.id), "occurred_at": row.created_at.isoformat(),
            "actor": _actor(row.recorded_by), "operation": "recorded",
            "object_type": "run", "object_id": row.public_id,
            "object_name": None, "revision": "r001", "revision_id": str(row.id)}
    if source == "session":
        return {"id": str(row.id), "occurred_at": row.saved_at.isoformat(),
            "actor": _actor(row.actor), "operation": row.action,
            "object_type": "session", "object_id": row.session.public_id,
            "object_name": None, "revision": "r%03d" % row.number,
            "revision_id": str(row.id)}
    if source == "environment":
        return {"id": str(row.id), "occurred_at": row.created_at.isoformat(),
            "actor": _actor(row.user), "operation": "revised",
            "object_type": "environment", "object_id": "user:" + str(row.user_id),
            "object_name": None, "revision": "r%03d" % row.number,
            "revision_id": str(row.id)}
    parent, kind = {
        "workload": (row.profile, "workload"),
        "opportunity": (row.scenario, "opportunity"),
        "budget": (row.budget, "budget"),
        "deployment_revision": (row.target, "deployment"),
        "deployment_event": (row.target, "deployment"),
    }[source]
    number = getattr(row, "number", None)
    return {"id": str(row.id),
        "occurred_at": row.created_at.isoformat(),
        "actor": _actor(getattr(row, "actor", None) or getattr(row, "created_by", None)),
        "operation": row.action if source == "deployment_event" else
                     ("created" if number == 1 else "revised"),
        "object_type": kind, "object_id": parent.public_id,
        "object_name": None,
        "revision": "r%03d" % number if number is not None else None,
        "revision_id": str(row.id) if number is not None else
                       str(row.target_revision_id)}


def summary(source, row):
    doc = _meta(source, row)
    doc["id"] = source + ":" + doc["id"]
    doc["source"] = source
    doc["outcome"] = "committed"
    doc["origin"] = "unknown"  # Never pretend historical browser/API provenance.
    doc["actor_username_is_current"] = doc["actor"] is not None
    doc["actor_roles_at_event"] = None
    doc["correlation_id"] = None
    # An amendment is already identified by its own authoritative CatalogAuditEvent.
    if source == "catalog" and getattr(row, "run_amendment", None):
        doc["correlation_id"] = str(row.id)
    return doc


def _safe_offer(properties):
    return {
        "currency": properties.get("currency"),
        "billing_owner": properties.get("billing_owner"),
        "status": properties.get("status"),
        "lines": sorted([
            {k: line[k] for k in ("charge_id", "charge_type", "family", "meter",
                                  "rate", "unit_size", "period", "tiers",
                                  "provider_credit_namespace") if k in line}
            for line in properties.get("lines", []) if isinstance(line, dict)
        ], key=lambda x: str(x.get("charge_id", ""))),
    }


def _campaign_links(rev):
    snap = CampaignSnapshot.objects.filter(revision=rev).first()
    if snap is None:
        return {}
    return {
        "relations.task": snap.fixed_task.item.public_id if snap.fixed_task else None,
        "relations.guide": snap.guide.public_id if snap.guide else None,
        "relations.framework": snap.framework.public_id if snap.framework else None,
        "relations.cases": sorted(
            x.test_case.item.public_id + "@" + str(x.revision_id)
            for x in snap.case_pins.select_related("test_case__item")),
        "relations.components": sorted(
            x.kind + ":" + x.component.public_id + "@" + str(x.revision_id)
            for x in snap.component_pins.select_related("component")),
        "relations.pricing": sorted(
            x.source_key + ":" + x.offer.public_id + "@" + str(x.offer_revision_id)
            for x in snap.pricing_pins.select_related("offer")),
        "relations.participants": sorted(
            x.participant.public_id + ":" + x.model.public_id + ":" +
            x.provider.public_id + ":" + x.harness.public_id
            for x in snap.participant_pins.select_related(
                "participant", "model", "provider", "harness")),
    }


def _catalog_snapshot(rev):
    if rev is None:
        return {}
    typ = rev.item.type_slug
    p = rev.properties if isinstance(rev.properties, dict) else {}
    result = {"display_name": rev.display_name}
    if typ == "pricing_offer":
        result.update({"pricing": _safe_offer(p)})
    else:
        result.update({"properties": {k: p[k] for k in SAFE_PROPS if k in p
                                      and isinstance(p[k], (str, bool, int, float, type(None)))}})
    if typ == "campaign":
        result.update(_campaign_links(rev))
    if typ == "task":
        node = TaskStructureRevision.objects.filter(revision=rev).select_related(
            "parent__item").first()
        if node:
            result.update({"relations.parent": node.parent.item.public_id if node.parent else None,
                           "relations.position": node.position})
    if typ == "recommendation":
        s = getattr(rev, "recommendation_snapshot", None)
        if s:
            result["relations.task"] = s.task.item.public_id
            result["relations.solution"] = s.solution.item.public_id
    return result


def _run_metrics(values):
    if not isinstance(values, dict):
        return {}
    return {k: values[k] for k in RUN_METRICS if k in values and
            isinstance(values[k], (str, int, float, type(None)))}


def _state(source, row):
    if source == "catalog":
        amend = getattr(row, "run_amendment", None)
        if amend is not None:
            original = amend.individual_run or amend.composite_run
            prev = RunAmendment.objects.filter(
                **({"individual_run": original} if amend.individual_run_id else
                   {"composite_run": original}),
                number=amend.number-1).first()
            previous = _run_metrics(prev.metrics if prev else original.metrics)
            current = _run_metrics(amend.metrics)
            previous["outcome"] = prev.outcome if prev else original.outcome
            current["outcome"] = amend.outcome
            previous["withdrawn"] = bool(prev and prev.action == "withdrawn")
            current["withdrawn"] = amend.action == "withdrawn"
            return previous, current
        previous = CatalogRevision.objects.filter(
            item=row.item, number=row.revision.number - 1).first()
        return _catalog_snapshot(previous), _catalog_snapshot(row.revision)
    if source == "access":
        changes = {k: v for k, v in row.details.items()
                   if k in ACCESS_FIELDS and isinstance(v, dict) and
                   set(v).issubset({"from", "to"})}
        before = {k: v.get("from") for k, v in changes.items()}
        after = {k: v.get("to") for k, v in changes.items()}
        return before, after
    if source == "health":
        changes = {k: v for k, v in row.detail.items()
                   if k in {"from", "to", "check"} and
                   isinstance(v, (str, type(None)))}
        return {"status": changes.get("from")}, {"status": changes.get("to"),
                                               "check_version": changes.get("check")}
    if source in ("run", "composite_run"):
        return {}, {**_run_metrics(row.metrics), "outcome": row.outcome,
                    "configuration_revision_id": str(
                        row.solution_revision_id if source == "run"
                        else row.framework_revision_id)}
    if source == "session":
        previous = SessionCheckpoint.objects.filter(
            session=row.session, number=row.number-1).first()
        # Payload has prompts/evidence/secret-bearing session content.
        return ({"checkpoint": previous.number, "operation": previous.action} if previous else {},
                {"checkpoint": row.number, "operation": row.action})
    if source == "environment":
        previous = UserEnvironmentRevision.objects.filter(
            user=row.user, number=row.number-1).first()
        return ({"available_os": previous.available_os} if previous else {},
                {"available_os": row.available_os})
    if source == "workload":
        previous = WorkloadRevision.objects.filter(
            profile=row.profile, number=row.number-1).first()
        return ({"headcount": previous.headcount} if previous else {},
                {"headcount": row.headcount})
    if source == "opportunity":
        previous = OpportunitySnapshot.objects.filter(
            scenario=row.scenario, number=row.number-1).first()
        def safe(o):
            if not o:
                return {}
            return {"benchmark_weight": o.assumptions.get("benchmark_weight"),
                    "choice_count": len(o.assumptions.get("choices", []))}
        return safe(previous), safe(row)
    if source == "budget":
        previous = BudgetRevision.objects.filter(budget=row.budget, number=row.number-1).first()
        def safe(o):
            return ({"period_months": o.assumptions.get("period_months"),
                     "include_active": o.assumptions.get("include_active"),
                     "candidate_count": len(o.assumptions.get("items", []))}
                    if o else {})
        return safe(previous), safe(row)
    if source == "deployment_revision":
        previous = DeploymentRevision.objects.filter(
            target=row.target, number=row.number-1).first()
        def safe(o):
            if not o:
                return {}
            return {"state": o.selection.get("status"),
                    "seats": len(o.selection.get("seats", [])),
                    "components": sorted(x.get("id", "") for x in
                                         o.selection.get("components", []) if isinstance(x, dict))}
        return safe(previous), safe(row)
    if source == "deployment_event":
        return {}, {"operation": row.action,
                    "component": row.component.public_id if row.component else None,
                    "target_revision_id": str(row.target_revision_id)}
    return {}, {}


def _diff(before, after, prefix=""):
    changes = []
    keys = sorted(set(before) | set(after))
    for key in keys:
        path = prefix + "." + key if prefix else key
        a, b = before.get(key), after.get(key)
        if a == b:
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            changes.extend(_diff(a, b, path))
        else:
            changes.append({"field": path,
                            "operation": "added" if key not in before else
                                         "removed" if key not in after else "changed",
                            "before": a if key in before else None,
                            "after": b if key in after else None})
    return changes[:100]


def _allowed(source, user):
    if source not in SOURCES:
        raise InvalidAudit("unknown_source")
    if source not in allowed_sources(user):
        raise HiddenAudit("source_access_denied")


def _restricted_catalog_change(row):
    previous = CatalogRevision.objects.filter(
        item=row.item, number=row.revision.number-1).first()
    if previous is None:
        return False
    if row.revision.properties != previous.properties:
        old_visible = _catalog_snapshot(previous).get("properties")
        new_visible = _catalog_snapshot(row.revision).get("properties")
        if row.item.type_slug == "pricing_offer":
            old_visible = _safe_offer(previous.properties)
            new_visible = _safe_offer(row.revision.properties)
        if old_visible == new_visible:
            return True
    return False


def event_detail(source, row, user):
    _allowed(source, user)
    data = summary(source, row)
    previous, current = _state(source, row)
    changes = _diff(previous, current)
    return {"event": data, "changes": changes,
            "restricted_change_present": (source == "catalog" and
                not getattr(row, "run_amendment", None) and
                row.revision.number > 1 and
                _restricted_catalog_change(row)),
            "before_revision_id": (
                str(row.revision.item.revisions.filter(number=row.revision.number-1)
                    .values_list("pk", flat=True).first())
                if source == "catalog" and not getattr(row, "run_amendment", None)
                and row.revision.number > 1 else None),
            "after_revision_id": data["revision_id"],
            "detail_completeness": "whitelisted_source_fields_only",
            "restricted_fields": "excluded_not_recoverable_from_audit",
            "actor_attribution": "current_username_not_historical_snapshot"
            if data["actor"] else "unknown_not_inferred",
            "origin": "unknown", "correlation": data["correlation_id"]}


def _parse_dates(params):
    dates = []
    for key in ("from", "to"):
        raw = params.get(key)
        if not raw:
            dates.append(None)
            continue
        if len(raw) > 50:
            raise InvalidAudit("bad_date")
        dt = parse_datetime(raw)
        if dt is None or not is_aware(dt):
            raise InvalidAudit("timezone_required")
        dates.append(dt)
    if dates[0] and dates[1] and dates[0] > dates[1]:
        raise InvalidAudit("date_order_invalid")
    return dates


def parse(params, user):
    supported = {"source", "object_type", "object_id", "actor", "action", "field",
                 "from", "to", "page", "format"}
    if set(params) - supported:
        raise InvalidAudit("unsupported_filter")
    source = params.get("source", "all")
    if source != "all":
        _allowed(source, user)
    for name, maxlen in (("object_type", 36), ("object_id", 120),
                         ("actor", 150), ("action", 32), ("field", 120)):
        if len(params.get(name, "")) > maxlen:
            raise InvalidAudit("filter_too_long")
    try:
        page = int(params.get("page", "1"))
    except (ValueError, TypeError):
        raise InvalidAudit("invalid_page") from None
    if not 1 <= page <= MAX_ROWS // PAGE_SIZE:
        raise InvalidAudit("page_out_of_range")
    start, end = _parse_dates(params)
    return {"source": source, "object_type": params.get("object_type", ""),
        "object_id": params.get("object_id", ""), "actor": params.get("actor", ""),
        "action": params.get("action", ""), "field": params.get("field", ""),
        "from": start, "to": end, "page": page}


def _query(source, filters):
    model, timefield, actorfield = SOURCES[source]
    qs = model.objects.all()
    object_id = filters.get("object_id", "")
    if object_id:
        if source == "catalog":
            if object_id.startswith("run-"):
                qs = qs.filter(Q(run_amendment__individual_run__public_id=object_id) |
                               Q(run_amendment__composite_run__public_id=object_id))
            else:
                qs = qs.filter(item__public_id=object_id)
        elif source in ("run", "composite_run", "session", "health", "workload",
                        "opportunity", "budget", "deployment_revision", "deployment_event"):
            field = {"run": "public_id", "composite_run": "public_id",
                     "session": "session__public_id", "health": "issue__public_id",
                     "workload": "profile__public_id",
                     "opportunity": "scenario__public_id", "budget": "budget__public_id",
                     "deployment_revision": "target__public_id",
                     "deployment_event": "target__public_id"}[source]
            qs = qs.filter(**{field: object_id})
        elif source in ("access", "environment"):
            try:
                uid = int(object_id.removeprefix("user:"))
            except ValueError:
                return []
            qs = qs.filter(**{"subject_id" if source == "access"
                              else "user_id": uid})
    if source == "catalog":
        qs = qs.filter(item__type_slug__in=SAFE_TYPES).select_related(
            "item", "revision", "actor")
    if source == "access":
        qs = qs.select_related("actor", "subject")
    if source == "health":
        qs = qs.select_related("actor", "issue")
    if source in ("workload", "opportunity", "budget", "deployment_revision",
                  "deployment_event"):
        qs = qs.select_related("profile" if source == "workload" else
                              "scenario" if source == "opportunity" else
                              "budget" if source == "budget" else "target")
    if source in ("run", "composite_run"):
        qs = qs.select_related("recorded_by")
    if source == "session":
        qs = qs.select_related("actor", "session")
    if source == "environment":
        qs = qs.select_related("user")
    if filters["actor"] and actorfield:
        qs = qs.filter(**{actorfield: filters["actor"]})
    elif filters["actor"] and source == "environment":
        qs = qs.filter(user__username=filters["actor"])
    elif filters["actor"] and source != "environment":
        return []
    if filters["from"]:
        qs = qs.filter(**{timefield + "__gte": filters["from"]})
    if filters["to"]:
        qs = qs.filter(**{timefield + "__lte": filters["to"]})
    return list(qs.order_by("-" + timefield, "-id")[:MAX_ROWS + 1])


def collect(filters, user):
    choices = (sorted(allowed_sources(user)) if filters["source"] == "all"
               else [filters["source"]])
    events = []
    for source in choices:
        for row in _query(source, filters):
            meta = summary(source, row)
            if filters["object_type"] and meta["object_type"] != filters["object_type"]:
                continue
            if filters["object_id"] and meta["object_id"] != filters["object_id"]:
                continue
            if filters["action"] and meta["operation"] != filters["action"]:
                continue
            if filters["actor"] and meta["actor"] != filters["actor"]:
                continue
            if filters["field"]:
                before, after = _state(source, row)
                if not any(x["field"] == filters["field"] for x in _diff(before, after)):
                    continue
            events.append(meta)
    events.sort(key=lambda x: (x["occurred_at"], x["id"]), reverse=True)
    return events


def find(source, pk, user):
    _allowed(source, user)
    try:
        identifier = UUID(pk)
    except (ValueError, TypeError):
        raise InvalidAudit("invalid_event_id") from None
    # Explicit ID lookup, not the most recent 500-events global query.
    q = SOURCES[source][0].objects.filter(pk=identifier)
    if source == "catalog":
        q = q.filter(item__type_slug__in=SAFE_TYPES)
    row = q.first()
    if row is None:
        return None
    return event_detail(source, row, user)
