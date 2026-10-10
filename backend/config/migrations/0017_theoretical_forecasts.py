"""PLAT-20: technical forecast registry, exact immutable provenance, no forecasts seeded."""
import django.db.models.deletion
from django.db import migrations, models

SCHEMA={
 "$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",
 "properties":{
  "status":{"type":"string","enum":["draft","staged","reviewed","published"]},
  "rationale":{"type":"string","minLength":1,"maxLength":10000},
  "uncertainty":{"type":"string","maxLength":10000},
  "confidence":{"type":"string","enum":["low","medium","high","unknown"]},
  "predicted_metrics":{"type":"object","additionalProperties":True},
  "assumptions":{"type":"object","additionalProperties":True},
  "review_notes":{"type":"string","maxLength":10000},
  "reviewer":{"type":["string","null"]},
  "evidence_class":{"const":"theoretical"},
 }, "required":["status","rationale","predicted_metrics","uncertainty","assumptions",
                "confidence","evidence_class"],"additionalProperties":True,
}

def register(apps,editor):
    apps.get_model("config","ObjectTypeVersion").objects.using(editor.connection.alias).create(
        type_slug="forecast",version=1,json_schema=SCHEMA)

GUARDS="""
CREATE FUNCTION ai_compass_forecast_snapshot_check() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE kind text;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM config_catalogrevision r
   JOIN config_catalogitem i ON i.id=r.item_id
   WHERE r.id=NEW.revision_id AND i.type_slug='forecast') THEN
   RAISE EXCEPTION 'Invalid forecast revision'; END IF;
 IF NOT EXISTS(SELECT 1 FROM config_tasknode t JOIN config_catalogrevision r
   ON r.item_id=t.item_id WHERE t.item_id=NEW.task_id AND r.id=NEW.task_revision_id)
   THEN RAISE EXCEPTION 'Forecast task revision mismatch'; END IF;
 IF NOT EXISTS(SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i
   ON i.id=r.item_id WHERE i.id=NEW.model_id AND r.id=NEW.model_revision_id
     AND i.type_slug='model') OR
   NOT EXISTS(SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i
   ON i.id=r.item_id WHERE i.id=NEW.provider_id AND r.id=NEW.provider_revision_id
     AND i.type_slug='provider') OR
   NOT EXISTS(SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i
   ON i.id=r.item_id WHERE i.id=NEW.harness_id AND r.id=NEW.harness_revision_id
     AND i.type_slug='harness')
   THEN RAISE EXCEPTION 'Forecast component revision mismatch'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_forecast_snapshot BEFORE INSERT ON config_forecastsnapshot
 FOR EACH ROW EXECUTE FUNCTION ai_compass_forecast_snapshot_check();
CREATE FUNCTION ai_compass_forecast_watch_check() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM config_catalogrevision r
   JOIN config_catalogitem i ON i.id=r.item_id
   WHERE r.id=NEW.watch_revision_id AND r.item_id=NEW.watch_id
     AND i.type_slug='watch_entry') THEN
   RAISE EXCEPTION 'Forecast Watch pin must have exact Watch Entry revision'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_forecast_watch BEFORE INSERT ON config_forecastwatchpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_forecast_watch_check();
CREATE FUNCTION ai_compass_campaign_forecast_check() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM config_campaignsnapshot c
  JOIN config_catalogrevision r ON r.id=c.revision_id
  JOIN config_forecastsnapshot f ON f.revision_id=NEW.forecast_snapshot_id
  JOIN config_catalogrevision fr ON fr.id=f.revision_id
  WHERE c.revision_id=NEW.campaign_snapshot_id
    AND c.fixed_task_id=f.task_id AND c.fixed_task_revision_id=f.task_revision_id
    AND r.properties->>'mode'='task_centred'
    AND fr.properties->>'status' IN ('staged','reviewed','published')) THEN
   RAISE EXCEPTION 'Campaign must validate exact staged Forecast and Task revision'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_campaign_forecast BEFORE INSERT ON config_campaignforecastorigin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_campaign_forecast_check();
CREATE FUNCTION ai_compass_campaign_forecast_watch_check() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM config_campaignforecastorigin o
  JOIN config_forecastwatchpin w ON w.snapshot_id=o.forecast_snapshot_id
   AND w.watch_id=NEW.watch_id AND w.watch_revision_id=NEW.watch_revision_id
  WHERE o.campaign_snapshot_id=NEW.origin_id) THEN
   RAISE EXCEPTION 'Campaign Watch pin not present in originating Forecast snapshot'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_campaign_forecast_watch BEFORE INSERT ON config_campaignforecastwatchpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_campaign_forecast_watch_check();

CREATE TRIGGER immutable_forecast_snapshot BEFORE UPDATE OR DELETE ON config_forecastsnapshot
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_forecast_watch BEFORE UPDATE OR DELETE ON config_forecastwatchpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_campaign_forecast BEFORE UPDATE OR DELETE ON config_campaignforecastorigin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_campaign_forecast_watch BEFORE UPDATE OR DELETE ON config_campaignforecastwatchpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""
UNDO="""
DROP TRIGGER IF EXISTS immutable_campaign_forecast_watch ON config_campaignforecastwatchpin;
DROP TRIGGER IF EXISTS immutable_campaign_forecast ON config_campaignforecastorigin;
DROP TRIGGER IF EXISTS immutable_forecast_watch ON config_forecastwatchpin;
DROP TRIGGER IF EXISTS immutable_forecast_snapshot ON config_forecastsnapshot;
DROP TRIGGER IF EXISTS valid_campaign_forecast_watch ON config_campaignforecastwatchpin;
DROP FUNCTION IF EXISTS ai_compass_campaign_forecast_watch_check();
DROP TRIGGER IF EXISTS valid_campaign_forecast ON config_campaignforecastorigin;
DROP FUNCTION IF EXISTS ai_compass_campaign_forecast_check();
DROP TRIGGER IF EXISTS valid_forecast_watch ON config_forecastwatchpin;
DROP FUNCTION IF EXISTS ai_compass_forecast_watch_check();
DROP TRIGGER IF EXISTS valid_forecast_snapshot ON config_forecastsnapshot;
DROP FUNCTION IF EXISTS ai_compass_forecast_snapshot_check();
"""
protect=django.db.models.deletion.PROTECT

class Migration(migrations.Migration):
 dependencies=[("config","0016_research_sources_watch")]
 operations=[
  migrations.RunPython(register,migrations.RunPython.noop),
  migrations.CreateModel(name="ForecastSnapshot",fields=[
   ("revision",models.OneToOneField(primary_key=True,serialize=False,to="config.catalogrevision",
     related_name="forecast_snapshot",on_delete=protect)),
   ("task",models.ForeignKey(to="config.tasknode",related_name="+",on_delete=protect)),
   ("task_revision",models.ForeignKey(to="config.catalogrevision",related_name="+",on_delete=protect)),
   ("model",models.ForeignKey(to="config.catalogitem",related_name="+",on_delete=protect)),
   ("model_revision",models.ForeignKey(to="config.catalogrevision",related_name="+",on_delete=protect)),
   ("provider",models.ForeignKey(to="config.catalogitem",related_name="+",on_delete=protect)),
   ("provider_revision",models.ForeignKey(to="config.catalogrevision",related_name="+",on_delete=protect)),
   ("harness",models.ForeignKey(to="config.catalogitem",related_name="+",on_delete=protect)),
   ("harness_revision",models.ForeignKey(to="config.catalogrevision",related_name="+",on_delete=protect)),
   ("configuration",models.JSONField(default=dict)),
  ]),
  migrations.CreateModel(name="ForecastWatchPin",fields=[
   ("id",models.BigAutoField(primary_key=True,serialize=False)),
   ("snapshot",models.ForeignKey(to="config.forecastsnapshot",related_name="watch_pins",on_delete=protect)),
   ("watch",models.ForeignKey(to="config.catalogitem",related_name="+",on_delete=protect)),
   ("watch_revision",models.ForeignKey(to="config.catalogrevision",related_name="+",on_delete=protect)),
  ],options={"constraints":[models.UniqueConstraint(fields=("snapshot","watch"),
     name="uniq_forecast_watch")]}),
  migrations.CreateModel(name="CampaignForecastOrigin",fields=[
   ("campaign_snapshot",models.OneToOneField(primary_key=True,serialize=False,
      to="config.campaignsnapshot",related_name="forecast_origin",on_delete=protect)),
   ("forecast_snapshot",models.ForeignKey(to="config.forecastsnapshot",
      related_name="validation_campaigns",on_delete=protect)),
  ]),
  migrations.CreateModel(name="CampaignForecastWatchPin",fields=[
   ("id",models.BigAutoField(primary_key=True,serialize=False)),
   ("origin",models.ForeignKey(to="config.campaignforecastorigin",
      related_name="watch_pins",on_delete=protect)),
   ("watch",models.ForeignKey(to="config.catalogitem",related_name="+",on_delete=protect)),
   ("watch_revision",models.ForeignKey(to="config.catalogrevision",related_name="+",on_delete=protect)),
  ],options={"constraints":[models.UniqueConstraint(fields=("origin","watch"),
      name="uniq_campaign_forecast_watch")]}),
  migrations.RunSQL(GUARDS,reverse_sql=UNDO),
 ]
