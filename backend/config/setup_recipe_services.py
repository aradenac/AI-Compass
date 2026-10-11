"""FUT-07: resolve the actual immutable session setup and historical guide.

A caller never supplies Model/Provider/Harness IDs as proof of what was tested.
Configuration identities are taken exclusively from persisted snapshot pins.
"""
from copy import deepcopy

from .models import CatalogRevision, SessionSolutionPin
from .setup_composition import compose, SetupCompositionError, validate_recipe


def snapshots_for_recipe(recipe):
    validate_recipe(recipe)
    pins = {(m["id"], m["revision"]) for m in recipe.get("modules", [])}
    result = {}
    for public_id, revision in pins:
        row = CatalogRevision.objects.select_related("item").filter(
            item__type_slug="setup_guide", item__public_id=public_id,
            number=int(revision[1:])).first()
        if row:
            result[(public_id, revision)] = {
                "name": row.display_name, "properties": row.properties}
    return result


def from_revision(guide_revision, configuration, *, require_wiring=False):
    """Represent a pinned guide; legacy text/URL remains readable, not certified."""
    if guide_revision is None:
        return {"ready": False, "sections": [], "missing": [{"kind": "guide_not_selected"}]}
    properties = guide_revision.properties
    reference = {"id": guide_revision.item.public_id,
                 "revision": "r%03d" % guide_revision.number,
                 "revision_id": str(guide_revision.pk)}
    recipe = properties.get("recipe")
    if not isinstance(recipe, dict):
        return {"recipe": reference, "ready": False,
                "sections": [{"id": reference["id"], "revision": reference["revision"],
                              "name": guide_revision.display_name,
                              "text": properties.get("text"), "url": properties.get("url")}],
                "missing": [{"kind": "legacy_guide_requires_applicability_review"}]}
    # Never change the persisted recipe to enforce a session-specific check.
    effective = deepcopy(recipe)
    if require_wiring:
        groups = effective.setdefault("required_groups", [])
        # A Framework guide must explicitly cover every selected participant
        # and the actual routing/handoff integration, not merely the framework.
        participant_ids = [p["id"] for p in configuration.get("participants", [])]
        for group in ["framework_wiring"] + ["participant:"+pid for pid in participant_ids]:
            if group not in groups:
                groups.append(group)
    result = compose(effective, snapshots_for_recipe(recipe), configuration)
    result["recipe"] = reference
    return result


def session_configuration(session, setup):
    """Merge declared environment with authoritative pinned component identifiers."""
    environment = setup.get("environment", {})
    if not isinstance(environment, dict):
        environment = {}
    # Arbitrary untrusted user-entered environment cannot replace pinned identity.
    config = {k: v for k, v in environment.items()
              if k not in ("model", "provider", "harness", "framework",
                           "model_revision_id", "provider_revision_id",
                           "harness_revision_id", "framework_revision_id",
                           "participants", "configuration_version")}
    snapshot = session.campaign_snapshot
    pin = SessionSolutionPin.objects.filter(session=session).select_related(
        "model", "provider", "harness").first()
    if pin:
        for kind in ("model", "provider", "harness"):
            config[kind] = getattr(pin, kind).public_id
            config[kind+"_revision_id"] = str(getattr(pin, kind+"_revision_id"))
        config["configuration_version"] = pin.configuration_version
    if snapshot.framework_id:
        config["framework"] = snapshot.framework.public_id
        config["framework_revision_id"] = str(snapshot.framework_revision_id)
        participants = []
        selected = set(session.selected_participants)
        for item in snapshot.participant_pins.select_related(
            "participant", "model", "provider", "harness").order_by("position"):
            if item.participant.public_id not in selected:
                continue
            participant = {"id": item.participant.public_id, "role": item.role,
                           "configuration_version": item.configuration_version}
            for kind in ("model", "provider", "harness"):
                participant[kind] = getattr(item, kind).public_id
                participant[kind+"_revision_id"] = str(getattr(item, kind+"_revision_id"))
            participants.append(participant)
        config["participants"] = participants
    return config


def from_session(session):
    """Inspect original pinned guide at latest persisted setup checkpoint only."""
    from .session_services import _checkpoint
    cp = _checkpoint(session)
    setup = cp.state.get("setup", {})
    config = session_configuration(session, setup)
    result = from_revision(session.guide_revision, config,
                           require_wiring=bool(session.campaign_snapshot.framework_id))
    result["configuration"] = config
    result["session_id"] = session.public_id
    result["checkpoint_id"] = str(cp.pk)
    result["deviations"] = {"notes": setup.get("notes", ""),
                            "extensions": setup.get("extensions", {})}
    return result
