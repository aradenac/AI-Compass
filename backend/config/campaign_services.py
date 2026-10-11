"""PLAT-12: transactional version-pinned Server campaign planning and lifecycle.

No Demo import, no measured-run fabrication. Every edit/transition creates one
immutable CatalogRevision and one immutable relational CampaignSnapshot.
"""
import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .activity_services import record_catalog_event
from .pricing_services import (prepare_selections, pricing_status, serialize_selections, InvalidPricing)
from .models import CampaignPricingPin
from .catalog_compat import compatibility_for_revision
from .catalog_ids import new_public_id
from .catalog_schemas import InvalidModel, validate_model
from .catalog_services import RevisionConflict, SchemaWriteBlocked, ExhaustedIds
from .campaign_participant_services import prepare_participants, persist_participants, serialize_participants
from .models import (CampaignSnapshot, CampaignCasePin, CampaignComponentPin,
                     CampaignForecastOrigin, CampaignForecastWatchPin,
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
    repin = data.get("repin", False)
    if type(repin) is not bool:
        raise InvalidCampaign("repin must be a boolean")
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
    if "framework_id" in data:
        framework_id=data["framework_id"]
    elif previous:
        framework_id=previous.framework.public_id if previous.framework_id else None
    else:
        framework_id=None
    if framework_id in (None, ""):
        framework,framework_revision=None,None
    else:
        framework=_framework(framework_id)
        if previous and previous.framework_id==framework.pk and not repin:
            framework_revision=previous.framework_revision
        else:
            framework_revision=framework.current_revision
    changed_framework = (previous is not None and
                         framework_id != (previous.framework.public_id if previous.framework_id else None))
    if mode == "task_centred":
        if "component_ids" in data and data["component_ids"] not in (None, {}):
            raise InvalidCampaign("Task-centred mode cannot pin fixed solution components")
        if previous and not changed_mode and not repin and (
                "task_id" not in data or data["task_id"] == previous.fixed_task.item.public_id):
            task, task_rev = previous.fixed_task, previous.fixed_task_revision
        else:
            task = _task(data.get("task_id", previous.fixed_task.item.public_id
                                  if previous and not changed_mode else None))
            task_rev = task.item.current_revision
        if task is None or task_rev is None:
            raise InvalidCampaign("Task-centred campaign requires a fixed task")
    else:
        if data.get("task_id") not in (None, ""):
            raise InvalidCampaign("Solution-centred campaign does not fix a task")
        if framework is not None:
            if "component_ids" in data and data["component_ids"] not in (None, {}):
                raise InvalidCampaign("Framework participants replace the fixed solution trio")
        elif "component_ids" in data or not previous or changed_mode or changed_framework:
            ids = data.get("component_ids")
            if not isinstance(ids, dict) or set(ids) != set(COMPONENTS):
                raise InvalidCampaign("Select a model, provider and harness")
            originals = {p.kind:p for p in previous.component_pins.select_related(
                "component", "revision")} if previous and not changed_mode else {}
            component_pins = []
            for kind in COMPONENTS:
                old_pin = originals.get(kind)
                if old_pin and old_pin.component.public_id == ids[kind] and not repin:
                    component_pins.append((kind, old_pin.component, old_pin.revision))
                else:
                    item = _component(kind, ids[kind])
                    component_pins.append((kind, item, item.current_revision))
        else:
            component_pins = [(pin.kind, pin.component, pin.revision)
                              for pin in previous.component_pins.select_related("component","revision")]
        if framework is None and len(component_pins) != 3:
            raise InvalidCampaign("Solution-centred campaign requires all components")

    if previous and not repin and ("guide_id" not in data or
            data["guide_id"] == (previous.guide.public_id if previous.guide_id else None) or
            data["guide_id"] == (previous.guide.public_id if previous.guide_id else "")):
        guide, guide_rev = previous.guide, previous.guide_revision
    else:
        guide = _guide(data.get("guide_id", previous.guide.public_id if previous and previous.guide_id else None))
        guide_rev = guide.current_revision if guide else None

    if "test_case_ids" in data or previous is None:
        identifiers = data.get("test_case_ids", [])
        if not isinstance(identifiers, list) or len(identifiers) > 200 or len(identifiers) != len(set(
                x for x in identifiers if isinstance(x, str))):
            raise InvalidCampaign("test_case_ids must be a unique list of at most 200 IDs")
        old_cases = {p.test_case.item.public_id:p for p in previous.case_pins.select_related(
            "test_case__item","revision")} if previous else {}
        pins = []
        for identifier in identifiers:
            old_pin = old_cases.get(identifier) if isinstance(identifier,str) else None
            if old_pin and not repin:
                pins.append((old_pin.test_case, old_pin.revision))
            else:
                case = _case(identifier)
                pins.append((case, case.item.current_revision))
    else:
        pins = [(pin.test_case, pin.revision)
                for pin in previous.case_pins.select_related("test_case__task","revision")]
    if task and not (data.get("_trusted_matrix") or (previous and previous.revision.properties.get("matrix_plan"))) and any(case.task_id != task.pk for case, _ in pins):
        raise InvalidCampaign("All Test Cases must belong to the campaign's fixed task")
    if framework is None and "participants" in data and data["participants"] not in (None,[]):
        raise InvalidCampaign("Participant trios require a Framework")
    if previous and framework is None and previous.framework_id and "participants" not in data:
        raise InvalidCampaign("Clearing Framework requires explicit removal of participant list")
    participants=prepare_participants(
        supplied=data.get("participants"),previous=previous,framework=framework,
        changed_framework=changed_framework,repin=repin,
        component_lookup=_component,bounded_dict=_dictionary,error=InvalidCampaign)
    return dict(owner=owner, method=method, task=task, task_revision=task_rev,
                guide=guide, guide_revision=guide_rev, configuration=configuration,
                framework=framework,framework_revision=framework_revision,
                participants=participants,cases=pins, components=component_pins)


def _framework(public_id):
    if not isinstance(public_id,str) or not public_id.startswith("frm-"):
        raise InvalidCampaign("Framework must be a real Server Framework ID")
    framework=CatalogItem.objects.select_related("current_revision").filter(
        public_id=public_id,type_slug="framework").first()
    if framework is None or framework.current_revision_id is None:
        raise InvalidCampaign("Unknown Framework")
    return framework


def _properties(data, previous=None):
    props = dict(previous or {})
    supplied = data.get("properties", {})
    _dictionary(supplied, "properties", 512*1024 if data.get("_trusted_matrix") is True else 32768)
    if "matrix_plan" in supplied and data.get("_trusted_matrix") is not True:
        raise InvalidCampaign("Matrix plans must be changed through the evaluation API")
    if set(supplied) & {"mode", "status", "archived", "pricing_policy"}:
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
        configuration=ctx["configuration"],
        framework=ctx["framework"],framework_revision=ctx["framework_revision"])
    CampaignCasePin.objects.bulk_create([CampaignCasePin(
        snapshot=snap, test_case=case, revision=pinned) for case, pinned in ctx["cases"]])
    CampaignComponentPin.objects.bulk_create([CampaignComponentPin(
        snapshot=snap, kind=kind, component=component, revision=pinned)
        for kind, component, pinned in ctx["components"]])
    persist_participants(campaign=item,snapshot=snap,prepared=ctx["participants"])
    CampaignPricingPin.objects.bulk_create([
        CampaignPricingPin(snapshot=snap, source_key=key,component=component,
                           offer=offer,offer_revision=revision)
        for key,component,offer,revision in ctx.get("pricing_pins",[])
    ])
    origin=ctx.get("forecast_origin")
    initial=ctx.get("new_forecast_snapshot")
    if origin is not None or initial is not None:
        frozen=initial if initial is not None else origin.forecast_snapshot
        link=CampaignForecastOrigin.objects.create(
            campaign_snapshot=snap,forecast_snapshot=frozen)
        parents=frozen.watch_pins if initial is not None else origin.watch_pins
        CampaignForecastWatchPin.objects.bulk_create([
            CampaignForecastWatchPin(origin=link,watch=p.watch,watch_revision=p.watch_revision)
            for p in parents.select_related("watch","watch_revision").order_by("id")
        ])
    item.current_revision=rev
    item.save(update_fields=["current_revision"])
    record_catalog_event(item=item, revision=rev, actor=actor, action=action)
    return item


def create(*, actor, data, forecast_snapshot=None):
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
                if "pricing_selections" in data:
                    props["pricing_policy"]="offer_revisions_v1"
                ctx["pricing_pins"]=prepare_selections(data.get("pricing_selections"),ctx)
                if forecast_snapshot is not None:
                    if data.get("mode")!="task_centred" or ctx["task"].pk!=forecast_snapshot.task_id:
                        raise InvalidCampaign("Forecast validation campaign must pin the forecast's fixed task")
                    ctx["task_revision"]=forecast_snapshot.task_revision
                    ctx["new_forecast_snapshot"]=forecast_snapshot
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
            "guide","guide_revision","framework","framework_revision").get(revision=old)
        props=dict(old.properties)
        # A publication is an event on one immutable campaign revision, never
        # inherited by later working revisions or automatically republished.
        props.pop("publication_event", None)
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
                if action=="revoke_publication":
                    event=data.get("_publication_event")
                    if (not isinstance(event,dict) or event.get("kind")!="revoke"
                            or state not in ("in_progress","under_review")):
                        raise InvalidTransition("Only a working or reviewed campaign can revoke its effective publication")
                    props["publication_event"]=event
                elif action not in ACTIONS or state not in ACTIONS[action][0]:
                    raise InvalidTransition("Forbidden campaign lifecycle transition")
                if action!="revoke_publication" and action=="close" and props.get("matrix_plan"):
                    from .campaign_matrix_services import projection
                    counts=projection(item,old)["summary"]
                    partial=data.get("partial_review",False)
                    if type(partial) is not bool:
                        raise InvalidCampaign("partial_review must be a boolean")
                    if counts["outstanding"] and not partial:
                        raise InvalidTransition("Full plan has "+str(counts["outstanding"])+
                            " pending/in-progress obligations; complete/waive them or explicitly close for partial review")
                    props["review_scope"]="partial" if counts["outstanding"] else "full"
                elif action!="revoke_publication" and "partial_review" in data:
                    raise InvalidCampaign("partial_review applies only when closing a matrix campaign")
                if action=="publish":
                    event=data.get("_publication_event")
                    if not isinstance(event,dict) or event.get("kind")!="publish" or not event.get("runs"):
                        raise InvalidTransition("Publish requires validated selected Runs")
                    props["publication_event"]=event
                elif action=="unpublish":
                    event=data.get("_publication_event")
                    if not isinstance(event,dict) or event.get("kind")!="revoke":
                        raise InvalidTransition("Unpublish requires an explicit revocation decision")
                    props["publication_event"]=event
                if action!="revoke_publication":
                    props["status"]=ACTIONS[action][1]
            ctx=_snapshot_context({},actor,previous)
            ctx["pricing_pins"]=prepare_selections(None,ctx,previous)
            name=old.display_name
        else:
            if props["archived"] or state not in ("planned","in_progress"):
                raise InvalidTransition("Reopen a campaign before editing its plan")
            props=_properties(data,props)
            props["mode"]=data.get("mode",props["mode"])
            ctx=_snapshot_context(data,actor,previous)
            if "pricing_selections" in data:
                props["pricing_policy"]="offer_revisions_v1"
            ctx["pricing_pins"]=prepare_selections(data.get("pricing_selections"),ctx,previous)
            try:
                name=validate_model(data.get("name",old.display_name), props,old.schema_version.json_schema)
            except InvalidModel as error:
                raise InvalidCampaign(str(error)) from error
        # Retain exact original theoretical rationale and signal revisions when
        # a validation campaign plan is subsequently edited or transitioned.
        ctx["forecast_origin"]=CampaignForecastOrigin.objects.filter(campaign_snapshot=previous).first()
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
        "owner","method_definition","fixed_task__item","guide","framework"
    ).get(revision=revision)
    cases = list(snap.case_pins.select_related("test_case__item","revision")
                 .order_by("test_case__item__public_id"))
    components = list(snap.component_pins.select_related("component","revision").order_by("kind"))
    origin=CampaignForecastOrigin.objects.select_related(
        "forecast_snapshot__revision__item").filter(campaign_snapshot=snap).first()
    return {
        "id":item.public_id, "uuid":str(item.pk), "revision":f"r{revision.number:03d}",
        "revision_id":str(revision.pk), "schema_version":revision.schema_version.version,
        "name":revision.display_name, "properties":revision.properties,
        "owner":snap.owner.get_username(),
        "mode":revision.properties["mode"], "method_version":snap.method_definition.version,
        "method_definition_id":str(snap.method_definition_id),
        "method_definition":snap.method_definition.json_schema,
        "status":revision.properties["status"], "archived":revision.properties["archived"],
        "effective_publication":_serialized_publication(item, revision),
        "task_id":snap.fixed_task.item.public_id if snap.fixed_task_id else None,
        "task_revision_id":str(snap.fixed_task_revision_id) if snap.fixed_task_revision_id else None,
        "guide_id":snap.guide.public_id if snap.guide_id else None,
        "guide_revision_id":str(snap.guide_revision_id) if snap.guide_revision_id else None,
        "framework_id":snap.framework.public_id if snap.framework_id else None,
        "framework_revision_id":str(snap.framework_revision_id) if snap.framework_revision_id else None,
        "participants":serialize_participants(snap),
        "test_case_ids":[p.test_case.item.public_id for p in cases],
        "test_case_revisions":[{"id":p.test_case.item.public_id,"revision_id":str(p.revision_id)}
                               for p in cases],
        "component_ids":{p.kind:p.component.public_id for p in components},
        "component_revisions":{p.kind:str(p.revision_id) for p in components},
        "configuration":snap.configuration,
        "pricing_selections":serialize_selections(snap),
        "pricing_readiness":pricing_status(snap),
        "pricing_policy":revision.properties.get("pricing_policy","legacy_unclassified"),
        "forecast_origin":({
            "id":origin.forecast_snapshot.revision.item.public_id,
            "revision":f"r{origin.forecast_snapshot.revision.number:03d}",
            "revision_id":str(origin.forecast_snapshot_id),
            "evidence_class":"theoretical",
            "watch_links":[{
                "id":p.watch.public_id,"revision":f"r{p.watch_revision.number:03d}",
                "revision_id":str(p.watch_revision_id)
            } for p in origin.watch_pins.select_related("watch","watch_revision").order_by("id")]
        } if origin is not None else None),
        "created_at":revision.created_at.isoformat(),
        "created_by":revision.created_by.get_username(),
        "compatibility":compatibility_for_revision(item,revision),
    }


def _serialized_publication(item, revision):
    """Historical as-of pointer, with no draft Run content disclosed."""
    from .publication_services import effective
    row = effective(item, revision.number)
    if row is None:
        return None
    return {"revision": row["campaign_revision"],
            "revision_id": row["campaign_revision_id"],
            "included_runs": len([x for x in row["runs"] if x["id"] in __import__(
                "config.publication_services",fromlist=["effective_ids"]).effective_ids(item.public_id)]),
            "coverage": row["coverage"]}
