"""PLAT-09: additive, empty Server taxonomy with protected history and structure."""
import django.db.models.deletion
from django.db import migrations, models

TASK_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "phase": {"type": "string"},
        "domain": {"type": "string"},
        "baseline": {"type": "number", "minimum": 0},
        "status": {"type": "string", "enum": ["active", "retired"]},
        "desc": {"type": "string"},
        "criteria": {"type": "string"},
    },
    "additionalProperties": True,
}


def seed_task_schema(apps, schema_editor):
    apps.get_model("config", "ObjectTypeVersion").objects.using(
        schema_editor.connection.alias
    ).create(type_slug="task", version=1, json_schema=TASK_SCHEMA)


GUARDS = """
CREATE TRIGGER immutable_task_structure_revision
BEFORE UPDATE OR DELETE ON config_taskstructurerevision FOR EACH ROW
EXECUTE FUNCTION ai_compass_no_revision_mutation();

CREATE OR REPLACE FUNCTION ai_compass_check_task_structure_revision()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM config_catalogrevision r
    WHERE r.id = NEW.revision_id AND r.item_id = NEW.task_id
  ) THEN
    RAISE EXCEPTION 'Task placement revision must belong to its task';
  END IF;
  IF NEW.parent_id IS NOT NULL AND NEW.parent_id = NEW.task_id THEN
    RAISE EXCEPTION 'Task may not be its own parent';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER task_structure_revision_target
BEFORE INSERT ON config_taskstructurerevision FOR EACH ROW
EXECUTE FUNCTION ai_compass_check_task_structure_revision();

CREATE OR REPLACE FUNCTION ai_compass_check_task_parent()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM config_catalogitem c
    WHERE c.id = NEW.item_id AND c.type_slug = 'task'
  ) THEN
    RAISE EXCEPTION 'Task must reference a task catalog identity';
  END IF;
  IF NEW.parent_id IS NOT NULL THEN
    IF NEW.parent_id = NEW.item_id OR EXISTS (
      WITH RECURSIVE ancestors(item_id, parent_id) AS (
        SELECT p.item_id, p.parent_id FROM config_tasknode p
        WHERE p.item_id = NEW.parent_id
        UNION
        SELECT p.item_id, p.parent_id FROM config_tasknode p
        JOIN ancestors a ON a.parent_id = p.item_id
      ) SELECT 1 FROM ancestors WHERE item_id = NEW.item_id
    ) THEN
      RAISE EXCEPTION 'Task ancestry cycle refused';
    END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER task_node_parent_guard
BEFORE INSERT OR UPDATE OF parent_id, item_id ON config_tasknode
FOR EACH ROW EXECUTE FUNCTION ai_compass_check_task_parent();
"""

DROP_GUARDS = """
DROP TRIGGER IF EXISTS task_node_parent_guard ON config_tasknode;
DROP TRIGGER IF EXISTS task_structure_revision_target ON config_taskstructurerevision;
DROP TRIGGER IF EXISTS immutable_task_structure_revision ON config_taskstructurerevision;
DROP FUNCTION IF EXISTS ai_compass_check_task_parent();
DROP FUNCTION IF EXISTS ai_compass_check_task_structure_revision();
"""


class Migration(migrations.Migration):
    dependencies = [("config", "0004_evidence_store")]
    operations = [
        migrations.CreateModel(
            name="TaskNode",
            fields=[
                ("item", models.OneToOneField(primary_key=True, serialize=False,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="task_node", to="config.catalogitem")),
                ("position", models.PositiveIntegerField(default=0)),
                ("parent", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="children", to="config.tasknode")),
            ],
            options={"ordering": ["position", "item_id"]},
        ),
        migrations.CreateModel(
            name="TaskStructureRevision",
            fields=[
                ("revision", models.OneToOneField(primary_key=True, serialize=False,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="task_structure", to="config.catalogrevision")),
                ("position", models.PositiveIntegerField()),
                ("parent", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="config.tasknode")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="structure_history", to="config.tasknode")),
            ],
        ),
        migrations.RunPython(seed_task_schema, reverse_code=migrations.RunPython.noop),
        migrations.RunSQL(GUARDS, reverse_sql=DROP_GUARDS),
    ]
