"""PLAT-20: manually sourced, versioned THEORETICAL forecasts; never measured runs."""
import copy
import json
import math

from django.db import IntegrityError, transaction
from django.db.models import Q

from .activity_services import record_catalog_event
from .catalog_compat import compatibility_for_revision
from .catalog_ids import new_public_id
from .catalog_schemas import InvalidModel, validate_model
from .catalog_services import RevisionConflict, SchemaWriteBlocked, ExhaustedIds
from .models import (CatalogItem,CatalogRevision,ObjectTypeVersion,TaskNode,
                     ForecastSnapshot,ForecastWatchPin,WatchSourcePin)

KIND="forecast"
COMPONENTS=("model","provider","harness")
STATES=("draft","staged","reviewed","published")
METRICS={"quality_score":100,"acceptance_probability":100,"autonomy_score":100,
         "human_minutes":None,"ai_cost_eur":None,"tokens":None}
MAX_LINKS=32


class ForecastInvalid(ValueError):
    pass


def _dict(value,label,limit=32768):
    if not isinstance(value,dict):
        raise ForecastInvalid(label+" must be a JSON object")
    try:
        if len(json.dumps(value,ensure_ascii=False,allow_nan=False))>limit:
            raise ForecastInvalid(label+" too large")
    except (ValueError,TypeError) as exc:
        raise ForecastInvalid(label+" must be valid JSON") from exc
    return copy.deepcopy(value)


def _metrics(value):
    metrics=_dict(value,"predicted_metrics",12000)
    for key,upper in METRICS.items():
        if key not in metrics:
            continue
        v=metrics[key]
        if v is None:continue
        if type(v) not in (int,float) or not math.isfinite(v) or v<0 or (upper is not None and v>upper):
            raise ForecastInvalid(key+" must be a nonnegative finite predicted value or null")
        if key=="tokens" and type(v) is not int:
            raise ForecastInvalid("tokens must be integer or null")
    return metrics


def _properties(data,old=None):
    if not isinstance(data,dict):
        raise ForecastInvalid("properties must be a JSON object")
    p=copy.deepcopy(old or {})
    p.update(data)
    if p.get("evidence_class","theoretical")!="theoretical":
        raise ForecastInvalid("Forecast is theoretical, never measured")
    p["evidence_class"]="theoretical"
    p.setdefault("status","draft")
    p.setdefault("confidence","unknown")
    p.setdefault("uncertainty","")
    p.setdefault("review_notes","")
    p.setdefault("reviewer",None)
    p.setdefault("predicted_metrics",{})
    p.setdefault("assumptions",{})
    if p["status"] not in STATES:raise ForecastInvalid("Invalid forecast status")
    for key,limit in (("rationale",10000),("uncertainty",10000),("review_notes",10000)):
        if not isinstance(p.get(key),str) or len(p[key])>limit:
            raise ForecastInvalid(key+" must be bounded text")
    if not p["rationale"].strip():
        raise ForecastInvalid("Theoretical forecast requires an explicit rationale")
    if p["confidence"] not in ("low","medium","high","unknown"):
        raise ForecastInvalid("Invalid confidence")
    if p["reviewer"] is not None and (not isinstance(p["reviewer"],str) or len(p["reviewer"])>150):
        raise ForecastInvalid("Invalid reviewer")
    p["assumptions"]=_dict(p["assumptions"],"assumptions")
    p["predicted_metrics"]=_metrics(p["predicted_metrics"])
    return _dict(p,"properties",64000)


def _task(identifier,old=None):
    if identifier is None and old:
        return old.task,old.task_revision
    if not isinstance(identifier,str) or not identifier.startswith("tsk-"):
        raise ForecastInvalid("A real task ID is required")
    task=TaskNode.objects.select_related("item__current_revision").filter(
        item__public_id=identifier,item__type_slug="task").first()
    if task is None or task.item.current_revision_id is None:
        raise ForecastInvalid("Unknown task")
    if old and task.pk==old.task_id:
        return old.task,old.task_revision
    return task,task.item.current_revision


def _components(ids,old=None):
    if ids is None and old:
        return {kind:(getattr(old,kind),getattr(old,kind+"_revision")) for kind in COMPONENTS}
    if not isinstance(ids,dict) or set(ids)!=set(COMPONENTS):
        raise ForecastInvalid("Select exactly a Model, Provider and Harness")
    pinned={}
    for kind in COMPONENTS:
        identifier=ids[kind]
        if not isinstance(identifier,str):
            raise ForecastInvalid("Invalid "+kind+" identifier")
        prior=getattr(old,kind) if old else None
        if prior is not None and prior.public_id==identifier:
            pinned[kind]=(prior,getattr(old,kind+"_revision"))
            continue
        item=CatalogItem.objects.select_related("current_revision").filter(
            public_id=identifier,type_slug=kind).first()
        if item is None or not item.current_revision_id:
            raise ForecastInvalid("Unknown "+kind+" catalog component")
        pinned[kind]=(item,item.current_revision)
    return pinned


def _watch(links,old=None):
    if links is None and old:
        return [(p.watch,p.watch_revision) for p in old.watch_pins.select_related(
            "watch","watch_revision").order_by("id")]
    if links is None:links=[]
    if not isinstance(links,list) or len(links)>MAX_LINKS:
        raise ForecastInvalid("watch_links must be a list of at most 32 signals")
    result=[];seen=set()
    for link in links:
        if not isinstance(link,dict) or set(link)-{"id","revision"}:
            raise ForecastInvalid("Watch links must specify ID and optional revision")
        identifier=link.get("id")
        if not isinstance(identifier,str) or not identifier.startswith("wat-") or identifier in seen:
            raise ForecastInvalid("Invalid or duplicate Watch Entry")
        seen.add(identifier)
        item=CatalogItem.objects.select_related("current_revision").filter(
            public_id=identifier,type_slug="watch_entry").first()
        if item is None:raise ForecastInvalid("Unknown real Watch Entry")
        revision=link.get("revision")
        if revision is None:
            # Existing selected links do not silently re-pin if the caller omits revisions.
            prior=next((p for p in _watch(None,old) if p[0].pk==item.pk),None) if old else None
            rev=prior[1] if prior else item.current_revision
        elif isinstance(revision,str) and revision.startswith("r") and revision[1:].isdigit():
            n=int(revision[1:])
            if revision!=f"r{n:03d}":raise ForecastInvalid("Watch revision must be r001 style")
            rev=CatalogRevision.objects.filter(item=item,number=n).first()
        else:raise ForecastInvalid("Invalid Watch revision")
        if rev is None:raise ForecastInvalid("Watch revision does not exist")
        result.append((item,rev))
    return result


def _schema():
    schema=ObjectTypeVersion.objects.filter(type_slug=KIND,version=1).first()
    if not schema:raise ForecastInvalid("Registered Forecast schema unavailable")
    return schema


def _pins(old,data):
    task,task_revision=_task(data.get("task_id"),old)
    components=_components(data.get("component_ids"),old)
    config=(_dict(data["configuration"],"configuration",64000)
            if "configuration" in data else copy.deepcopy(old.configuration) if old else {})
    links=_watch(data.get("watch_links"),old)
    return task,task_revision,components,config,links


def _snapshot(rev,pins):
    task,taskrev,components,config,links=pins
    kwargs={kind:components[kind][0] for kind in COMPONENTS}
    kwargs.update({kind+"_revision":components[kind][1] for kind in COMPONENTS})
    snap=ForecastSnapshot.objects.create(revision=rev,task=task,task_revision=taskrev,
                                          configuration=config,**kwargs)
    ForecastWatchPin.objects.bulk_create([ForecastWatchPin(
        snapshot=snap,watch=watch,watch_revision=pin) for watch,pin in links])
    return snap


def _qualified(links,public=False):
    if not links:
        raise ForecastInvalid("Stage a forecast only with cited Technology Watch signals")
    for watch,revision in links:
        if not WatchSourcePin.objects.filter(entry_revision=revision).exists():
            raise ForecastInvalid("Every staged Watch signal requires a cited Research Source")
        if public:
            from .watch_services import serialize as show_watch
            if show_watch(watch,rev=revision,reader=True) is None:
                raise ForecastInvalid("Publish source evidence and the exact Watch revision first")


def _current(identifier):
    if not isinstance(identifier,str) or not identifier.startswith("fct-"):
        raise ForecastInvalid("Invalid Forecast identifier")
    item=CatalogItem.objects.select_for_update(of=("self",)).select_related(
        "current_revision__schema_version").filter(public_id=identifier,type_slug=KIND).first()
    if item is None:raise ForecastInvalid("Unknown theoretical forecast")
    return item


def _guard(item,expected):
    rev=item.current_revision
    if rev is None or expected!=f"r{rev.number:03d}":
        raise RevisionConflict("Forecast changed; reload exact revision")
    compat=compatibility_for_revision(item,rev)
    if compat["read_only"] or rev.schema_version.version!=1:
        raise SchemaWriteBlocked(compat)
    return rev


def create(*,actor,data):
    schema=_schema()
    if not isinstance(data,dict) or set(data)-{"name","properties","task_id","component_ids","configuration","watch_links"}:
        raise ForecastInvalid("Unsupported Forecast fields")
    props=_properties(data.get("properties",{}))
    if props["status"]!="draft":raise ForecastInvalid("Forecast must begin as Draft")
    name=validate_model(data.get("name"),props,schema.json_schema)
    for _ in range(12):
        identifier=new_public_id("fct")
        try:
            with transaction.atomic():
                pins=_pins(None,data)
                item=CatalogItem.objects.create(public_id=identifier,type_slug=KIND)
                rev=CatalogRevision.objects.create(
                    item=item,number=1,schema_version=schema,display_name=name,
                    properties=props,created_by=actor)
                _snapshot(rev,pins)
                item.current_revision=rev;item.save(update_fields=["current_revision"])
                record_catalog_event(item=item,revision=rev,actor=actor,action="created")
                return item
        except IntegrityError:
            if CatalogItem.objects.filter(public_id=identifier).exists():continue
            raise
    raise ExhaustedIds("Cannot allocate Forecast public ID")


def change(*,actor,identifier,data,action=None):
    with transaction.atomic():
        item=_current(identifier)
        old=_guard(item,data.get("expected_revision"))
        previous=ForecastSnapshot.objects.get(revision=old)
        if action is None:
            if set(data)-{"expected_revision","name","properties","task_id","component_ids","configuration","watch_links"}:
                raise ForecastInvalid("Unsupported Forecast edit")
            new_props=data.get("properties",{})
            if not isinstance(new_props,dict) or any(k in new_props for k in ("status","reviewer","review_notes","evidence_class")):
                raise ForecastInvalid("Lifecycle/reviewer is not editable through properties")
            props=_properties(new_props,old.properties)
            name=validate_model(data.get("name",old.display_name),props,old.schema_version.json_schema)
            pins=_pins(previous,data)
            current=_pins(previous,{})
            changed=(props!=old.properties or name!=old.display_name or
                     pins[:2]!=current[:2] or
                     [(v[0].pk,v[1].pk) for v in pins[2].values()]!=
                     [(v[0].pk,v[1].pk) for v in current[2].values()] or
                     pins[3]!=current[3] or
                     [(v[0].pk,v[1].pk) for v in pins[4]]!=
                     [(v[0].pk,v[1].pk) for v in current[4]])
            if not changed:return item,False
            # Any material change, including editing an already published version,
            # invalidates review; the prior version remains immutable & publishable.
            props.update(status="draft",reviewer=None,review_notes="")
            event="revised"
        else:
            if set(data)!={"expected_revision"}:
                raise ForecastInvalid("Review actions accept expected_revision only")
            allowed={"stage":("draft","staged"),
                     "review":("staged","reviewed"),
                     "publish":("reviewed","published"),
                     "rework":("staged","draft"),
                     "unpublish":("published","draft")}
            if action not in allowed or old.properties["status"]!=allowed[action][0]:
                raise ForecastInvalid("Invalid forecast lifecycle transition")
            props=copy.deepcopy(old.properties)
            props["status"]=allowed[action][1]
            if action=="review":props["reviewer"]=actor.get_username()
            if action in ("rework","unpublish"):props.update(reviewer=None,review_notes="")
            if action in ("stage","review","publish"):
                _qualified(_pins(previous,{})[4],public=action=="publish")
                if not props["uncertainty"].strip():
                    raise ForecastInvalid("State uncertainty before staging or publishing")
            name=old.display_name
            pins=_pins(previous,{})
            event=action
        rev=CatalogRevision.objects.create(
            item=item,number=old.number+1,schema_version=old.schema_version,
            display_name=name,properties=props,created_by=actor)
        _snapshot(rev,pins)
        item.current_revision=rev;item.save(update_fields=["current_revision"])
        record_catalog_event(item=item,revision=rev,actor=actor,action=event)
        return item,True


def serialize(item,rev=None,reader=False):
    rev=rev or item.current_revision
    if reader and (item.current_revision.properties.get("status")!="published" or
                   rev.properties.get("status")!="published"):
        return None
    snap=ForecastSnapshot.objects.select_related("task__item","task_revision",
        "model","provider","harness").get(revision=rev)
    watches=list(snap.watch_pins.select_related("watch","watch_revision").order_by("id"))
    result={"id":item.public_id,"revision":f"r{rev.number:03d}",
            "revision_id":str(rev.pk),"name":rev.display_name,"properties":rev.properties,
            "status":rev.properties["status"],"evidence_class":"theoretical",
            "measured_solution_id":None,
            "task_id":snap.task.item.public_id,"task_revision_id":str(snap.task_revision_id),
            "component_ids":{kind:getattr(snap,kind).public_id for kind in COMPONENTS},
            "component_revisions":{kind:str(getattr(snap,kind+"_revision_id")) for kind in COMPONENTS},
            "configuration":snap.configuration,
            "watch_links":[{"id":p.watch.public_id,"revision":f"r{p.watch_revision.number:03d}",
                            "revision_id":str(p.watch_revision_id)} for p in watches],
            "created_at":rev.created_at.isoformat(),
            "created_by":rev.created_by.get_username()}
    if reader:
        from .watch_services import serialize as watch_serialize
        if any(watch_serialize(p.watch,rev=p.watch_revision,reader=True) is None for p in watches):
            return None
    return result


def accessible(actor,task_id=None):
    reader=not (actor.has_perm("auth.business_write") or actor.has_perm("auth.publication_review"))
    objects=CatalogItem.objects.filter(type_slug=KIND).select_related(
        "current_revision__created_by").order_by("created_at","public_id")
    if task_id:objects=objects.filter(
        current_revision__forecast_snapshot__task__item__public_id=task_id)
    if reader:objects=objects.filter(current_revision__properties__status="published")
    result=[]
    for item in objects[:501]:
        row=serialize(item,reader=reader)
        if row is not None:result.append(row)
    return result
