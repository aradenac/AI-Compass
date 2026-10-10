"""PLAT-23: persistent shared chronological feedback, immutable corrections, scoped privacy.

The API never infers permissions from client mode or filters after serializing
restricted content. Each individual message has a permanent CatalogItem, every
change is an attributable CatalogRevision; links remain relationally pinned.
"""
import copy
import json

from django.db import transaction,IntegrityError
from .activity_services import record_catalog_event
from .catalog_ids import new_public_id
from .catalog_compat import compatibility_for_revision
from .catalog_schemas import validate_model
from .catalog_services import RevisionConflict, SchemaWriteBlocked, ExhaustedIds
from .models import (CatalogItem,CatalogRevision,ObjectTypeVersion,DiscussionThread,
                     DiscussionMessage,EvidenceLink)

PUBLIC_CONTEXT_TYPES=frozenset({
    "task","model","provider","harness","framework","solution",
})
THREAD_KINDS=frozenset({"feedback","question","idea","request","discussion"})
VISIBILITY=frozenset({"public","internal"})
MAX_THREADS=500
MAX_MESSAGES=500


class InvalidDiscussion(ValueError):
    pass


def privileged(user):
    return (user.has_perm("auth.business_write") or
            user.has_perm("auth.publication_review"))


def _schema(kind):
    s=ObjectTypeVersion.objects.filter(type_slug=kind,version=1).first()
    if s is None:raise InvalidDiscussion("Discussion schema not registered")
    return s


def _object(value,limit=24000):
    if not isinstance(value,dict):
        raise InvalidDiscussion("Expected JSON object")
    try:
        if len(json.dumps(value,allow_nan=False,ensure_ascii=False))>limit:
            raise InvalidDiscussion("Discussion record too large")
    except (ValueError,TypeError) as exc:
        raise InvalidDiscussion("Invalid JSON") from exc
    return copy.deepcopy(value)


def _text(value,key,max_length,required=False):
    if not isinstance(value,str) or len(value)>max_length or (required and not value.strip()):
        raise InvalidDiscussion(key+" must be a bounded"+(" nonempty" if required else "")+" string")
    return value.strip() if required else value


def _thread_props(payload):
    p=_object(payload,8000)
    if set(p)-{"scope","kind","description","extensions"}:
        raise InvalidDiscussion("Unsupported thread fields")
    p.setdefault("scope","public")
    p.setdefault("kind","feedback")
    p.setdefault("description","")
    p.setdefault("extensions",{})
    if p["scope"] not in VISIBILITY or p["kind"] not in THREAD_KINDS:
        raise InvalidDiscussion("Invalid thread scope or kind")
    _text(p["description"],"description",4000)
    if not isinstance(p["extensions"],dict):
        raise InvalidDiscussion("Thread extensions must be an object")
    return p


def _message_props(payload,previous=None):
    p=_object(payload)
    if set(p)-{"body","visibility","edit_reason","extensions"}:
        raise InvalidDiscussion("Unsupported message fields")
    out=copy.deepcopy(previous or {})
    out.update(p)
    out.setdefault("edit_reason","")
    out.setdefault("extensions",{})
    _text(out.get("body"),"body",16000,True)
    if out.get("visibility") not in VISIBILITY:
        raise InvalidDiscussion("Invalid message visibility")
    _text(out["edit_reason"],"edit_reason",4000)
    if not isinstance(out["extensions"],dict):
        raise InvalidDiscussion("Extensions must be an object")
    return _object(out)


def _context(identifier):
    if identifier is None:
        return None,None
    if not isinstance(identifier,str) or len(identifier)>120:
        raise InvalidDiscussion("Invalid context object ID")
    item=CatalogItem.objects.select_related("current_revision").filter(public_id=identifier).first()
    if not item or item.type_slug not in PUBLIC_CONTEXT_TYPES or not item.current_revision_id:
        raise InvalidDiscussion("Unknown or unsupported public discussion context object")
    return item,item.current_revision


def _thread(identifier):
    if not isinstance(identifier,str) or not identifier.startswith("thr-"):
        raise InvalidDiscussion("Invalid discussion thread ID")
    row=DiscussionThread.objects.select_related(
        "item__current_revision","context_item","context_revision").filter(
        item__public_id=identifier).first()
    if row is None:raise InvalidDiscussion("Unknown discussion thread")
    return row


def _message(identifier):
    if not isinstance(identifier,str) or not identifier.startswith("msg-"):
        raise InvalidDiscussion("Invalid discussion message ID")
    row=DiscussionMessage.objects.select_related(
        "item__current_revision__created_by","thread__item__current_revision","parent__item__current_revision").filter(
        item__public_id=identifier).first()
    if row is None:raise InvalidDiscussion("Unknown discussion message")
    return row


def _thread_visible(thread,user):
    return privileged(user) or thread.item.current_revision.properties.get("scope")=="public"


def _message_visible(message,user,rev=None):
    if not _thread_visible(message.thread,user):return False
    if privileged(user):return True
    # A newly internalized record must not be accessible through a prior
    # public revision or a raw attachment UUID.
    if message.item.current_revision.properties.get("visibility")!="public":
        return False
    if rev is not None and rev.properties.get("visibility")!="public":return False
    parent=message.parent
    while parent:
        if parent.item.current_revision.properties.get("visibility")!="public":
            return False
        parent=parent.parent
    return True


def readable_revision(item,user,revision=None):
    """Single central ACL for generic catalog and binary evidence routes."""
    if item.type_slug=="discussion_thread":
        row=DiscussionThread.objects.select_related(
            "item__current_revision").filter(item=item).first()
        return bool(row and _thread_visible(row,user) and (
            revision is None or revision.item_id==item.pk))
    if item.type_slug=="discussion_message":
        row=DiscussionMessage.objects.select_related("item__current_revision",
            "thread__item__current_revision","parent__item__current_revision").filter(item=item).first()
        return bool(row and _message_visible(row,user,revision) and (
            revision is None or revision.item_id==item.pk))
    return False


def _new_item(kind,actor,name,properties,callback):
    schema=_schema(kind)
    name=validate_model(name,properties,schema.json_schema)
    from .catalog_services import CATALOG_TYPES
    for _ in range(12):
        identifier=new_public_id(CATALOG_TYPES[kind])
        try:
            with transaction.atomic():
                item=CatalogItem.objects.create(public_id=identifier,type_slug=kind)
                revision=CatalogRevision.objects.create(
                    item=item,number=1,schema_version=schema,
                    display_name=name,properties=properties,created_by=actor)
                callback(item,revision)
                item.current_revision=revision;item.save(update_fields=["current_revision"])
                record_catalog_event(item=item,revision=revision,actor=actor,action="created")
                return item
        except IntegrityError:
            if CatalogItem.objects.filter(public_id=identifier).exists():continue
            raise
    raise ExhaustedIds("Discussion ID allocation exhausted")


def create_thread(actor,data):
    data=_object(data)
    if set(data)-{"title","properties","context_id","body","visibility"}:
        raise InvalidDiscussion("Unsupported thread input")
    props=_thread_props(data.get("properties",{}))
    if props["scope"]=="internal" and not privileged(actor):
        raise InvalidDiscussion("Only workgroup can create internal conversations")
    context,context_revision=_context(data.get("context_id"))
    title=_text(data.get("title"),"title",160,True)
    body=_text(data.get("body"),"body",16000,True)
    visibility=data.get("visibility","public" if props["scope"]=="public" else "internal")
    if visibility not in VISIBILITY or (visibility=="internal" and not privileged(actor)):
        raise InvalidDiscussion("Only workgroup can post internal messages")
    if props["scope"]=="internal" and visibility!="internal":
        raise InvalidDiscussion("Internal thread cannot have public messages")
    with transaction.atomic():
        def saved(item,revision):
            DiscussionThread.objects.create(item=item,context_item=context,
                                            context_revision=context_revision)
        item=_new_item("discussion_thread",actor,title,props,saved)
        row=DiscussionThread.objects.get(item=item)
        message=create_message(actor,row,{
            "body":body,"visibility":visibility})
        return row,message


def create_message(actor,thread,data):
    data=_object(data)
    if set(data)-{"body","visibility","parent_id","extensions"}:
        raise InvalidDiscussion("Unsupported reply input")
    if not _thread_visible(thread,actor):
        raise InvalidDiscussion("Unknown discussion")
    scope=thread.item.current_revision.properties["scope"]
    visibility=data.get("visibility","public" if scope=="public" else "internal")
    if visibility=="internal" and not privileged(actor):
        raise InvalidDiscussion("Only workgroup may post internal replies")
    if scope=="internal" and visibility!="internal":
        raise InvalidDiscussion("Internal thread cannot have a public message")
    parent=None
    if data.get("parent_id") is not None:
        parent=_message(data["parent_id"])
        if parent.thread_id!=thread.pk or not _message_visible(parent,actor):
            raise InvalidDiscussion("Parent message not accessible within thread")
        if visibility=="public" and parent.item.current_revision.properties["visibility"]!="public":
            raise InvalidDiscussion("Cannot publish a reply under an internal parent")
    props=_message_props({
        "body":data.get("body"),"visibility":visibility,"extensions":data.get("extensions",{})})
    title="Reply" if parent else "Feedback"
    def saved(item,revision):
        DiscussionMessage.objects.create(item=item,thread=thread,parent=parent)
    item=_new_item("discussion_message",actor,title,props,saved)
    return DiscussionMessage.objects.select_related("item__current_revision").get(item=item)


def revise_message(actor,identifier,expected_revision,properties):
    with transaction.atomic():
        msg=_message(identifier)
        item=CatalogItem.objects.select_for_update(of=("self",)).select_related("current_revision__schema_version").get(pk=msg.item_id)
        current=item.current_revision
        if expected_revision!=f"r{current.number:03d}":
            raise RevisionConflict("Message changed; reload")
        compat=compatibility_for_revision(item,current)
        if compat["read_only"] or current.schema_version.version!=1:
            raise SchemaWriteBlocked(compat)
        if not privileged(actor) and msg.item.revisions.order_by("number").first().created_by_id!=actor.pk:
            raise InvalidDiscussion("Only author/workgroup may correct this message")
        if not _message_visible(msg,actor):
            raise InvalidDiscussion("Not permitted to revise internal message")
        if not isinstance(properties,dict):
            raise InvalidDiscussion("Revision properties must be an object")
        if "edit_reason" not in properties:
            raise InvalidDiscussion("A correction or moderation reason is mandatory")
        reason=_text(properties["edit_reason"],"edit_reason",4000,True)
        if (not privileged(actor) and properties.get("visibility",current.properties["visibility"])
            !=current.properties["visibility"]):
            raise InvalidDiscussion("Only workgroup may change message visibility")
        props=_message_props(properties,current.properties)
        props["edit_reason"]=reason
        if props["visibility"]=="public":
            if msg.thread.item.current_revision.properties["scope"]!="public":
                raise InvalidDiscussion("Cannot make internal thread message public")
            if msg.parent and msg.parent.item.current_revision.properties["visibility"]!="public":
                raise InvalidDiscussion("Cannot publish a child of an internal message")
        if props["visibility"]=="internal":
            if not privileged(actor):raise InvalidDiscussion("Internal message needs workgroup permission")
            # Prevent orphaning public descendants. Old revisions remain immutable.
            if DiscussionMessage.objects.filter(parent=msg,
                item__current_revision__properties__visibility="public").exists():
                raise InvalidDiscussion("Hide/reclassify public child replies first")
        rev=CatalogRevision.objects.create(item=item,number=current.number+1,
            schema_version=current.schema_version,display_name=current.display_name,
            properties=props,created_by=actor)
        item.current_revision=rev;item.save(update_fields=["current_revision"])
        record_catalog_event(item=item,revision=rev,actor=actor,action="corrected")
        # Reload rather than serializing the select_related cache from r001.
        return _message(identifier)


def thread_record(thread,user):
    if not _thread_visible(thread,user):return None
    item=thread.item
    rev=item.current_revision
    count=thread.messages.filter(
        item__current_revision__properties__visibility="public").count() if not privileged(user) else thread.messages.count()
    return {
        "id":item.public_id,"revision":f"r{rev.number:03d}","title":rev.display_name,
        "properties":rev.properties,
        "context_id":thread.context_item.public_id if thread.context_item else None,
        "context_revision_id":str(thread.context_revision_id) if thread.context_item else None,
        "message_count":count,"created_at":rev.created_at.isoformat(),
        "created_by":rev.created_by.get_username(),
    }


def message_record(msg,user,rev=None):
    if not _message_visible(msg,user,rev):return None
    current=msg.item.current_revision
    rev=rev or current
    links=EvidenceLink.objects.select_related("blob","revision","uploaded_by").filter(
        item=msg.item,revision=rev).order_by("created_at","id")
    from .evidence_store import serialize as evidence_serialize
    return {
        "id":msg.item.public_id,"thread_id":msg.thread.item.public_id,
        "parent_id":msg.parent.item.public_id if msg.parent else None,
        "revision":f"r{rev.number:03d}","revision_id":str(rev.pk),
        "body":rev.properties["body"],"visibility":rev.properties["visibility"],
        "edit_reason":rev.properties.get("edit_reason",""),
        "extensions":rev.properties.get("extensions",{}),
        "created_by":msg.item.revisions.order_by("number").first().created_by.get_username(),
        "revision_by":rev.created_by.get_username(),
        "created_at":msg.item.created_at.isoformat(),
        "revision_at":rev.created_at.isoformat(),
        "attachments":[evidence_serialize(x) for x in links],
    }


def list_threads(user):
    result=[]
    for thread in DiscussionThread.objects.select_related(
        "item__current_revision__created_by","context_item").order_by(
        "item__created_at","item__public_id")[:MAX_THREADS+1]:
        data=thread_record(thread,user)
        if data is not None:result.append(data)
    if len(result)>MAX_THREADS:raise InvalidDiscussion("Too many discussions; narrow scope")
    return result


def list_messages(thread,user):
    if not _thread_visible(thread,user):return None
    output=[]
    messages=thread.messages.select_related("item__current_revision__created_by",
        "parent__item__current_revision","thread__item").order_by(
        "item__created_at","item__public_id")[:MAX_MESSAGES+1]
    for msg in messages:
        item=message_record(msg,user)
        if item is not None:output.append(item)
    if len(output)>MAX_MESSAGES:raise InvalidDiscussion("Too many messages for one thread")
    return output
