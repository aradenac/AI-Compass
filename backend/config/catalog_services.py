"""Transactional Model lifecycle; always append, never change previous revisions."""
from django.db import IntegrityError, transaction

from .catalog_ids import new_public_id
from .catalog_schemas import validate_model, InvalidModel
from .catalog_compat import compatibility_for_revision
from .models import CatalogItem, CatalogRevision, CatalogAuditEvent, ObjectTypeVersion


class RevisionConflict(Exception):
    pass


class ExhaustedIds(Exception):
    pass


class SchemaWriteBlocked(Exception):
    """Historical data is readable but unsafe to revise with current capabilities."""
    def __init__(self, compatibility):
        super().__init__(compatibility["reason"] or "Schema is not safely editable")
        self.compatibility = compatibility


def model_schema(version=None):
    schemas = ObjectTypeVersion.objects.filter(type_slug="model")
    return schemas.get(version=version) if version is not None else schemas.order_by("-version").first()


def create_model(*, actor, name, properties):
    schema = model_schema()
    name = validate_model(name, properties, schema.json_schema)
    # A DB unique constraint is the source of truth. Savepoints allow retries
    # without poisoning an outer transaction in PostgreSQL.
    for _ in range(12):
        candidate = new_public_id()
        try:
            with transaction.atomic():
                item = CatalogItem.objects.create(public_id=candidate, type_slug="model")
                revision = CatalogRevision.objects.create(
                    item=item, number=1, schema_version=schema,
                    display_name=name, properties=properties, created_by=actor,
                )
                item.current_revision = revision
                item.save(update_fields=["current_revision"])
                CatalogAuditEvent.objects.create(
                    item=item, revision=revision, actor=actor, action="created"
                )
                return item
        except IntegrityError:
            # The retry is limited to a unique public-ID conflict: other DB
            # integrity failures must propagate rather than being concealed.
            if CatalogItem.objects.filter(public_id=candidate).exists():
                continue
            raise
    raise ExhaustedIds("could not reserve a unique public ID")


def revise_model(*, item, actor, expected_revision, name=None, properties=None):
    with transaction.atomic():
        locked = CatalogItem.objects.select_for_update().get(pk=item.pk, type_slug="model")
        previous = locked.current_revision
        if not previous or expected_revision != f"r{previous.number:03d}":
            raise RevisionConflict("revision mismatch; reload before editing")
        # Never silently promote a historical revision to v2. A v1 name/edit
        # remains validated and appended under its exact pinned v1 schema.
        compatibility = compatibility_for_revision(locked, previous)
        if compatibility["read_only"]:
            raise SchemaWriteBlocked(compatibility)
        schema = previous.schema_version
        updated_name = name if name is not None else previous.display_name
        updated_properties = properties if properties is not None else previous.properties
        updated_name = validate_model(updated_name, updated_properties, schema.json_schema)
        revision = CatalogRevision.objects.create(
            item=locked, number=previous.number + 1,
            schema_version=schema, display_name=updated_name,
            properties=updated_properties, created_by=actor,
        )
        locked.current_revision = revision
        locked.save(update_fields=["current_revision"])
        CatalogAuditEvent.objects.create(
            item=locked, revision=revision, actor=actor, action="revised"
        )
        return locked
