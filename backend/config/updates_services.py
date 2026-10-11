"""UX-R06: one published-only Workgroup Updates / What's New read projection.

Derived from existing authoritative objects and their current *effective*
published state. This service creates no business object, no status model and no
assignment: it is a read model. Drafts, internal hypotheses and private
discussion content are never included, and administrative/audit events or the
privileged Activity Feed are deliberately not reused as a public news source.
Every entry carries the exact source object ID and the source revision it was
derived from so a reader can open the authoritative origin.
"""
from django.db.models import Q
from django.utils import timezone

from .models import CatalogItem, RecommendationSnapshot
from . import publication_services, recommendation_services
from .results_explorer_services import explore

MAX_ITEMS = 40
RECENT_MEASURED_RUNS = 12
RECENT_TECHNOLOGY = 5
COMPONENT_TYPES = ("model", "provider", "harness", "framework")

FAILED_NOTE = ("A published failed-DoD Run is recorded negative evidence; it is "
               "never an endorsement or an automatically positive recommendation.")
MEASURED_NOTE = ("Measured Server evidence under its recorded method. Withdrawn or "
                 "corrected sources are excluded by the shared published selector.")
THEORETICAL_NOTE = ("Theoretical Forecasts, internal Watch hypotheses and unreviewed "
                    "drafts are deliberately absent from this published view.")
TECHNOLOGY_NOTE = ("Catalog availability is shared Workgroup metadata, not measured "
                   "experimental evidence.")


def _display_names(type_slug, ids):
    wanted = {value for value in ids if value}
    if not wanted:
        return {}
    rows = (CatalogItem.objects.filter(type_slug=type_slug, public_id__in=wanted)
            .select_related("current_revision"))
    return {row.public_id: (row.current_revision.display_name if row.current_revision
                            else row.public_id) for row in rows}


def _published_observations():
    """Current effective published measured evidence, via the shared selector."""
    rows = []
    for kind in ("individual", "composite"):
        data = explore(None, {"scope": "published", "view": "task", "kind": kind})
        rows.extend(entry for entry in data["results"]
                    if entry["evidence_class"] == "measured")
    rows.sort(key=lambda entry: (entry["created_at"], entry["id"]), reverse=True)
    return rows


def _measured_items(observations):
    recent = observations[:RECENT_MEASURED_RUNS]
    task_names = _display_names("task", [entry["task_id"] for entry in recent])
    solution_names = _display_names(
        "ai_solution", [entry["solution_id"] for entry in recent if entry["solution_id"]])
    framework_names = _display_names(
        "framework", [entry["framework_id"] for entry in recent if entry["framework_id"]])
    items = []
    for entry in recent:
        candidate_id = entry["solution_id"] or entry["framework_id"]
        name = (solution_names.get(candidate_id) or framework_names.get(candidate_id) or
                candidate_id or entry["candidate"])
        task_name = task_names.get(entry["task_id"], entry["task_id"])
        accepted = entry["outcome"] == "accepted"
        items.append({
            "kind": "measured_result",
            "title": str(name) + " on " + str(task_name),
            "summary": ("Outcome: accepted Definition of Done." if accepted else
                        "Outcome: failed Definition of Done (negative evidence)."),
            "notice": FAILED_NOTE if not accepted else MEASURED_NOTE,
            "published_at": entry["created_at"],
            "timestamp_basis": "run_recorded_at",
            "source": {"object_id": entry["id"],
                       "revision": entry["effective_revision"] or "r001",
                       "section": "results"},
            "parent": {"campaign_id": entry["campaign_id"],
                       "test_case_id": entry["test_case_id"],
                       "task_id": entry["task_id"],
                       "solution_id": entry["solution_id"],
                       "framework_id": entry["framework_id"]},
            "measured": True,
        })
    return items


def _campaign_items(observations):
    counts = {}
    for entry in observations:
        counts[entry["campaign_id"]] = counts.get(entry["campaign_id"], 0) + 1
    items = []
    for item in (CatalogItem.objects.filter(type_slug="campaign")
                 .select_related("current_revision")):
        event = publication_services.effective(item)
        if event is None:
            continue
        name = item.current_revision.display_name if item.current_revision else item.public_id
        items.append({
            "kind": "campaign_published",
            "title": str(name),
            "summary": ("%d active published measured Run(s) from this publication."
                        % counts.get(item.public_id, 0)),
            "notice": "Publication is an explicit reviewed decision; reopening or "
                      "editing the working draft does not unpublish this evidence.",
            "published_at": event["reviewed_at"],
            "timestamp_basis": "publication_decision",
            "source": {"object_id": item.public_id,
                       "revision": event["campaign_revision"],
                       "section": "benchmark"},
            "measured": False,
        })
    return items


def _recommendation_items():
    items = []
    for item in CatalogItem.objects.filter(type_slug="recommendation"):
        revision = recommendation_services.published_revision(item)
        if revision is None:
            continue
        snapshot = RecommendationSnapshot.objects.filter(revision=revision).first()
        props = revision.properties or {}
        task_id = snapshot.task.item.public_id if snapshot else None
        solution_id = snapshot.solution.item.public_id if snapshot else None
        pinned_runs = snapshot.run_pins.count() if snapshot else 0
        items.append({
            "kind": "recommendation_published",
            "title": revision.display_name or item.public_id,
            "summary": ("Editorial decision: %s. Pinned to Task %s and measured Solution %s "
                        "with %d original Run(s)."
                        % (props.get("decision", "not specified"), task_id or "unavailable",
                           solution_id or "unavailable", pinned_runs)),
            "notice": "An editorial opinion is descriptive context. It never overrides the "
                      "measured methodology result and is not a ranking.",
            "published_at": ((snapshot.reviewed_at or revision.created_at).isoformat()
                             if snapshot else revision.created_at.isoformat()),
            "timestamp_basis": ("publication_decision" if snapshot and snapshot.reviewed_at
                                else "revision_created_at"),
            "source": {"object_id": item.public_id,
                       "revision": "r%03d" % revision.number,
                       "section": "recommendations"},
            "pins": {"task_id": task_id, "solution_id": solution_id,
                     "original_run_pins": pinned_runs},
            "measured": False,
        })
    return items


def _guide_items():
    items = []
    rows = (CatalogItem.objects
            .filter(type_slug="setup_guide",
                    current_revision__properties__publication="published")
            .select_related("current_revision"))
    for item in rows:
        revision = item.current_revision
        props = revision.properties or {}
        items.append({
            "kind": "guide_published",
            "title": revision.display_name or item.public_id,
            "summary": (props.get("description") or
                        "Published reusable Setup Guide / recipe revision."),
            "notice": "A setup recipe is documentation for an exact configuration; it is "
                      "not a compatibility guarantee for another environment.",
            "published_at": revision.created_at.isoformat(),
            "timestamp_basis": "revision_created_at",
            "source": {"object_id": item.public_id,
                       "revision": "r%03d" % revision.number,
                       "section": "guides"},
            "measured": False,
        })
    return items


def _watch_items():
    items = []
    rows = (CatalogItem.objects
            .filter(type_slug="watch_entry",
                    current_revision__properties__visibility="published")
            .select_related("current_revision"))
    for item in rows:
        revision = item.current_revision
        props = revision.properties or {}
        items.append({
            "kind": "watch_published",
            "title": revision.display_name or item.public_id,
            "summary": (props.get("hypothesis") or props.get("summary") or
                        "Reviewed Watch signal made visible."),
            "notice": ("A reviewed signal is not a measured Run and creates neither a Task "
                       "nor an obligation to run a benchmark."),
            "published_at": revision.created_at.isoformat(),
            "timestamp_basis": "revision_created_at",
            "source": {"object_id": item.public_id,
                       "revision": "r%03d" % revision.number,
                       "section": "watch"},
            "measured": False,
        })
    return items


def _technology_items():
    rows = (CatalogItem.objects.filter(type_slug__in=COMPONENT_TYPES)
            .select_related("current_revision").order_by("-created_at", "-id")
            [:RECENT_TECHNOLOGY])
    items = []
    for item in rows:
        revision = item.current_revision
        items.append({
            "kind": "technology_available",
            "title": "%s · %s" % (item.type_slug, revision.display_name if revision
                                  else item.public_id),
            "summary": "Newly recorded %s component available in the shared Catalog."
                       % item.type_slug,
            "notice": TECHNOLOGY_NOTE,
            "published_at": item.created_at.isoformat(),
            "timestamp_basis": "record_created_at",
            "source": {"object_id": item.public_id,
                       "revision": "r%03d" % revision.number if revision else "",
                       "section": "catalog"},
            "measured": False,
        })
    return items


def _excluded():
    """Counts of existing records deliberately withheld by this published view."""
    def not_marked(key, value):
        # Absent/non-string values stay visible to the count: an unset publication
        # field means "not published", never "published".
        return Q(**{"current_revision__properties__" + key + "__isnull": True}) | ~Q(
            **{"current_revision__properties__" + key: value})

    unpublished_campaigns = 0
    for item in CatalogItem.objects.filter(type_slug="campaign"):
        if publication_services.effective(item) is None:
            unpublished_campaigns += 1
    unpublished_recommendations = sum(
        1 for item in CatalogItem.objects.filter(type_slug="recommendation")
        if recommendation_services.published_revision(item) is None)
    unpublished_guides = (CatalogItem.objects.filter(type_slug="setup_guide")
                          .filter(not_marked("publication", "published")).count())
    unpublished_watch = (CatalogItem.objects.filter(type_slug="watch_entry")
                         .filter(not_marked("visibility", "published")).count())
    return {"unpublished_or_draft_campaigns": unpublished_campaigns,
            "unpublished_or_draft_recommendations": unpublished_recommendations,
            "unpublished_or_draft_guides": unpublished_guides,
            "internal_or_unreviewed_watch_entries": unpublished_watch,
            "discussions_internal_or_private": "never included",
            "activity_feed_and_audit_events": "never included",
            "theoretical_forecasts": "never included"}


def collection():
    observations = _published_observations()
    items = (_measured_items(observations) + _campaign_items(observations) +
             _recommendation_items() + _guide_items() + _watch_items() +
             _technology_items())
    items.sort(key=lambda entry: (entry["published_at"], entry["kind"]), reverse=True)
    counts = {}
    for entry in items:
        counts[entry["kind"]] = counts.get(entry["kind"], 0) + 1
    return {
        "generated_from": "effective_published_sources",
        "generated_at": timezone.now().isoformat(),
        "scope": "published_only",
        "items": items[:MAX_ITEMS],
        "counts": counts,
        "excluded": _excluded(),
        "notes": [MEASURED_NOTE, FAILED_NOTE, THEORETICAL_NOTE, TECHNOLOGY_NOTE],
    }
