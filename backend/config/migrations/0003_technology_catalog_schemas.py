"""Register immutable Provider/Harness/Framework schemas without touching Model v1/v2."""
from django.db import migrations

SCHEMAS = {
 "provider": {
  "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
  "properties": {
   "hosting": {"type": "string"}, "access": {"type": "string"},
   "pricing": {"type": ["string", "object"]},
   "endpoint": {"type": "string"}, "regions": {"type": "array", "items": {"type": "string"}},
   "accessible": {"type": "boolean"}, "version": {"type": "string"},
   "publication": {"type": "string"}, "status": {"type": "string"},
   "url": {"type": "string"}, "details": {"type": "string"},
  }, "additionalProperties": True
 },
 "harness": {
  "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
  "properties": {
   "integrations": {"type": "array", "items": {"type": "string"}},
   "interface": {"type": "string", "enum": ["cli", "ide", "web", "agent", "multi"]},
   "agent_capabilities": {"type": "array", "items": {"type": "string"}},
   "accessible": {"type": "boolean"}, "version": {"type": "string"},
   "publication": {"type": "string"}, "status": {"type": "string"},
   "url": {"type": "string"}, "details": {"type": "string"},
  }, "additionalProperties": True
 },
 "framework": {
  "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
  "properties": {
   "process": {"type": "string"}, "orchestration": {"type": "string"},
   "stages": {"type": "array", "items": {"type": "string"}},
   "participant_roles": {"type": "array", "items": {"type": "string"}},
   "accessible": {"type": "boolean"}, "version": {"type": "string"},
   "publication": {"type": "string"}, "status": {"type": "string"},
   "url": {"type": "string"}, "details": {"type": "string"},
  }, "additionalProperties": True
 }
}


def register_catalog_schemas(apps, schema_editor):
    Registry = apps.get_model("config", "ObjectTypeVersion")
    for slug, schema in SCHEMAS.items():
        Registry.objects.using(schema_editor.connection.alias).create(
            type_slug=slug, version=1, json_schema=schema
        )


class Migration(migrations.Migration):
    dependencies = [("config", "0002_model_schema_v2")]
    operations = [
        migrations.RunPython(register_catalog_schemas, reverse_code=migrations.RunPython.noop),
    ]
