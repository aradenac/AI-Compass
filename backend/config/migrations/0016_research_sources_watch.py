"""PLAT-18: new versioned Source and Watch types, FK revision links, no seeded business data."""
import django.db.models.deletion
from django.db import migrations, models

SOURCE_SCHEMA={
    "$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",
    "properties":{
        "claim":{"type":"string","minLength":1,"maxLength":10000},
        "citation":{"type":"string","maxLength":4000},
        "url":{"type":"string","maxLength":2048},
        "source_type":{"type":"string","enum":["research","provider_notice","benchmark","documentation","other"]},
        "confidence":{"type":["string","null"],"enum":["low","medium","high","unknown",None]},
        "limitations":{"type":"string","maxLength":10000},
        "published_on":{"type":["string","null"],"format":"date"},
        "retrieved_on":{"type":["string","null"],"format":"date"},
        "visibility":{"type":"string","enum":["internal","published"]},
    },"required":["claim","source_type","visibility"],"additionalProperties":True,
}
WATCH_SCHEMA={
    "$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",
    "properties":{
        "hypothesis":{"type":"string","minLength":1,"maxLength":10000},
        "assumptions":{"type":"string","maxLength":10000},
        "notes":{"type":"string","maxLength":20000},
        "visibility":{"type":"string","enum":["internal","published"]},
        "review_state":{"type":"string","enum":["draft","under_review","reviewed"]},
    },"required":["hypothesis","visibility","review_state"],"additionalProperties":True,
}

def register(apps,editor):
    version=apps.get_model("config","ObjectTypeVersion")
    for kind,schema in (("research_source",SOURCE_SCHEMA),("watch_entry",WATCH_SCHEMA)):
        version.objects.using(editor.connection.alias).create(
            type_slug=kind,version=1,json_schema=schema)

GUARDS="""
CREATE FUNCTION ai_compass_watch_source_pin_check() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM config_catalogrevision r
     JOIN config_catalogitem i ON i.id=r.item_id
     WHERE r.id=NEW.entry_revision_id AND i.type_slug='watch_entry') OR
     NOT EXISTS (SELECT 1 FROM config_catalogrevision r
     JOIN config_catalogitem i ON i.id=r.item_id
     WHERE r.id=NEW.source_revision_id AND r.item_id=NEW.source_id
     AND i.type_slug='research_source')
  THEN RAISE EXCEPTION 'Watch Source pin must reference exact type, item and immutable revision'; END IF;
  RETURN NEW;
END $body$;
CREATE TRIGGER valid_watch_source_pin BEFORE INSERT ON config_watchsourcepin
  FOR EACH ROW EXECUTE FUNCTION ai_compass_watch_source_pin_check();
CREATE TRIGGER immutable_watch_source_pin BEFORE UPDATE OR DELETE ON config_watchsourcepin
  FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""
UNDO="""
DROP TRIGGER IF EXISTS immutable_watch_source_pin ON config_watchsourcepin;
DROP TRIGGER IF EXISTS valid_watch_source_pin ON config_watchsourcepin;
DROP FUNCTION IF EXISTS ai_compass_watch_source_pin_check();
"""

class Migration(migrations.Migration):
    dependencies=[("config","0015_composite_runs")]
    operations=[
        migrations.RunPython(register,migrations.RunPython.noop),
        migrations.CreateModel(name="WatchSourcePin",fields=[
            ("id",models.BigAutoField(primary_key=True,serialize=False)),
            ("entry_revision",models.ForeignKey(to="config.catalogrevision",
                related_name="watch_source_pins",on_delete=django.db.models.deletion.PROTECT)),
            ("source",models.ForeignKey(to="config.catalogitem",
                related_name="+",on_delete=django.db.models.deletion.PROTECT)),
            ("source_revision",models.ForeignKey(to="config.catalogrevision",
                related_name="+",on_delete=django.db.models.deletion.PROTECT)),
        ],options={"constraints":[models.UniqueConstraint(
            fields=("entry_revision","source"),name="uniq_watch_source_revision")]}),
        migrations.RunSQL(GUARDS,reverse_sql=UNDO),
    ]
