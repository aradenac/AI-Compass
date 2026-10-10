"""PLAT-12: transactional version-pinned Server campaign planning and lifecycle.

No Demo import, no measured-run fabrication. Every edit/transition creates one
immutable CatalogRevision and one immutable relational CampaignSnapshot.
"""
import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .activity_services import record_catalog_event
from .catalog_compat import compatibility_for_revision
from .catalog_ids import new_public_id
from .catalog_schemas import InvalidModel, validate_model
from .catalog_services import RevisionConflict, SchemaWriteBlocked, ExhaustedIds
from .models import (CampaignSnapshot, CampaignCasePin, CampaignComponentPin,
                     CatalogItem, CatalogRevision, ObjectTypeVersion, TaskNode, TestCase)

MODES = ("task_centred", "solution_centred")
COMPONENTS = ("model", "provider", "harness")
ACTIONS = {
    "start": (("planned",), "in_progress"),
    "close": (("in_progress",), "under_review"),
    "rework": (("under_review",), "in_progress"),
    "publish": (("under_review",), "published"),
    "unpublish": (("published",), "under_review"),
    "reopen": (("under_review", "published"), "in_progress"),
}


class InvalidCampaign(ValueError):
    pass


class InvalidTransition(Exception):
    pass


def _method(mode, version=None):
    if mode not in MODES:
        raise InvalidCampaign("mode must be task_centred or solution_centred")
    query = ObjectTypeVersion.objects.filter(type_slug="campaign_method_" + mode)
    method = query.filter(version=version).first() if version is not None else query.order_by("-version").first()
    if method is None or not isinstance(method.json_schema, dict):
        raise InvalidCampaign("Unknown or unsupported experimental method version")
    if method.json_schema.get("mode") != mode:
        raise InvalidCampaign("Method descriptor does not match campaign mode")
    return method


def _schema():
    schema = ObjectTypeVersion.objects.filter(type_slug="campaign", version=1).first()
    if not schema:
        raise InvalidCampaign("Campaign schema is not registered")
    return schema


def _owner(username, fallback):
    if username is None:
        return fallback
    if not isinstance(username, str) or not username or len(username) > 150:
        raise InvalidCampaign("owner must be a valid Server username")
    user = get_user_model().objects.filter(username=username, is_active=True).first()
    if user is None or not user.has_perm("auth.business_write"):
        raise InvalidCampaign("owner must be an active Server contributor")
    return user


def _task(public_id):
    if not isinstance(public_id, str) or not public_id.startswith("tsk-"):
        raise InvalidCampaign("Fixed task must be an existing Server task")
    task = TaskNode.objects.select_related("item__current_revision").filter(
        item__public_id=public_id, item__type_slug="task").first()
    if task is None or task.item.current_revision_id is None:
        raise InvalidCampaign("Fixed task does not exist")
    return task


def _guide(public_id):
    if public_id is None or public_id == "":
        return None
    if not isinstance(public_id, str) or not public_id.startswith("gui-"):
        raise InvalidCampaign("Guide must be a real Server Setup Guide ID")
    item = CatalogItem.objects.select_related("current_revision").filter(
        public_id=public_id, type_slug="setup_guide").first()
    if item is None or item.current_revision_id is None:
        raise InvalidCampaign("Guide does not exist")
    return item


def _case(public_id):
    if not isinstance(public_id, str) or not public_id.startswith("tcs-"):
        raise InvalidCampaign("Invalid Server Test Case identifier")
    result = TestCase.objects.select_related("item__current_revision","task").filter(
        item__public_id=public_id, item__type_slug="test_case").first()
    if result is None or result.item.current_revision_id is None:
        raise InvalidCampaign("Test Case does not exist")
    return result


def _component(kind, public_id):
    if kind not in COMPONENTS or not isinstance(public_id, str):
        raise InvalidCampaign("Invalid component reference")
    item = CatalogItem.objects.select_related("current_revision").filter(
        public_id=public_id, type_slug=kind).first()
    if item is None or item.current_revision_id is None:
        raise InvalidCampaign("Missing real Server "+kind+" component")
    return item


def _dictionary(value, name, maximum=32768):
    if not isinstance(value, dict) or len(json.dumps(value, ensure_ascii=False)) > maximum:
        raise InvalidCampaign(name + " must be a bounded JSON object")
    return value


def _snapshot_context(data, actor, previous=None):
    """Preserve exact old FK revision pins unless a link is explicitly replaced."""
    old_props = previous.revision.properties if previous else {}
    mode = data.get("mode", old_props.get("mode"))
    changed_mode = previous is not None and mode != old_props["mode"]
    if mode not in MODES:
        raise InvalidCampaign("Select a campaign mode")
    version = data.get("method_version")
    if version is not None and (type(version) is not int or version < 1):
        raise InvalidCampaign("method_version must be a positive integer")
    method = (_method(mode, version) if version is not None or previous is None or changed_mode
              else previous.method_definition)

    owner = _owner(data.get("owner"), previous.owner if previous else actor)
    configuration = (_dictionary(data["configuration"], "configuration", 65536)
                     if "configuration" in data else
                     (previous.configuration if previous and not changed_mode else {}))
    task = None
    task_rev = None
    component_pins = []
    if mode == "task_centred":
        if "component_ids" in data and data["component_ids"] not in (None, {}):
            raise InvalidCampaign("Task-centred mode cannot pin fixed solution components")
        if "task_id" in data or not previous or changed_mode:
            task = _task(data.get("task_id"))
            task_rev = task.item.current_revision
        else:
            task, task_rev = previous.fixed_task, previous.fixed_task_revision
        if task is None or task_rev is None:
            raise InvalidCampaign("Task-centred campaign requires a fixed task")
    else:
        if data.get("task_id") not in (None, ""):
            raise InvalidCampaign("Solution-centred campaign does not fix a task")
        if "component_ids" in data or not previous or changed_mode:
            ids = data.get("component_ids")
            if not isinstance(ids, dict) or set(ids) != set(COMPONENTS):
                raise InvalidCampaign("Select a model, provider and harness")
            component_pins = [(kind, item, item.current_revision)
                              for kind in COMPONENTS for item in [_component(kind, ids[kind])]]
        else:
            component_pins = [(pin.kind, pin.component, pin.revision)
                              for pin in previous.component_pins.select_related("component","revision")]
        if len(component_pins) != 3:
            raise InvalidCampaign("Solution-centred campaign requires all components")

    if "guide_id" in data or previous is None:
        guide = _guide(data.get("guide_id"))
        guide_rev = guide.current_revision if guide else None
    else:
        guide, guide_rev = previous.guide, previous.guide_revision

    if "test_case_ids" in data or previous is None:
        identifiers = data.get("test_case_ids", [])
        if not isinstance(identifiers, list) or len(identifiers) > 200 or len(identifiers) != len(set(
                x for x in identifiers if isinstance(x, str))):
            raise InvalidCampaign("test_case_ids must be a unique list of at most 200 IDs")
        pins = [(case, case.item.current_revision) for case in map(_case, identifiers)]
    else:
        pins = [(pin.test_case, pin.revision)
                for pin in previous.case_pins.select_related("test_case__task","revision")]
    if task and any(case.task_id != task.pk for case, _ in pins):
        raise InvalidCampaign("All Test Cases must belong to the campaign's fixed task")
    return dict(owner=owner, method=method, task=task, task_revision=task_rev,
                guide=guide, guide_revision=guide_rev, configuration=configuration,
                cases=pins, components=component_pins)


def _properties(data, previous=None):
    props = dict(previous or {})
    supplied = data.get("properties", {})
    _dictionary(supplied, "properties")
    if set(supplied) & {"mode", "status", "archived"}:
        raise InvalidCampaign("mode and lifecycle state cannot be overridden through properties")
    props.update(supplied)
    if "objective" in data:
        props["objective"] = data["objective"]
    if "notes" in data:
        props["notes"] = data["notes"]
    return props


def _record(item, rev, ctx, actor, action):
    snap = CampaignSnapshot.objects.create(
        revision=rev, owner=ctx["owner"], method_definition=ctx["method"],
        fixed_task=ctx["task"], fixed_task_revision=ctx["task_revision"],
        guide=ctx["guide"], guide_revision=ctx["guide_revision"],
        configuration=ctx["configuration"])
    CampaignCasePin.objects.bulk_create([CampaignCasePin(
        snapshot=snap, test_case=case, revision=pinned) for case, pinned in ctx["cases"]])
    CampaignComponentPin.objects.bulk_create([CampaignComponentPin(
        snapshot=snap, kind=kind, component=component, revision=pinned)
        for kind, component, pinned in ctx["components"]])
    item.current_revision=rev
    item.save(update_fields=["current_revision"])
    record_catalog_event(item=item, revision=rev, actor=actor, action=action)
    return item


def create(*, actor, data):
    schema=_schema()
    props=_properties(data)
    props.update(mode=data.get("mode"),status="planned",archived=False)
    try:
        name=validate_model(data.get("name"), props, schema.json_schema)
    except InvalidModel as error:
        raise InvalidCampaign(str(error)) from error
    for _ in range(12):
        candidate=new_public_id("cmp")
        try:
            with transaction.atomic():
                ctx=_snapshot_context(data, actor)
                item=CatalogItem.objects.create(public_id=candidate,type_slug="campaign")
                rev=CatalogRevision.objects.create(
                    item=item,number=1,schema_version=schema,display_name=name,
                    properties=props,created_by=actor)
                return _record(item,rev,ctx,actor,"created")
        except IntegrityError:
            if CatalogItem.objects.filter(public_id=candidate).exists():
                continue
            raise
    raise ExhaustedIds("No available campaign public identifier")


def _current(public_id):
    item=CatalogItem.objects.select_for_update(of=("self",)).select_related(
        "current_revision__schema_version").get(public_id=public_id,type_slug="campaign")
    if item.current_revision_id is None:
        raise InvalidCampaign("Campaign has no current revision")
    return item


def _check(item, expected_revision):
    old=item.current_revision
    if expected_revision != f"r{old.number:03d}":
        raise RevisionConflict("Campaign changed; reload before saving")
    compatibility=compatibility_for_revision(item,old)
    if compatibility["read_only"] or old.schema_version.type_slug!="campaign" or old.schema_version.version!=1:
        raise SchemaWriteBlocked(compatibility)
    return old


def modify(*, actor, public_id, data, action=None):
    with transaction.atomic():
        item=_current(public_id)
        old=_check(item,data.get("expected_revision"))
        previous=CampaignSnapshot.objects.select_related(
            "owner","method_definition","fixed_task","fixed_task_revision",
            "guide","guide_revision").get(revision=old)
        props=dict(old.properties)
        state=props["status"]
        if action:
            if action=="archive":
                if props["archived"]: raise InvalidTransition("Campaign already archived")
                props["archived"]=True
            elif action=="restore":
                if not props["archived"]: raise InvalidTransition("Campaign is not archived")
                props["archived"]=False
            else:
                if props["archived"]: raise InvalidTransition("Archived campaigns cannot transition")
                if action not in ACTIONS or state not in ACTIONS[action][0]:
                    raise InvalidTransition("Forbidden campaign lifecycle transition")
                if action=="publish" and previous.case_pins.count()==0:
                    raise InvalidTransition("Cannot publish a campaign without Test Cases")
                props["status"]=ACTIONS[action][1]
            ctx=_snapshot_context({},actor,previous)
            name=old.display_name
        else:
            if props["archived"] or state not in ("planned","in_progress"):
                raise InvalidTransition("Reopen a campaign before editing its plan")
            props=_properties(data,props)
            props["mode"]=data.get("mode",props["mode"])
            ctx=_snapshot_context(data,actor,previous)
            try:
                name=validate_model(data.get("name",old.display_name), props,old.schema_version.json_schema)
            except InvalidModel as error:
                raise InvalidCampaign(str(error)) from error
        # Avoid creating a false revision for an unchanged plan.
        if not action and (props==old.properties and name==old.display_name
                and data.keys() <= {"expected_revision"}):
            return item,False
        try:
            validate_model(name,props,old.schema_version.json_schema)
        except InvalidModel as error:
            raise InvalidCampaign(str(error)) from error
        rev=CatalogRevision.objects.create(
            item=item,number=old.number+1,schema_version=old.schema_version,
            display_name=name,properties=props,created_by=actor)
        return _record(item,rev,ctx,actor,action or "revised"),True


def serialize(item, rev=None):
    revision = rev or item.current_revision
    snap = CampaignSnapshot.objects.select_related(
        "owner","method_definition","fixed_task__item","guide"
    ).get(revision=revision)
    cases = list(snap.case_pins.select_related("test_case__item","revision")
                 .order_by("test_case__item__public_id"))
    components = list(snap.component_pins.select_related("component","revision").order_by("kind"))
    return {
        "id":item.public_id, "uuid":str(item.pk), "revision":f"r{revision.number:03d}",
        "revision_id":str(revision.pk), "schema_version":revision.schema_version.version,
        "name":revision.display_name, "properties":revision.properties,
        "owner":snap.owner.get_username(),
        "mode":revision.properties["mode"], "method_version":snap.method_definition.version,
        "method_definition_id":str(snap.method_definition_id),
        "method_definition":snap.method_definition.json_schema,
        "status":revision.properties["status"], "archived":revision.properties["archived"],
        "task_id":snap.fixed_task.item.public_id if snap.fixed_task_id else None,
        "task_revision_id":str(snap.fixed_task_revision_id) if snap.fixed_task_revision_id else None,
        "guide_id":snap.guide.public_id if snap.guide_id else None,
        "guide_revision_id":str(snap.guide_revision_id) if snap.guide_revision_id else None,
        "test_case_ids":[p.test_case.item.public_id for p in cases],
        "test_case_revisions":[{"id":p.test_case.item.public_id,"revision_id":str(p.revision_id)}
                               for p in cases],
        "component_ids":{p.kind:p.component.public_id for p in components},
        "component_revisions":{p.kind:str(p.revision_id) for p in components},
        "configuration":snap.configuration,
        "created_at":revision.created_at.isoformat(),
        "created_by":revision.created_by.get_username(),
        "compatibility":compatibility_for_revision(item,revision),
    }
