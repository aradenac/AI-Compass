"""PLAT-11: an immutable registered guide schema; no business guide fixtures."""
from django.db import migrations

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "text": {"type":"string","maxLength":32768},
        "url": {"type":"string","maxLength":2048,"pattern":r"^https?://[^\s]+$"},
        "description": {"type":"string","maxLength":4000},
        "publication": {"type":"string","enum":["draft","published","archived"]},
    },
    "anyOf":[
        {"properties":{"text":{"type":"string","minLength":1}},"required":["text"]},
        {"properties":{"url":{"type":"string","minLength":8}},"required":["url"]},
    ],
    "additionalProperties": True,
}

def register(apps, editor):
    apps.get_model("config","ObjectTypeVersion").objects.using(editor.connection.alias).create(
        type_slug="setup_guide", version=1, json_schema=SCHEMA
    )

class Migration(migrations.Migration):
    dependencies=[("config","0009_test_case")]
    operations=[migrations.RunPython(register,migrations.RunPython.noop)]
