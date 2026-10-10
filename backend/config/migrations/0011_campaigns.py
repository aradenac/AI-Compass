"""PLAT-12: revision-pinned campaigns and versioned experimental methods.

Only technical descriptors are created on fresh Server; never seed campaigns.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

CAMPAIGN_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "objective": {"type": "string", "minLength": 1, "maxLength": 4000},
        "notes": {"type": "string", "maxLength": 20000},
        "mode": {"type": "string", "enum": ["task_centred", "solution_centred"]},
        "status": {"type": "string", "enum": ["planned", "in_progress", "under_review", "published"]},
        "archived": {"type": "boolean"},
    },
    "required": ["objective", "mode", "status", "archived"],
    "additionalProperties": True,
}

METHOD_FIELDS = {
    "steps": [
        {"key": "planning", "label": "Plan challenges and setup"},
        {"key": "execution", "label": "Execute controlled Test Cases"},
        {"key": "review", "label": "Review original evidence"},
    ],
    "criteria": [
        {"key": "dod", "label": "Test Case definition of done"},
        {"key": "reproducibility", "label": "Exact configuration and provenance"},
    ],
    "fields": [
        {"key": "objective", "type": "text", "required": True},
        {"key": "notes", "type": "text", "required": False},
    ],
}

def register(apps, editor):
    version=apps.get_model("config","ObjectTypeVersion")
    alias=editor.connection.alias
    version.objects.using(alias).create(type_slug="campaign",version=1,json_schema=CAMPAIGN_SCHEMA)
    for mode in ("task_centred","solution_centred"):
        version.objects.using(alias).create(
            type_slug="campaign_method_"+mode,version=1,
            json_schema={"mode":mode, "steps":METHOD_FIELDS["steps"],
                         "criteria":METHOD_FIELDS["criteria"],
                         "fields":METHOD_FIELDS["fields"],
                         "extensions":{}}
        )

GUARDS = """
CREATE TRIGGER immutable_campaign_snapshot BEFORE UPDATE OR DELETE
ON config_campaignsnapshot FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_campaign_cases BEFORE UPDATE OR DELETE
ON config_campaigncasepin FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_campaign_components BEFORE UPDATE OR DELETE
ON config_campaigncomponentpin FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();

CREATE FUNCTION ai_compass_validate_campaign_snapshot() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM config_catalogrevision r
                  JOIN config_catalogitem i ON i.id=r.item_id
                  WHERE r.id=NEW.revision_id AND i.type_slug='campaign') THEN
        RAISE EXCEPTION 'Campaign snapshot must refer to a campaign revision';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM config_objecttypeversion v
                  WHERE v.id=NEW.method_definition_id
                  AND v.type_slug LIKE 'campaign_method_%') THEN
        RAISE EXCEPTION 'Invalid campaign method definition';
    END IF;
    IF (NEW.fixed_task_id IS NULL) <> (NEW.fixed_task_revision_id IS NULL) THEN
        RAISE EXCEPTION 'Task and task revision must be pinned together';
    END IF;
    IF NEW.fixed_task_id IS NOT NULL AND NOT EXISTS(
        SELECT 1 FROM config_catalogrevision r
        JOIN config_tasknode t ON t.item_id=r.item_id
        WHERE r.id=NEW.fixed_task_revision_id AND t.item_id=NEW.fixed_task_id
    ) THEN RAISE EXCEPTION 'Task revision does not belong to task'; END IF;
    IF (NEW.guide_id IS NULL) <> (NEW.guide_revision_id IS NULL) THEN
        RAISE EXCEPTION 'Guide and guide revision must be pinned together';
    END IF;
    IF NEW.guide_id IS NOT NULL AND NOT EXISTS(
        SELECT 1 FROM config_catalogrevision r
        JOIN config_catalogitem i ON i.id=r.item_id
        WHERE r.id=NEW.guide_revision_id AND i.id=NEW.guide_id
          AND i.type_slug='setup_guide'
    ) THEN RAISE EXCEPTION 'Guide revision does not belong to guide'; END IF;
    RETURN NEW;
END $body$;
CREATE TRIGGER campaign_snapshot_reference_guard BEFORE INSERT
ON config_campaignsnapshot FOR EACH ROW EXECUTE FUNCTION ai_compass_validate_campaign_snapshot();

CREATE FUNCTION ai_compass_validate_campaign_pin() RETURNS trigger
LANGUAGE plpgsql AS $body$
DECLARE expected_type text;
BEGIN
    IF TG_TABLE_NAME='config_campaigncasepin' THEN
        IF NOT EXISTS(SELECT 1 FROM config_catalogrevision r
                      JOIN config_testcase t ON t.item_id=r.item_id
                      WHERE r.id=NEW.revision_id AND t.item_id=NEW.test_case_id) THEN
            RAISE EXCEPTION 'Pinned Test Case revision mismatch';
        END IF;
    ELSE
        expected_type=CASE NEW.kind WHEN 'model' THEN 'model'
            WHEN 'provider' THEN 'provider' WHEN 'harness' THEN 'harness' ELSE NULL END;
        IF expected_type IS NULL OR NOT EXISTS(
            SELECT 1 FROM config_catalogrevision r
            JOIN config_catalogitem i ON i.id=r.item_id
            WHERE r.id=NEW.revision_id AND i.id=NEW.component_id
              AND i.type_slug=expected_type) THEN
            RAISE EXCEPTION 'Pinned component revision or type mismatch';
        END IF;
    END IF;
    RETURN NEW;
END $body$;
CREATE TRIGGER campaign_case_reference_guard BEFORE INSERT
ON config_campaigncasepin FOR EACH ROW EXECUTE FUNCTION ai_compass_validate_campaign_pin();
CREATE TRIGGER campaign_component_reference_guard BEFORE INSERT
ON config_campaigncomponentpin FOR EACH ROW EXECUTE FUNCTION ai_compass_validate_campaign_pin();
"""
DROP_GUARDS = """
DROP TRIGGER IF EXISTS campaign_component_reference_guard ON config_campaigncomponentpin;
DROP TRIGGER IF EXISTS campaign_case_reference_guard ON config_campaigncasepin;
DROP FUNCTION IF EXISTS ai_compass_validate_campaign_pin();
DROP TRIGGER IF EXISTS campaign_snapshot_reference_guard ON config_campaignsnapshot;
DROP FUNCTION IF EXISTS ai_compass_validate_campaign_snapshot();
DROP TRIGGER IF EXISTS immutable_campaign_components ON config_campaigncomponentpin;
DROP TRIGGER IF EXISTS immutable_campaign_cases ON config_campaigncasepin;
DROP TRIGGER IF EXISTS immutable_campaign_snapshot ON config_campaignsnapshot;
"""

class Migration(migrations.Migration):
    dependencies=[("config","0010_setup_guide_schema"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="CampaignSnapshot",fields=[
            ("revision",models.OneToOneField(primary_key=True,serialize=False,
                related_name="campaign_snapshot",on_delete=django.db.models.deletion.PROTECT,
                to="config.catalogrevision")),
            ("configuration",models.JSONField(default=dict)),
            ("owner",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_campaign_snapshots",to=settings.AUTH_USER_MODEL)),
            ("method_definition",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="campaign_snapshots",to="config.objecttypeversion")),
            ("fixed_task",models.ForeignKey(blank=True,null=True,
                on_delete=django.db.models.deletion.PROTECT,related_name="+",to="config.tasknode")),
            ("fixed_task_revision",models.ForeignKey(blank=True,null=True,
                on_delete=django.db.models.deletion.PROTECT,related_name="+",to="config.catalogrevision")),
            ("guide",models.ForeignKey(blank=True,null=True,
                on_delete=django.db.models.deletion.PROTECT,related_name="+",to="config.catalogitem")),
            ("guide_revision",models.ForeignKey(blank=True,null=True,
                on_delete=django.db.models.deletion.PROTECT,related_name="+",to="config.catalogrevision")),
        ]),
        migrations.CreateModel(name="CampaignCasePin",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False)),
            ("snapshot",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="case_pins",to="config.campaignsnapshot")),
            ("test_case",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.testcase")),
            ("revision",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.catalogrevision")),
        ],options={"constraints":[models.UniqueConstraint(fields=("snapshot","test_case"),
                name="uniq_campaign_snapshot_case")]}),
        migrations.CreateModel(name="CampaignComponentPin",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False)),
            ("snapshot",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="component_pins",to="config.campaignsnapshot")),
            ("kind",models.CharField(max_length=12)),
            ("component",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.catalogitem")),
            ("revision",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.catalogrevision")),
        ],options={"constraints":[models.UniqueConstraint(fields=("snapshot","kind"),
                name="uniq_campaign_snapshot_component")]}),
        migrations.RunPython(register,migrations.RunPython.noop),
        migrations.RunSQL(GUARDS,reverse_sql=DROP_GUARDS),
    ]
