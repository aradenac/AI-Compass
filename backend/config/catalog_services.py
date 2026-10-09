"""One transactional, append-only catalog lifecycle for all registered technology types."""
from django.db import IntegrityError, transaction

from .catalog_ids import new_public_id
from .catalog_schemas import validate_model
from .catalog_compat import compatibility_for_revision, SUPPORTED_MODEL_VERSIONS
from .models import CatalogItem, CatalogRevision, ObjectTypeVersion
from .activity_services import record_catalog_event

CATALOG_TYPES = {
    "model": "mdl",
    "provider": "prv",
    "harness": "hrn",
    "framework": "frm",
    "setup_guide": "gui",
}
SUPPORTED_SCHEMA_VERSIONS = {
    "model": SUPPORTED_MODEL_VERSIONS,
    "provider": frozenset({1}),
    "harness": frozenset({1}),
    "framework": frozenset({1}),
    "setup_guide": frozenset({1}),
}


class RevisionConflict(Exception):
    pass


class ExhaustedIds(Exception):
    pass


class SchemaWriteBlocked(Exception):
    """Original record is still readable, but cannot safely be edited."""
    def __init__(self, compatibility):
        super().__init__(compatibility["reason"] or "Schema is not safely editable")
        self.compatibility = compatibility


def catalog_schema_for(type_slug, version=None):
    if type_slug not in CATALOG_TYPES:
        raise ValueError("Unknown technology catalog type")
    schema = ObjectTypeVersion.objects.filter(type_slug=type_slug)
    supported = SUPPORTED_SCHEMA_VERSIONS[type_slug]
    if version is None:
        return schema.filter(version__in=supported).order_by("-version").first()
    if version not in supported:
        raise ValueError("Application does not support writes to this schema version")
    return schema.get(version=version)


def model_schema(version=None):
    return catalog_schema_for("model", version=version)


def create_component(*, type_slug, actor, name, properties):
    if type_slug not in CATALOG_TYPES:
        raise ValueError("Unregistered catalog type")
    schema = catalog_schema_for(type_slug)
    if schema is None:
        raise ValueError("No supported schema registered for catalog type")
    name = validate_model(name, properties, schema.json_schema)
    for _ in range(12):
        candidate = new_public_id(CATALOG_TYPES[type_slug])
        try:
            with transaction.atomic():
                item = CatalogItem.objects.create(public_id=candidate, type_slug=type_slug)
                revision = CatalogRevision.objects.create(
                    item=item, number=1, schema_version=schema,
                    display_name=name, properties=properties, created_by=actor,
                )
                item.current_revision = revision
                item.save(update_fields=["current_revision"])
                record_catalog_event(item=item, revision=revision, actor=actor, action="created")
                return item
        except IntegrityError:
            if CatalogItem.objects.filter(public_id=candidate).exists():
                continue
            raise
    raise ExhaustedIds("could not reserve a unique public ID")


def revise_component(*, item, type_slug, actor, expected_revision,
                     name=None, properties=None):
    if type_slug not in CATALOG_TYPES:
        raise ValueError("Unregistered catalog type")
    with transaction.atomic():
        locked = CatalogItem.objects.select_for_update().get(pk=item.pk, type_slug=type_slug)
        previous = locked.current_revision
        if not previous or expected_revision != f"r{previous.number:03d}":
            raise RevisionConflict("revision mismatch; reload before editing")
        compatibility = compatibility_for_revision(locked, previous)
        if compatibility["read_only"] or previous.schema_version.version not in SUPPORTED_SCHEMA_VERSIONS[type_slug]:
            raise SchemaWriteBlocked(compatibility)
        # Pin to the preceding immutable registry row: no silent schema promotion.
        schema = previous.schema_version
        updated_name = name if name is not None else previous.display_name
        updated_properties = properties if properties is not None else previous.properties
        updated_name = validate_model(updated_name, updated_properties, schema.json_schema)
        revision = CatalogRevision.objects.create(
            item=locked, number=previous.number + 1, schema_version=schema,
            display_name=updated_name, properties=updated_properties, created_by=actor,
        )
        locked.current_revision = revision
        locked.save(update_fields=["current_revision"])
        previous_publication = previous.properties.get("publication")
        current_publication = updated_properties.get("publication")
        action = "revised"
        if previous_publication != "published" and current_publication == "published":
            action = "published"
        elif previous_publication == "published" and current_publication != "published":
            action = "unpublished"
        record_catalog_event(item=locked, revision=revision, actor=actor, action=action)
        return locked


def create_model(*, actor, name, properties):
    return create_component(type_slug="model", actor=actor, name=name, properties=properties)


def revise_model(*, item, actor, expected_revision, name=None, properties=None):
    return revise_component(type_slug="model", item=item, actor=actor,
                            expected_revision=expected_revision,
                            name=name, properties=properties)
