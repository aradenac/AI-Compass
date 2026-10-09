"""PLAT-10: append-only Test Cases, distinct from task taxonomy and benchmark runs."""
from django.db import connection, IntegrityError, transaction

from .activity_services import record_catalog_event
from .catalog_compat import compatibility_for_revision
from .catalog_ids import new_public_id
from .catalog_schemas import validate_model, InvalidModel
from .catalog_services import RevisionConflict, ExhaustedIds
from .models import CatalogItem, CatalogRevision, ObjectTypeVersion, TaskNode, TestCase

LOCK = 101010
FIELDS = ("objective", "inputs", "constraints", "expected_outputs", "dod")
MAX_VERSION_LENGTH = 160


class InvalidTestCase(ValueError):
    pass


def _lock():
    if connection.vendor != "postgresql":
        raise InvalidTestCase("Test Case writes require PostgreSQL")
    with connection.cursor() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK])


def _schema():
    row = ObjectTypeVersion.objects.filter(type_slug="test_case", version=1).first()
    if row is None:
        raise InvalidTestCase("Registered Test Case schema unavailable")
    return row


def _task(public_id):
    if not isinstance(public_id, str) or not public_id.startswith("tsk-"):
        raise InvalidTestCase("A real Server task public ID is required")
    node = TaskNode.objects.select_related("item__current_revision").filter(
        item__public_id=public_id, item__type_slug="task").first()
    if node is None or node.item.current_revision_id is None:
        raise InvalidTestCase("Task does not exist in Server mode")
    return node


def _case(public_id):
    if not isinstance(public_id, str) or not public_id.startswith("tcs-"):
        raise InvalidTestCase("Invalid Test Case identifier")
    case = TestCase.objects.select_related(
        "item__current_revision__schema_version", "item__current_revision__created_by",
        "task__item", "fork_parent__item", "fork_source_revision",
        "task_revision_at_creation"
    ).filter(item__public_id=public_id, item__type_slug="test_case").first()
    if case is None:
        raise InvalidTestCase("Unknown Server Test Case")
    return case


def _properties(properties):
    if not isinstance(properties, dict):
        raise InvalidTestCase("properties must be an object")
    return properties


def _validate(name, properties, schema):
    try:
        return validate_model(name, properties, schema.json_schema)
    except InvalidModel as error:
        raise InvalidTestCase(str(error)) from error


def serialize(case, revision=None):
    item = case.item
    rev = revision or item.current_revision
    task = case.task
    return {
        "id":item.public_id, "uuid":str(item.pk), "type":"test_case",
        "name":rev.display_name, "properties":rev.properties,
        "revision":f"r{rev.number:03d}", "revision_id":str(rev.pk),
        "schema_version":rev.schema_version.version,
        "case_version":case.case_version,
        "task_id":task.item.public_id, "task_revision_at_creation":
            str(case.task_revision_at_creation_id),
        "fork_parent_id":case.fork_parent.item.public_id if case.fork_parent_id else None,
        "fork_source_revision_id":str(case.fork_source_revision_id)
            if case.fork_source_revision_id else None,
        "created_at":rev.created_at.isoformat(),
        "created_by":rev.created_by.get_username(),
        "compatibility":compatibility_for_revision(item, rev),
    }


def _create_case(*, actor, task, name, properties, parent=None, version="1.0"):
    schema = _schema()
    name = _validate(name, properties, schema)
    if len(version) > MAX_VERSION_LENGTH:
        raise InvalidTestCase("Fork version depth exhausted")
    for _ in range(12):
        public_id = new_public_id("tcs")
        try:
            with transaction.atomic():
                item = CatalogItem.objects.create(public_id=public_id,type_slug="test_case")
                rev = CatalogRevision.objects.create(
                    item=item,number=1,schema_version=schema,
                    display_name=name,properties=properties,created_by=actor)
                item.current_revision=rev
                item.save(update_fields=["current_revision"])
                case = TestCase.objects.create(
                    item=item,task=task,task_revision_at_creation=task.item.current_revision,
                    fork_parent=parent,
                    fork_source_revision=parent.item.current_revision if parent else None,
                    case_version=version)
                record_catalog_event(item=item,revision=rev,actor=actor,
                                     action="forked" if parent else "created")
                return case
        except IntegrityError:
            if CatalogItem.objects.filter(public_id=public_id).exists():
                continue
            raise
    raise ExhaustedIds("Could not allocate a unique Test Case ID")


def create(*, actor, name, task_id, properties):
    properties = _properties(properties)
    with transaction.atomic():
        _lock()
        return _create_case(actor=actor,task=_task(task_id),name=name,
                            properties=properties)


def fork(*, actor, parent_id, expected_parent_revision, name=None, properties=None):
    with transaction.atomic():
        _lock()
        parent = _case(parent_id)
        old=parent.item.current_revision
        if expected_parent_revision != f"r{old.number:03d}":
            raise RevisionConflict("Source Test Case changed; reload before forking")
        state=compatibility_for_revision(parent.item,old)
        if state["read_only"] or old.schema_version.version != 1:
            raise InvalidTestCase("Cannot fork an unsupported Test Case revision")
        children=list(TestCase.objects.filter(fork_parent=parent).values_list(
            "case_version",flat=True))
        suffixes=[]
        prefix=parent.case_version+"."
        for version in children:
            suffix=version[len(prefix):] if version.startswith(prefix) else ""
            if suffix.isdecimal():
                suffixes.append(int(suffix))
        version=prefix+str(max(suffixes,default=0)+1)
        # Keep parent raw extension keys when forking; never drop future metadata.
        props=dict(old.properties)
        if properties is not None:
            props.update(_properties(properties))
        return _create_case(actor=actor,task=parent.task,
                            name=name if name is not None else old.display_name,
                            properties=props,parent=parent,version=version)


def revise(*, actor, public_id, expected_revision, name=None, properties=None):
    with transaction.atomic():
        _lock()
        case=_case(public_id)
        item=CatalogItem.objects.select_for_update().get(pk=case.item_id)
        old=item.current_revision
        if expected_revision != f"r{old.number:03d}":
            raise RevisionConflict("Test Case changed; reload before saving")
        state=compatibility_for_revision(item,old)
        if state["read_only"] or old.schema_version.version != 1:
            raise InvalidTestCase("Test Case is not editable under this schema version")
        props=dict(old.properties)
        if properties is not None:
            props.update(_properties(properties))
        name=_validate(name if name is not None else old.display_name,
                       props,old.schema_version)
        rev=CatalogRevision.objects.create(
            item=item,number=old.number+1,schema_version=old.schema_version,
            display_name=name,properties=props,created_by=actor)
        item.current_revision=rev
        item.save(update_fields=["current_revision"])
        record_catalog_event(item=item,revision=rev,actor=actor,action="revised")
        case.item=item
        return case
