"""Snapshot the actual individual AI setup as immutable relational session pins."""
from .models import CatalogItem, SessionSolutionPin
from .session_services import InvalidSession


KINDS=("model","provider","harness")


def prepare(snapshot, participant_ids, data):
    if snapshot.framework_id:
        if any(k in data for k in ("component_ids","settings","properties","configuration_version")):
            raise InvalidSession("Framework participant already defines the pinned setup")
        if len(participant_ids)!=1:
            return None  # Collaborative draft for PLAT-16: cannot close as individual.
        participant=snapshot.participant_pins.select_related(
            "participant","model","model_revision","provider","provider_revision",
            "harness","harness_revision").get(participant__public_id=participant_ids[0])
        return {
            "parts":{k:(getattr(participant,k),getattr(participant,k+"_revision")) for k in KINDS},
            "settings":participant.settings,"properties":participant.properties,
            "configuration_version":participant.configuration_version,
        }
    if snapshot.revision.properties.get("mode")=="solution_centred":
        if "component_ids" in data or "settings" in data or "properties" in data or "configuration_version" in data:
            raise InvalidSession("Non-Framework solution-centred setup is fixed by the campaign")
        selected=list(snapshot.component_pins.select_related("component","revision"))
        if {p.kind for p in selected}!=set(KINDS):
            raise InvalidSession("Fixed campaign solution is not a complete trio")
        return {"parts":{p.kind:(p.component,p.revision) for p in selected},
                "settings":snapshot.configuration,"properties":{},"configuration_version":"1"}
    # Task-centred sessions may vary by individually selected Model/Provider/Harness.
    # Existing PLAT-14 drafts created with no setup remain readable, but cannot close
    # until a new session is started with a known controlled setup.
    ids=data.get("component_ids")
    if ids is None:
        if any(k in data for k in ("settings","properties","configuration_version")):
            raise InvalidSession("Setup fields need a complete Model/Provider/Harness trio")
        return None
    if not isinstance(ids,dict) or set(ids)!=set(KINDS):
        raise InvalidSession("Select exactly one Model, Provider and Harness")
    parts={}
    for kind in KINDS:
        key=ids[kind]
        if not isinstance(key,str):
            raise InvalidSession("Invalid component identifier")
        item=CatalogItem.objects.select_related("current_revision").filter(
            public_id=key,type_slug=kind).first()
        if item is None or item.current_revision_id is None:
            raise InvalidSession("All selected components must exist in Server")
        parts[kind]=(item,item.current_revision)
    settings=data.get("settings",snapshot.configuration)
    properties=data.get("properties",{})
    for val,name in ((settings,"settings"),(properties,"properties")):
        if not isinstance(val,dict):
            raise InvalidSession(name+" must be a JSON object")
    version=data.get("configuration_version","1")
    if not isinstance(version,str) or not 1<=len(version)<=160:
        raise InvalidSession("Invalid configuration_version")
    return {"parts":parts,"settings":settings,"properties":properties,
            "configuration_version":version}


def save(session,prepared):
    if prepared is None:return None
    parts=prepared["parts"]
    return SessionSolutionPin.objects.create(
        session=session,
        model=parts["model"][0],model_revision=parts["model"][1],
        provider=parts["provider"][0],provider_revision=parts["provider"][1],
        harness=parts["harness"][0],harness_revision=parts["harness"][1],
        settings=prepared["settings"],properties=prepared["properties"],
        configuration_version=prepared["configuration_version"])


def serialize(session):
    p=SessionSolutionPin.objects.filter(session=session).select_related(
        "model","provider","harness").first()
    if p is None:return None
    return {"component_ids":{k:getattr(p,k).public_id for k in KINDS},
            "component_revisions":{k:str(getattr(p,k+"_revision_id")) for k in KINDS},
            "configuration_version":p.configuration_version,
            "settings":p.settings,"properties":p.properties}
