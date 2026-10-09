"""PLAT-10: add schema definition and protected test-case ancestry."""
import django.db.models.deletion
from django.db import migrations, models

TEST_CASE_SCHEMA = {
    "$schema":"https://json-schema.org/draft/2020-12/schema",
    "type":"object",
    "properties":{
        "objective":{"type":"string","minLength":1},
        "inputs":{"type":"string"},
        "constraints":{"type":"string"},
        "expected_outputs":{"type":"string"},
        "dod":{"type":"string","minLength":1},
        "environment":{"type":"string"},
        "difficulty":{"type":"string"},
    },
    "required":["objective","dod"],
    "additionalProperties":True,
}


def seed_schema(apps, editor):
    apps.get_model("config","ObjectTypeVersion").objects.using(editor.connection.alias).create(
        type_slug="test_case",version=1,json_schema=TEST_CASE_SCHEMA
    )


GUARDS = """
CREATE TRIGGER immutable_test_case_identity
BEFORE UPDATE OF item_id, task_id, task_revision_at_creation_id,
                 fork_parent_id, fork_source_revision_id, case_version
    OR DELETE ON config_testcase FOR EACH ROW
EXECUTE FUNCTION ai_compass_no_revision_mutation();

CREATE FUNCTION ai_compass_check_testcase_identity() RETURNS trigger
LANGUAGE plpgsql AS $case_guard$
BEGIN
  IF NOT EXISTS(
    SELECT 1 FROM config_catalogitem c
    WHERE c.id=NEW.item_id AND c.type_slug='test_case'
  ) THEN
    RAISE EXCEPTION 'Test Case identity must be a registered test_case catalog item';
  END IF;
  IF NOT EXISTS(
    SELECT 1 FROM config_catalogrevision r
    WHERE r.id=NEW.task_revision_at_creation_id
      AND r.item_id=NEW.task_id AND EXISTS(
        SELECT 1 FROM config_catalogitem c WHERE c.id=NEW.task_id AND c.type_slug='task'
      )
  ) THEN
    RAISE EXCEPTION 'Original task revision does not belong to referenced task';
  END IF;
  IF NEW.fork_parent_id IS NULL THEN
    IF NEW.case_version <> '1.0' OR NEW.fork_source_revision_id IS NOT NULL THEN
      RAISE EXCEPTION 'Root Test Case must have version 1.0 and no fork source';
    END IF;
  ELSE
    IF NEW.fork_parent_id=NEW.item_id THEN
      RAISE EXCEPTION 'Test Case cannot fork itself';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM config_testcase parent
      JOIN config_catalogrevision source
        ON source.id=NEW.fork_source_revision_id
      WHERE parent.item_id=NEW.fork_parent_id
        AND parent.task_id=NEW.task_id
        AND source.item_id=parent.item_id
        AND NEW.case_version ~ '^[0-9]+(\\.[0-9]+)+$'
        AND NEW.case_version LIKE parent.case_version || '.%'
        AND split_part(substr(NEW.case_version, length(parent.case_version)+2), '.', 2)=''
        AND substring(NEW.case_version from length(parent.case_version)+2)::integer > 0
    ) THEN
      RAISE EXCEPTION 'Fork version, task or pinned source revision is inconsistent';
    END IF;
  END IF;
  RETURN NEW;
END $case_guard$;

CREATE TRIGGER test_case_create_guard
BEFORE INSERT ON config_testcase FOR EACH ROW
EXECUTE FUNCTION ai_compass_check_testcase_identity();
"""
DROP_GUARDS = """
DROP TRIGGER IF EXISTS test_case_create_guard ON config_testcase;
DROP FUNCTION IF EXISTS ai_compass_check_testcase_identity();
DROP TRIGGER IF EXISTS immutable_test_case_identity ON config_testcase;
"""


class Migration(migrations.Migration):
    dependencies = [("config","0008_data_health")]
    operations = [
        migrations.CreateModel(
            name="TestCase",
            fields=[
                ("item",models.OneToOneField(primary_key=True,serialize=False,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="test_case",to="config.catalogitem")),
                ("case_version",models.CharField(max_length=160)),
                ("task",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="test_cases",to="config.tasknode")),
                ("task_revision_at_creation",models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,related_name="+",
                    to="config.catalogrevision")),
                ("fork_parent",models.ForeignKey(blank=True,null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="forks",to="config.testcase")),
                ("fork_source_revision",models.ForeignKey(blank=True,null=True,
                    on_delete=django.db.models.deletion.PROTECT,related_name="+",
                    to="config.catalogrevision")),
            ],
            options={
                "ordering":["item__public_id"],
                "constraints":[models.UniqueConstraint(
                    fields=("fork_parent","case_version"),
                    name="uniq_test_case_fork_version")],
            },
        ),
        migrations.RunPython(seed_schema,reverse_code=migrations.RunPython.noop),
        migrations.RunSQL(GUARDS,reverse_sql=DROP_GUARDS),
    ]
