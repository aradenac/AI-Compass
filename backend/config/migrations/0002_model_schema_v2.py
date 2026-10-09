"""Schema v2 is additive and immutable: v1 records and schema rows remain intact.

V2 gives previously opaque extension keys published validation semantics.
A v1 object with an incompatible old extension can still be read (needs_review)
without inventing a value or silently converting it to v2.
"""
from django.db import migrations


MODEL_SCHEMA_V2 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "context_window": {"type": "integer", "minimum": 1},
        "modalities": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "supports_tools": {"type": "boolean"},
        "reasoning_effort": {"type": "string", "enum": ["none", "low", "medium", "high", "max"]},
        "model_identifier": {"type": "string", "minLength": 1},
        "accessible": {"type": "boolean"},
        # Existing v1 records can contain these as unconstrained extensions.
        # No value is defaulted or materialized into historical snapshots.
        "release_channel": {"type": "string", "enum": ["stable", "preview", "experimental"]},
        "max_output_tokens": {"type": "integer", "minimum": 1},
    },
    "additionalProperties": True,
}


def register_v2(apps, schema_editor):
    TypeVersion = apps.get_model("config", "ObjectTypeVersion")
    TypeVersion.objects.using(schema_editor.connection.alias).create(
        type_slug="model", version=2, json_schema=MODEL_SCHEMA_V2
    )


class Migration(migrations.Migration):
    dependencies = [("config", "0001_initial")]
    operations = [
        # Never erase a schema version: CatalogRevision may reference it.
        migrations.RunPython(register_v2, reverse_code=migrations.RunPython.noop),
    ]
