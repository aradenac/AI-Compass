"""First immutable catalog schema: UUIDv7 identities, revisions, versioned schemas."""
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids


MODEL_SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "context_window": {"type": "integer", "minimum": 1},
        "modalities": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "supports_tools": {"type": "boolean"},
        "reasoning_effort": {"type": "string", "enum": ["none", "low", "medium", "high", "max"]},
        "model_identifier": {"type": "string", "minLength": 1},
        "accessible": {"type": "boolean"},
    },
    "additionalProperties": True,
}


def seed_model_schema(apps, schema_editor):
    Schema = apps.get_model("config", "ObjectTypeVersion")
    Schema.objects.using(schema_editor.connection.alias).create(
        type_slug="model", version=1, json_schema=MODEL_SCHEMA_V1
    )


DB_GUARDS = """
CREATE OR REPLACE FUNCTION ai_compass_no_revision_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Immutable catalog history cannot be modified or deleted';
END $$;

CREATE TRIGGER immutable_catalog_revision BEFORE UPDATE OR DELETE
ON config_catalogrevision FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_catalog_schema BEFORE UPDATE OR DELETE
ON config_objecttypeversion FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_catalog_audit BEFORE UPDATE OR DELETE
ON config_catalogauditevent FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();

CREATE OR REPLACE FUNCTION ai_compass_protect_catalog_identity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE referenced_item uuid;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Catalog identities must be retained as permanent tombstones';
  END IF;
  IF NEW.id IS DISTINCT FROM OLD.id OR NEW.public_id IS DISTINCT FROM OLD.public_id
     OR NEW.type_slug IS DISTINCT FROM OLD.type_slug
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'Catalog technical and public identity is immutable';
  END IF;
  IF NEW.current_revision_id IS NOT NULL THEN
    SELECT item_id INTO referenced_item FROM config_catalogrevision
      WHERE id = NEW.current_revision_id;
    IF referenced_item IS DISTINCT FROM NEW.id THEN
      RAISE EXCEPTION 'Current revision must belong to the catalog item';
    END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER protect_catalog_identity BEFORE UPDATE OR DELETE
ON config_catalogitem FOR EACH ROW EXECUTE FUNCTION ai_compass_protect_catalog_identity();
"""

DROP_GUARDS = """
DROP TRIGGER IF EXISTS protect_catalog_identity ON config_catalogitem;
DROP TRIGGER IF EXISTS immutable_catalog_audit ON config_catalogauditevent;
DROP TRIGGER IF EXISTS immutable_catalog_schema ON config_objecttypeversion;
DROP TRIGGER IF EXISTS immutable_catalog_revision ON config_catalogrevision;
DROP FUNCTION IF EXISTS ai_compass_protect_catalog_identity();
DROP FUNCTION IF EXISTS ai_compass_no_revision_mutation();
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="ObjectTypeVersion",
            fields=[
                ("id", models.UUIDField(default=config.catalog_ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ("type_slug", models.SlugField(max_length=40)),
                ("version", models.PositiveIntegerField()),
                ("json_schema", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["type_slug", "version"]},
        ),
        migrations.CreateModel(
            name="CatalogItem",
            fields=[
                ("id", models.UUIDField(default=config.catalog_ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ("public_id", models.CharField(max_length=120, unique=True)),
                ("type_slug", models.SlugField(default="model", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["created_at", "public_id"]},
        ),
        migrations.CreateModel(
            name="CatalogRevision",
            fields=[
                ("id", models.UUIDField(default=config.catalog_ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ("number", models.PositiveIntegerField()),
                ("display_name", models.CharField(max_length=160)),
                ("properties", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="revisions", to="config.catalogitem")),
                ("schema_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="revisions", to="config.objecttypeversion")),
            ],
            options={"ordering": ["item", "number"]},
        ),
        migrations.CreateModel(
            name="CatalogAuditEvent",
            fields=[
                ("id", models.UUIDField(default=config.catalog_ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="config.catalogitem")),
                ("revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="config.catalogrevision")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddField(
            model_name="catalogitem",
            name="current_revision",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="config.catalogrevision"),
        ),
        migrations.AddConstraint(
            model_name="objecttypeversion",
            constraint=models.UniqueConstraint(fields=("type_slug", "version"), name="uniq_object_type_version"),
        ),
        migrations.AddConstraint(
            model_name="catalogrevision",
            constraint=models.UniqueConstraint(fields=("item", "number"), name="uniq_item_revision_number"),
        ),
        migrations.RunPython(seed_model_schema, reverse_code=migrations.RunPython.noop),
        migrations.RunSQL(DB_GUARDS, reverse_sql=DROP_GUARDS),
    ]
