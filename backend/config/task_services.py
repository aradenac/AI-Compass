"""PLAT-09: versioned engineering task taxonomy with relational placement.

All writes serialize through one PostgreSQL transaction advisory lock. Structural
revisions are always appended (including siblings shifted by a reordering).
There is no delete or cross-runtime data synchronization.
"""
from django.db import IntegrityError, connection, transaction

from .catalog_compat import compatibility_for_revision
from .catalog_ids import new_public_id
from .catalog_schemas import InvalidModel, validate_model
from .catalog_services import ExhaustedIds, RevisionConflict
from .models import (
    CatalogAuditEvent, CatalogItem, CatalogRevision, ObjectTypeVersion,
    TaskNode, TaskStructureRevision,
)

LOCK_ID = 2940901


class InvalidTask(ValueError):
    pass


def _lock_taxonomy():
    if connection.vendor != "postgresql":
        raise InvalidTask("Taxonomy writes require PostgreSQL transactions")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_ID])


def _all_nodes():
    return list(
        TaskNode.objects.select_related(
            "item__current_revision__schema_version",
            "item__current_revision__created_by", "parent__item"
        ).order_by("position", "item__public_id")
    )


def _resolve(nodes, public_id):
    if public_id is None:
        return None
    if not isinstance(public_id, str) or not public_id.startswith("tsk-"):
        raise InvalidTask("Invalid task parent/anchor identifier")
    for node in nodes:
        if node.item.public_id == public_id:
            return node
    raise InvalidTask("Task parent or ordering anchor does not exist")


def _expected(revision, expected):
    if not isinstance(expected, str) or expected != f"r{revision.number:03d}":
        raise RevisionConflict("Task changed concurrently; reload before saving")


def _schema_for_new():
    schema = ObjectTypeVersion.objects.filter(type_slug="task", version=1).first()
    if schema is None:
        raise InvalidTask("Task schema is unavailable")
    return schema


def _append(node, actor, *, name=None, properties=None, action="revised"):
    """One immutable content revision and its exact structure snapshot."""
    item = node.item
    old = item.current_revision
    schema = old.schema_version
    if schema.type_slug != "task" or schema.version != 1:
        raise InvalidTask("Unsupported task schema version; preserve historical data")
    if compatibility_for_revision(item, old)["read_only"]:
        raise InvalidTask("Task is not safely editable; schema review required")
    next_properties = dict(old.properties)
    if properties is not None:
        if not isinstance(properties, dict):
            raise InvalidTask("properties must be an object")
        next_properties.update(properties)  # merge unknown fields, never silently discard
    next_name = name if name is not None else old.display_name
    try:
        next_name = validate_model(next_name, next_properties, schema.json_schema)
    except InvalidModel as error:
        raise InvalidTask(str(error)) from error
    row = CatalogRevision.objects.create(
        item=item, number=old.number + 1, schema_version=schema,
        display_name=next_name, properties=next_properties, created_by=actor,
    )
    TaskStructureRevision.objects.create(
        revision=row, task=node, parent=node.parent, position=node.position
    )
    item.current_revision = row
    item.save(update_fields=["current_revision"])
    CatalogAuditEvent.objects.create(item=item, revision=row, actor=actor, action=action)


def _siblings(nodes, parent):
    parent_id = parent.pk if parent else None
    return [n for n in nodes if n.parent_id == parent_id]


def _validate_position(nodes, parent, before, moving=None):
    siblings = [n for n in _siblings(nodes, parent) if n.pk != (moving.pk if moving else None)]
    if before is not None:
        anchor = _resolve(nodes, before)
        if anchor.pk == (moving.pk if moving else None) or anchor not in siblings:
            raise InvalidTask("Ordering anchor must be a different sibling of target parent")
        index = siblings.index(anchor)
    else:
        index = len(siblings)
    return siblings, index


def _apply_order(nodes, parent, actor, special=None, name=None, properties=None):
    """Materialize ordered siblings and retain immutable history for all changes."""
    touched = False
    for index, node in enumerate(nodes):
        moved = node.parent_id != (parent.pk if parent else None) or node.position != index
        is_special = special is not None and node.pk == special.pk
        changed_fields = is_special and (name is not None or properties is not None)
        if moved:
            node.parent = parent
            node.position = index
            node.save(update_fields=["parent", "position"])
        if moved or changed_fields:
            _append(node, actor, name=name if is_special else None,
                    properties=properties if is_special else None,
                    action="reorganized" if moved else "revised")
            touched = True
    return touched


def create_task(*, actor, name, properties=None, parent_id=None, before=None):
    if properties is None:
        properties = {}
    schema = _schema_for_new()
    try:
        name = validate_model(name, properties, schema.json_schema)
    except InvalidModel as error:
        raise InvalidTask(str(error)) from error
    for _ in range(12):
        try:
            with transaction.atomic():
                _lock_taxonomy()
                nodes = _all_nodes()
                parent = _resolve(nodes, parent_id)
                destination, index = _validate_position(nodes, parent, before)
                candidate = new_public_id("tsk")
                item = CatalogItem.objects.create(public_id=candidate, type_slug="task")
                revision = CatalogRevision.objects.create(
                    item=item, number=1, schema_version=schema,
                    display_name=name, properties=properties, created_by=actor,
                )
                item.current_revision = revision
                item.save(update_fields=["current_revision"])
                node = TaskNode.objects.create(item=item, parent=parent, position=index)
                TaskStructureRevision.objects.create(
                    revision=revision, task=node, parent=parent, position=index
                )
                CatalogAuditEvent.objects.create(item=item, revision=revision, actor=actor, action="created")
                destination.insert(index, node)
                for i, sibling in enumerate(destination):
                    if sibling.pk == node.pk:
                        continue
                    if sibling.position != i:
                        sibling.position = i
                        sibling.save(update_fields=["position"])
                        _append(sibling, actor, action="reorganized")
                return node
        except IntegrityError:
            if CatalogItem.objects.filter(public_id=candidate).exists():
                continue
            raise
    raise ExhaustedIds("Could not allocate task public identifier")


def update_task(*, public_id, expected_revision, actor,
                name=None, properties=None, parent_id_marker=Ellipsis, before_marker=Ellipsis):
    with transaction.atomic():
        _lock_taxonomy()
        nodes = _all_nodes()
        node = _resolve(nodes, public_id)
        if node is None:
            raise InvalidTask("Task does not exist")
        _expected(node.item.current_revision, expected_revision)
        parent = node.parent if parent_id_marker is Ellipsis else _resolve(nodes, parent_id_marker)
        # Follow parent chain to prevent moving a task into itself/its descendants.
        ancestor = parent
        seen = set()
        while ancestor is not None:
            if ancestor.pk == node.pk or ancestor.pk in seen:
                raise InvalidTask("Cyclic or broken task ancestry is not allowed")
            seen.add(ancestor.pk)
            ancestor = ancestor.parent
        old_siblings = [n for n in _siblings(nodes, node.parent) if n.pk != node.pk]
        before = None if before_marker is Ellipsis else before_marker
        if before_marker is Ellipsis and parent.pk if parent is not None else False:
            pass
        if before_marker is Ellipsis and parent.pk == node.parent_id if parent is not None else (node.parent_id is None):
            # Preserve relative placement when only editing name/properties.
            dest = [n for n in _siblings(nodes, parent) if n.pk != node.pk]
            insert_index = min(node.position, len(dest))
        else:
            dest, insert_index = _validate_position(nodes, parent, before, moving=node)
        dest.insert(insert_index, node)
        source_changed = node.parent_id != (parent.pk if parent else None)
        # Move must materialize the selected node once, with any content changes.
        if source_changed:
            _apply_order(old_siblings, node.parent, actor)
        changed = _apply_order(dest, parent, actor, special=node, name=name, properties=properties)
        return node, changed


def serialize_task(node, revision=None):
    row = revision or node.item.current_revision
    if revision is not None:
        snap = row.task_structure
        parent, position = snap.parent, snap.position
    else:
        parent, position = node.parent, node.position
    return {
        "id": node.item.public_id, "uuid": str(node.pk),
        "type": "task", "name": row.display_name,
        "revision": f"r{row.number:03d}",
        "schema_version": row.schema_version.version,
        "properties": row.properties, "parent_id": parent.item.public_id if parent else None,
        "position": position, "created_at": row.created_at.isoformat(),
        "created_by": row.created_by.get_username(),
        "compatibility": compatibility_for_revision(node.item, row),
    }
