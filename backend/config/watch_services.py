"""PLAT-18: authoritative Source library and revision-pinned Watch hypotheses.

CatalogItem+CatalogRevision own immutable identities/content/audit. The WatchSourcePin
join is append-only for EACH entry revision; unlinking only creates a new entry
revision, never deletes an earlier edge or canonical source.
"""
import copy
import json
from datetime import date
from urllib.parse import urlsplit

from django.db import transaction
from django.db.models import Q

from .catalog_ids import new_public_id
from .catalog_services import create_component, RevisionConflict, SchemaWriteBlocked
from .catalog_compat import compatibility_for_revision
from .catalog_schemas import InvalidModel, validate_model
from .activity_services import record_catalog_event
from .models import CatalogItem, CatalogRevision, WatchSourcePin

SOURCE="research_source"
WATCH="watch_entry"
TYPES={SOURCE:"src",WATCH:"wat"}
VISIBILITY={"internal","published"}
REVIEW={"draft","under_review","reviewed"}
MAX_LINKS=64


def _props(kind,properties,old=None):
    if not isinstance(properties,dict):
        raise InvalidModel("properties must be a JSON object")
    state=copy.deepcopy(old or {})
    state.update(properties)
    visible=state.setdefault("visibility","internal")
    if visible not in VISIBILITY:raise InvalidModel("Invalid visibility")
    if kind==SOURCE:
        claim=state.get("claim")
        if not isinstance(claim,str) or not claim.strip() or len(claim)>10000:
            raise InvalidModel("Research Source needs a claim (max 10000 characters)")
        for key,limit in (("citation",4000),("limitations",10000)):
            value=state.get(key,"")
            if not isinstance(value,str) or len(value)>limit:
                raise InvalidModel(key+" must be bounded text")
        kind_of_source=state.setdefault("source_type","research")
        if kind_of_source not in ("research","provider_notice","benchmark","documentation","other"):
            raise InvalidModel("Unknown source type")
        if state.get("confidence") not in (None,"low","medium","high","unknown"):
            raise InvalidModel("Invalid confidence")
        if "url" in state and state["url"] not in ("",None):
            link=state["url"]
            if not isinstance(link,str) or len(link)>2048 or any(
                    ord(ch)<33 or ord(ch)==127 for ch in link):
                raise InvalidModel("Source URL must not contain whitespace/control characters")
            try:
                parsed=urlsplit(link);port=parsed.port
            except (ValueError,TypeError) as exc:
                raise InvalidModel("Invalid Source URL") from exc
            if (parsed.scheme not in ("http","https") or not parsed.hostname or
                    parsed.username is not None or parsed.password is not None or
                    port==0 or link.startswith(("http:///","https:///"))):
                raise InvalidModel("Source URL must be absolute HTTP(S) without credentials")
        else:
            state.pop("url",None)
        for field in ("published_on","retrieved_on"):
            value=state.get(field)
            if value is not None:
                if not isinstance(value,str):
                    raise InvalidModel(field+" must be an ISO date or null")
                try:
                    if date.fromisoformat(value).isoformat()!=value:
                        raise ValueError("noncanonical")
                except ValueError as exc:
                    raise InvalidModel(field+" must be an ISO date or null") from exc
    else:
        hypothesis=state.get("hypothesis")
        if not isinstance(hypothesis,str) or not hypothesis.strip() or len(hypothesis)>10000:
            raise InvalidModel("Watch Entry needs a hypothesis (max 10000 characters)")
        for field,limit in (("assumptions",10000),("notes",20000)):
            if not isinstance(state.get(field,""),str) or len(state.get(field,""))>limit:
                raise InvalidModel(field+" must be bounded text")
        if state.setdefault("review_state","draft") not in REVIEW:
            raise InvalidModel("Invalid review state")
        if visible=="published" and state["review_state"]!="reviewed":
            raise InvalidModel("A published Watch Entry must be reviewed")
    if len(json.dumps(state,ensure_ascii=False,allow_nan=False))>30000:
        raise InvalidModel("Properties exceed 30 KiB")
    return state


def _new(kind,actor,name,properties):
    item=create_component(type_slug=kind,actor=actor,name=name,
                          properties=_props(kind,properties))
    return item


def _revise(item,actor,expected_revision,name,properties,allow_publication):
    with transaction.atomic():
        locked=CatalogItem.objects.select_for_update(of=("self",)).select_related(
            "current_revision__schema_version").get(pk=item.pk)
        old=locked.current_revision
        if old is None or expected_revision!=f"r{old.number:03d}":
            raise RevisionConflict("Record changed; reload current revision")
        compatible=compatibility_for_revision(locked,old)
        if compatible["read_only"] or old.schema_version.version!=1:
            raise SchemaWriteBlocked(compatible)
        props=_props(locked.type_slug,properties,old.properties)
        if not allow_publication and props.get("visibility")!=old.properties.get("visibility"):
            raise InvalidModel("Changing visibility requires a review action")
        if not allow_publication and locked.type_slug==WATCH and props.get("review_state")!=old.properties.get("review_state"):
            raise InvalidModel("Review state changes require a review action")
        display=validate_model(name if name is not None else old.display_name,
                               props,old.schema_version.json_schema)
        return locked,old,props,display


def _publishable(pins):
    for source,revision in pins:
        if (source.current_revision.properties.get("visibility")!="published" or
                revision.properties.get("visibility")!="published"):
            raise InvalidModel("Publish linked sources first; internal source evidence cannot be exposed")


def _links(data,prior=None):
    if data is None:
        return list(prior or [])
    if not isinstance(data,list) or len(data)>MAX_LINKS:
        raise InvalidModel("sources must be a list of at most 64 exact source references")
    resolved=[]
    seen=set()
    for row in data:
        if not isinstance(row,dict) or set(row)-{"id","revision"}:
            raise InvalidModel("Each source must specify id and optional exact revision")
        ref=row.get("id")
        if not isinstance(ref,str) or not ref.startswith("src-") or ref in seen:
            raise InvalidModel("Duplicate or invalid source ID")
        seen.add(ref)
        source=CatalogItem.objects.select_related("current_revision").filter(
            public_id=ref,type_slug=SOURCE).first()
        if source is None:raise InvalidModel("Source does not exist")
        revision=row.get("revision")
        if revision is None:
            rev=source.current_revision
        elif isinstance(revision,str) and revision.startswith("r") and revision[1:].isdigit():
            n=int(revision[1:])
            if revision!=f"r{n:03d}":raise InvalidModel("Revision must be exact r001 format")
            rev=CatalogRevision.objects.filter(item=source,number=n).first()
        else:raise InvalidModel("Invalid Source revision")
        if rev is None:raise InvalidModel("Source revision does not exist")
        resolved.append((source,rev))
    return resolved


def _source_payload(source,rev,reader=False):
    p=rev.properties
    if reader and (p.get("visibility")!="published" or
                   source.current_revision.properties.get("visibility")!="published"):
        return None
    return {"id":source.public_id,"revision":f"r{rev.number:03d}",
            "revision_id":str(rev.pk),"name":rev.display_name,
            "properties":p,"created_by":rev.created_by.get_username(),
            "created_at":rev.created_at.isoformat()}


def _entry_links(rev):
    return [(p.source,p.source_revision) for p in WatchSourcePin.objects.filter(
        entry_revision=rev).select_related(
            "source__current_revision","source_revision__created_by").order_by("id")]


def serialize(item,rev=None,reader=False):
    rev=rev or item.current_revision
    if item.type_slug==SOURCE:return _source_payload(item,rev,reader=reader)
    pins=_entry_links(rev)
    if reader and any(_source_payload(src,pinned,reader=True) is None for src,pinned in pins):
        return None
    if reader and (rev.properties.get("visibility")!="published" or
                   item.current_revision.properties.get("visibility")!="published"):
        return None
    return {"id":item.public_id,"revision":f"r{rev.number:03d}",
            "revision_id":str(rev.pk),"name":rev.display_name,"properties":rev.properties,
            "created_at":rev.created_at.isoformat(),"created_by":rev.created_by.get_username(),
            "sources":[_source_payload(src,version,reader=reader) for src,version in pins]}


def create(kind,actor,name,properties,sources=None):
    if kind not in TYPES:raise InvalidModel("Unsupported Watch type")
    with transaction.atomic():
        pins=_links(sources) if kind==WATCH else []
        props=_props(kind,properties)
        if props["visibility"]=="published":
            raise InvalidModel("New records begin internally; submit them for review")
        item=_new(kind,actor,name,props)
        if kind==WATCH:
            WatchSourcePin.objects.bulk_create([
                WatchSourcePin(entry_revision=item.current_revision,source=src,source_revision=rev)
                for src,rev in pins])
        return item


def revise(kind,actor,item,expected_revision,name=None,properties=None,sources=None,
           review_action=None):
    if kind not in TYPES or item.type_slug!=kind:raise InvalidModel("Wrong type")
    with transaction.atomic():
        locked,old,props,display=_revise(
            item,actor,expected_revision,name,properties or {},
            allow_publication=review_action is not None)
        if review_action is not None:
            if kind==WATCH:
                transitions={"submit":("draft","under_review"),"approve":("under_review","reviewed"),
                             "publish":("reviewed","reviewed"),"unpublish":("reviewed","under_review")}
                if review_action not in transitions or props["review_state"]!=transitions[review_action][0]:
                    raise InvalidModel("Invalid Watch review transition")
                props["review_state"]=transitions[review_action][1]
                props["visibility"]="published" if review_action=="publish" else "internal"
            else:
                if review_action not in ("publish","unpublish"):
                    raise InvalidModel("Unknown Research Source review action")
                desired="published" if review_action=="publish" else "internal"
                if old.properties["visibility"]==desired:
                    raise InvalidModel("Source already has requested visibility")
                props["visibility"]=desired
            props=_props(kind,props)
        previous=_entry_links(old) if kind==WATCH else []
        pins=_links(sources,prior=previous) if kind==WATCH else []
        if props["visibility"]=="published" and kind==WATCH:_publishable(pins)
        if kind==WATCH and sources is not None and review_action:
            raise InvalidModel("Review transitions cannot silently alter source links")
        if props==old.properties and display==old.display_name and (
                kind!=WATCH or [(s.pk,r.pk) for s,r in pins]==[(s.pk,r.pk) for s,r in previous]):
            return locked,False
        rev=CatalogRevision.objects.create(
            item=locked,number=old.number+1,schema_version=old.schema_version,
            display_name=display,properties=props,created_by=actor)
        if kind==WATCH:
            WatchSourcePin.objects.bulk_create([
                WatchSourcePin(entry_revision=rev,source=src,source_revision=r)
                for src,r in pins])
        locked.current_revision=rev
        locked.save(update_fields=["current_revision"])
        record_catalog_event(item=locked,revision=rev,actor=actor,
                             action=review_action or "revised")
        return locked,True


def accessible(kind,actor,q=""):
    if kind not in TYPES:raise InvalidModel("Unsupported Watch type")
    items=CatalogItem.objects.filter(type_slug=kind).select_related(
        "current_revision__created_by","current_revision__schema_version"
    ).order_by("public_id")
    if q:
        items=items.filter(Q(public_id__icontains=q)|Q(current_revision__display_name__icontains=q))
    if not actor.has_perm("auth.business_write") and not actor.has_perm("auth.publication_review"):
        items=items.filter(current_revision__properties__visibility="published")
    result=[]
    reader=not (actor.has_perm("auth.business_write") or actor.has_perm("auth.publication_review"))
    for item in items[:501]:
        payload=serialize(item,reader=reader)
        if payload is not None:result.append(payload)
    return result
