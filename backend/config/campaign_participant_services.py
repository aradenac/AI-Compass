"""PLAT-13: validated, stable participant identities and immutable trio snapshots.

This module never edits a catalog revision, never imports Demo records and
never derives pinned component revisions from mutable descriptions.
"""
from django.db import IntegrityError

from .catalog_ids import new_public_id
from .models import CampaignParticipantIdentity, CampaignParticipantPin

LIMIT = 64
KINDS = ("model", "provider", "harness")


def prepare_participants(*, supplied, previous, framework, changed_framework, repin, component_lookup, bounded_dict, error):
    """Return immutable per-revision participant values, without writing rows.

    Partial campaign PATCHes preserve previous pins verbatim. Explicit list
    replacement handles adds, edits, reordering and removal. Same-ID component
    submissions retain original revisions until repin=True.
    """
    old_pins = {}
    if previous is not None:
        old_pins = {p.participant.public_id: p for p in previous.participant_pins.select_related(
            "participant", "model", "model_revision", "provider", "provider_revision",
            "harness", "harness_revision")}
    if framework is None:
        if supplied not in (None, []):
            raise error("Participants require a selected Framework")
        return []
    if supplied is None:
        if previous is None or changed_framework:
            raise error("A Framework requires at least one configured participant")
        # Old FK revision pins and opaque settings are unchanged on ordinary edits.
        return [dict(identity=p.participant, label=p.label, role=p.role,
            version=p.configuration_version, settings=p.settings, properties=p.properties,
            components={k:(getattr(p,k),getattr(p,k+"_revision")) for k in KINDS})
            for p in sorted(old_pins.values(),key=lambda p:p.position)]
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= LIMIT:
        raise error("A Framework requires 1–64 participant trios")
    seen = set()
    result = []
    for position, row in enumerate(supplied):
        if not isinstance(row,dict) or set(row)-{
                "id","label","role","configuration_version","settings","properties","component_ids"}:
            raise error("Participant entry must contain only supported fields and optional properties")
        pid=row.get("id")
        if pid is not None and (not isinstance(pid,str) or pid not in old_pins):
            raise error("Participant ID is not part of the current campaign revision")
        if pid is not None and changed_framework:
            raise error("Switching Framework requires new participant identities")
        if pid is not None and pid in seen:
            raise error("Participant IDs cannot repeat")
        if pid is not None:seen.add(pid)
        previous_pin=old_pins.get(pid) if pid else None
        label=row.get("label",previous_pin.label if previous_pin else None)
        role=row.get("role",previous_pin.role if previous_pin else None)
        version=row.get("configuration_version",
                        previous_pin.configuration_version if previous_pin else "1")
        if any(not isinstance(v,str) or not v.strip() or len(v.strip())>160
               for v in (label,role,version)):
            raise error("Every participant needs a nonempty label, role and configuration version (max 160)")
        settings=bounded_dict(row.get("settings",previous_pin.settings if previous_pin else {}),
                              "participant settings",65536)
        properties=bounded_dict(row.get("properties",previous_pin.properties if previous_pin else {}),
                                "participant properties",32768)
        ids=row.get("component_ids")
        if ids is None:
            if previous_pin is None:
                raise error("Every new participant requires a complete trio")
            ids={k:getattr(previous_pin,k).public_id for k in KINDS}
        if not isinstance(ids,dict) or set(ids)!=set(KINDS):
            raise error("Participant must reference exactly model, provider and harness")
        components={}
        for kind in KINDS:
            value=ids[kind]
            old_component=getattr(previous_pin,kind) if previous_pin else None
            if old_component and old_component.public_id==value and not repin:
                components[kind]=(old_component,getattr(previous_pin,kind+"_revision"))
            else:
                item=component_lookup(kind,value)
                components[kind]=(item,item.current_revision)
        result.append(dict(identity=previous_pin.participant if previous_pin else None,
                           label=label.strip(),role=role.strip(),version=version.strip(),
                           settings=settings,properties=properties,components=components))
    return result


def persist_participants(*, campaign, snapshot, prepared):
    """Called within the parent campaign atomic revision transaction."""
    for position,record in enumerate(prepared):
        identity=record["identity"]
        if identity is None:
            # Globally stable participant ID (not a per-snapshot row ID).
            for _ in range(12):
                public_id=new_public_id("ptp")
                try:
                    identity=CampaignParticipantIdentity.objects.create(
                        public_id=public_id,campaign=campaign)
                    break
                except IntegrityError:
                    if CampaignParticipantIdentity.objects.filter(public_id=public_id).exists():
                        continue
                    raise
            if identity is None:
                raise ValueError("Participant identifier capacity exhausted")
        components=record["components"]
        CampaignParticipantPin.objects.create(
            snapshot=snapshot,participant=identity,position=position,
            label=record["label"],role=record["role"],configuration_version=record["version"],
            settings=record["settings"],properties=record["properties"],
            model=components["model"][0],model_revision=components["model"][1],
            provider=components["provider"][0],provider_revision=components["provider"][1],
            harness=components["harness"][0],harness_revision=components["harness"][1])


def serialize_participants(snapshot):
    rows=snapshot.participant_pins.select_related(
        "participant","model","provider","harness").order_by("position")
    return [{
        "id":p.participant.public_id,"uuid":str(p.participant_id),"position":p.position,
        "label":p.label,"role":p.role,"configuration_version":p.configuration_version,
        "settings":p.settings,"properties":p.properties,
        "component_ids":{k:getattr(p,k).public_id for k in KINDS},
        "component_revisions":{k:str(getattr(p,k+"_revision_id")) for k in KINDS},
    } for p in rows]
