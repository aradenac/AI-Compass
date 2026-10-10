"""PLAT-13: additive framework/trio pins; no backfill or Demo fixture import."""
import django.db.models.deletion
from django.db import migrations, models
from config.catalog_ids import uuid7

SQL = """
CREATE TRIGGER immutable_campaign_participant_identity BEFORE UPDATE OR DELETE
ON config_campaignparticipantidentity FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_campaign_participant_pin BEFORE UPDATE OR DELETE
ON config_campaignparticipantpin FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();

CREATE FUNCTION ai_compass_check_framework_pin() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  IF (NEW.framework_id IS NULL) <> (NEW.framework_revision_id IS NULL) THEN
    RAISE EXCEPTION 'Framework identity and revision must be pinned together';
  END IF;
  IF NEW.framework_id IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM config_catalogrevision r
    JOIN config_catalogitem i ON i.id=r.item_id
    WHERE i.id=NEW.framework_id AND i.type_slug='framework'
    AND r.id=NEW.framework_revision_id
  ) THEN RAISE EXCEPTION 'Framework revision is not from the referenced Framework'; END IF;
  RETURN NEW;
END $body$;

CREATE TRIGGER campaign_framework_reference_guard BEFORE INSERT
ON config_campaignsnapshot FOR EACH ROW EXECUTE FUNCTION ai_compass_check_framework_pin();

CREATE FUNCTION ai_compass_check_participant_identity() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  IF NOT EXISTS(SELECT 1 FROM config_catalogitem
                WHERE id=NEW.campaign_id AND type_slug='campaign') THEN
    RAISE EXCEPTION 'Participant identity must belong to a registered campaign';
  END IF;
  RETURN NEW;
END $body$;
CREATE TRIGGER campaign_participant_identity_guard BEFORE INSERT
ON config_campaignparticipantidentity FOR EACH ROW EXECUTE FUNCTION ai_compass_check_participant_identity();

CREATE FUNCTION ai_compass_check_participant_pin() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  IF NOT EXISTS(
    SELECT 1 FROM config_campaignsnapshot s
    JOIN config_catalogrevision r ON r.id=s.revision_id
    JOIN config_campaignparticipantidentity i ON i.id=NEW.participant_id
    WHERE s.revision_id=NEW.snapshot_id AND s.framework_id IS NOT NULL
      AND r.item_id=i.campaign_id
  ) THEN RAISE EXCEPTION 'Participant belongs to a different campaign or a non-Framework snapshot'; END IF;

  IF NOT EXISTS(
    SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i ON i.id=r.item_id
    WHERE r.id=NEW.model_revision_id AND i.id=NEW.model_id AND i.type_slug='model'
  ) OR NOT EXISTS(
    SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i ON i.id=r.item_id
    WHERE r.id=NEW.provider_revision_id AND i.id=NEW.provider_id AND i.type_slug='provider'
  ) OR NOT EXISTS(
    SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i ON i.id=r.item_id
    WHERE r.id=NEW.harness_revision_id AND i.id=NEW.harness_id AND i.type_slug='harness'
  ) THEN RAISE EXCEPTION 'Participant components or revision references are inconsistent'; END IF;
  RETURN NEW;
END $body$;
CREATE TRIGGER campaign_participant_pin_guard BEFORE INSERT
ON config_campaignparticipantpin FOR EACH ROW EXECUTE FUNCTION ai_compass_check_participant_pin();
"""

REVERSE = """
DROP TRIGGER IF EXISTS campaign_participant_pin_guard ON config_campaignparticipantpin;
DROP FUNCTION IF EXISTS ai_compass_check_participant_pin();
DROP TRIGGER IF EXISTS campaign_participant_identity_guard ON config_campaignparticipantidentity;
DROP FUNCTION IF EXISTS ai_compass_check_participant_identity();
DROP TRIGGER IF EXISTS campaign_framework_reference_guard ON config_campaignsnapshot;
DROP FUNCTION IF EXISTS ai_compass_check_framework_pin();
DROP TRIGGER IF EXISTS immutable_campaign_participant_pin ON config_campaignparticipantpin;
DROP TRIGGER IF EXISTS immutable_campaign_participant_identity ON config_campaignparticipantidentity;
"""

class Migration(migrations.Migration):
    dependencies = [("config", "0011_campaigns")]
    operations = [
        migrations.AddField(model_name="campaignsnapshot",name="framework",
            field=models.ForeignKey(blank=True,null=True,related_name="+",
               on_delete=django.db.models.deletion.PROTECT,to="config.catalogitem")),
        migrations.AddField(model_name="campaignsnapshot",name="framework_revision",
            field=models.ForeignKey(blank=True,null=True,related_name="+",
               on_delete=django.db.models.deletion.PROTECT,to="config.catalogrevision")),
        migrations.CreateModel(name="CampaignParticipantIdentity",fields=[
            ("id",models.UUIDField(primary_key=True,default=uuid7,editable=False,serialize=False)),
            ("public_id",models.CharField(max_length=120,unique=True)),
            ("campaign",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="participant_identities",to="config.catalogitem")),
        ]),
        migrations.CreateModel(name="CampaignParticipantPin",fields=[
            ("id",models.UUIDField(primary_key=True,default=uuid7,editable=False,serialize=False)),
            ("position",models.PositiveIntegerField()),
            ("label",models.CharField(max_length=160)),
            ("role",models.CharField(max_length=160)),
            ("configuration_version",models.CharField(max_length=160)),
            ("settings",models.JSONField(default=dict)),
            ("properties",models.JSONField(default=dict)),
            ("snapshot",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name="participant_pins",to="config.campaignsnapshot")),
            ("participant",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name="snapshots",to="config.campaignparticipantidentity")),
            ("model",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name="+",to="config.catalogitem")),
            ("model_revision",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name="+",to="config.catalogrevision")),
            ("provider",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name="+",to="config.catalogitem")),
            ("provider_revision",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name="+",to="config.catalogrevision")),
            ("harness",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name="+",to="config.catalogitem")),
            ("harness_revision",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                 related_name="+",to="config.catalogrevision")),
        ],options={
            "ordering":["position","participant__public_id"],
            "constraints":[
                models.UniqueConstraint(fields=("snapshot","participant"),name="uniq_campaign_participant_revision"),
                models.UniqueConstraint(fields=("snapshot","position"),name="uniq_campaign_participant_order"),
            ],
        }),
        migrations.RunSQL(SQL,reverse_sql=REVERSE),
    ]
