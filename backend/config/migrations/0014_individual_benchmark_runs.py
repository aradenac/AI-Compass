"""PLAT-15: additive immutable per-session setup and measured individual runs."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from config.catalog_ids import uuid7

SOLUTION_SCHEMA={
    "$schema":"https://json-schema.org/draft/2020-12/schema",
    "type":"object",
    "properties":{
        "fingerprint":{"type":"string","pattern":"^[0-9a-f]{64}$"},
        "lifecycle":{"type":"string","enum":["draft","published","retired"]},
    },
    "required":["fingerprint","lifecycle"],
    "additionalProperties":True,
}

def register(apps,schema_editor):
    table=apps.get_model("config","ObjectTypeVersion")
    table.objects.using(schema_editor.connection.alias).create(
        type_slug="ai_solution",version=1,json_schema=SOLUTION_SCHEMA)

GUARDS="""
CREATE FUNCTION ai_compass_check_session_solution_pin() RETURNS trigger LANGUAGE plpgsql AS $b$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i
    ON i.id=r.item_id WHERE i.id=NEW.model_id AND r.id=NEW.model_revision_id AND i.type_slug='model')
  OR NOT EXISTS (SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i
    ON i.id=r.item_id WHERE i.id=NEW.provider_id AND r.id=NEW.provider_revision_id AND i.type_slug='provider')
  OR NOT EXISTS (SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i
    ON i.id=r.item_id WHERE i.id=NEW.harness_id AND r.id=NEW.harness_revision_id AND i.type_slug='harness')
  THEN RAISE EXCEPTION 'Session component IDs, types and revisions must match'; END IF;
  RETURN NEW;
END $b$;
CREATE TRIGGER valid_session_solution_pin BEFORE INSERT ON config_sessionsolutionpin
  FOR EACH ROW EXECUTE FUNCTION ai_compass_check_session_solution_pin();

CREATE FUNCTION ai_compass_check_measured_solution() RETURNS trigger LANGUAGE plpgsql AS $b$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM config_catalogitem WHERE id=NEW.item_id AND type_slug='ai_solution')
 THEN RAISE EXCEPTION 'Measured solution must use the ai_solution catalog'; END IF;
 RETURN NEW;
END $b$;
CREATE TRIGGER valid_measured_solution BEFORE INSERT ON config_measuredsolution
 FOR EACH ROW EXECUTE FUNCTION ai_compass_check_measured_solution();

CREATE FUNCTION ai_compass_check_benchmark_run() RETURNS trigger LANGUAGE plpgsql AS $b$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM config_sessioncheckpoint WHERE id=NEW.closing_checkpoint_id
     AND session_id=NEW.session_id AND action='closed' AND state->>'status'='closed')
 THEN RAISE EXCEPTION 'Run must reference its own closed session checkpoint'; END IF;
 IF NOT EXISTS(SELECT 1 FROM config_measuredsolution s
     JOIN config_catalogrevision r ON r.item_id=s.item_id
     WHERE s.item_id=NEW.solution_id AND r.id=NEW.solution_revision_id)
 THEN RAISE EXCEPTION 'Run solution revision mismatch'; END IF;
 IF NEW.outcome NOT IN ('accepted','failed')
 THEN RAISE EXCEPTION 'Invalid controlled run outcome'; END IF;
 RETURN NEW;
END $b$;
CREATE TRIGGER valid_benchmark_run BEFORE INSERT ON config_benchmarkrun
 FOR EACH ROW EXECUTE FUNCTION ai_compass_check_benchmark_run();

CREATE FUNCTION ai_compass_check_run_evidence() RETURNS trigger LANGUAGE plpgsql AS $b$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM config_benchmarkrun r
  JOIN config_benchmarksession s ON s.id=r.session_id
  JOIN config_campaignsnapshot cs ON cs.revision_id=s.campaign_snapshot_id
  JOIN config_campaigncasepin cp ON cp.id=s.case_pin_id
  JOIN config_evidencelink l ON l.id=NEW.evidence_id
  WHERE r.id=NEW.run_id AND (l.item_id=cs.revision_id AND FALSE))
 THEN
  IF NOT EXISTS(SELECT 1 FROM config_benchmarkrun r
    JOIN config_benchmarksession s ON s.id=r.session_id
    JOIN config_campaignsnapshot cs ON cs.revision_id=s.campaign_snapshot_id
    JOIN config_catalogrevision cr ON cr.id=cs.revision_id
    JOIN config_campaigncasepin cp ON cp.id=s.case_pin_id
    JOIN config_evidencelink l ON l.id=NEW.evidence_id
    WHERE r.id=NEW.run_id AND (l.item_id=cr.item_id OR l.item_id=cp.test_case_id))
  THEN RAISE EXCEPTION 'Run evidence not attached to pinned campaign or Test Case'; END IF;
 END IF;
 RETURN NEW;
END $b$;
CREATE TRIGGER valid_benchmark_run_evidence BEFORE INSERT ON config_benchmarkrunevidence
 FOR EACH ROW EXECUTE FUNCTION ai_compass_check_run_evidence();

CREATE TRIGGER immutable_session_solution_pin BEFORE UPDATE OR DELETE ON config_sessionsolutionpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_measured_solution BEFORE UPDATE OR DELETE ON config_measuredsolution
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_benchmark_run BEFORE UPDATE OR DELETE ON config_benchmarkrun
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_benchmark_run_evidence BEFORE UPDATE OR DELETE ON config_benchmarkrunevidence
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""
GUARDS=GUARDS.replace(""" IF NOT EXISTS(SELECT 1 FROM config_benchmarkrun r
  JOIN config_benchmarksession s ON s.id=r.session_id
  JOIN config_campaignsnapshot cs ON cs.revision_id=s.campaign_snapshot_id
  JOIN config_campaigncasepin cp ON cp.id=s.case_pin_id
  JOIN config_evidencelink l ON l.id=NEW.evidence_id
  WHERE r.id=NEW.run_id AND (l.item_id=cs.revision_id AND FALSE))
 THEN
  IF NOT EXISTS(""",""" IF NOT EXISTS(""").replace("""  THEN RAISE EXCEPTION 'Run evidence not attached to pinned campaign or Test Case'; END IF;
 END IF;""",""" THEN RAISE EXCEPTION 'Run evidence not attached to pinned campaign or Test Case'; END IF;""")
UNDO="""
DROP TRIGGER IF EXISTS immutable_benchmark_run_evidence ON config_benchmarkrunevidence;
DROP TRIGGER IF EXISTS immutable_benchmark_run ON config_benchmarkrun;
DROP TRIGGER IF EXISTS immutable_measured_solution ON config_measuredsolution;
DROP TRIGGER IF EXISTS immutable_session_solution_pin ON config_sessionsolutionpin;
DROP TRIGGER IF EXISTS valid_benchmark_run_evidence ON config_benchmarkrunevidence;
DROP FUNCTION IF EXISTS ai_compass_check_run_evidence();
DROP TRIGGER IF EXISTS valid_benchmark_run ON config_benchmarkrun;
DROP FUNCTION IF EXISTS ai_compass_check_benchmark_run();
DROP TRIGGER IF EXISTS valid_measured_solution ON config_measuredsolution;
DROP FUNCTION IF EXISTS ai_compass_check_measured_solution();
DROP TRIGGER IF EXISTS valid_session_solution_pin ON config_sessionsolutionpin;
DROP FUNCTION IF EXISTS ai_compass_check_session_solution_pin();
"""

class Migration(migrations.Migration):
    dependencies=[("config","0013_benchmark_sessions"),
                  migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.RunPython(register,reverse_code=migrations.RunPython.noop),
        migrations.CreateModel(name="SessionSolutionPin",fields=[
            ("session",models.OneToOneField(primary_key=True,serialize=False,
                on_delete=django.db.models.deletion.PROTECT,related_name="individual_setup",to="config.benchmarksession")),
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
            ("configuration_version",models.CharField(default="1",max_length=160)),
            ("settings",models.JSONField(default=dict)),
            ("properties",models.JSONField(default=dict)),
        ]),
        migrations.CreateModel(name="MeasuredSolution",fields=[
            ("item",models.OneToOneField(primary_key=True,serialize=False,
                on_delete=django.db.models.deletion.PROTECT,related_name="measured_solution",to="config.catalogitem")),
            ("fingerprint",models.CharField(max_length=64,unique=True)),
        ]),
        migrations.CreateModel(name="BenchmarkRun",fields=[
            ("id",models.UUIDField(primary_key=True,default=uuid7,editable=False,serialize=False)),
            ("public_id",models.CharField(max_length=120,unique=True)),
            ("outcome",models.CharField(max_length=12)),
            ("metrics",models.JSONField(default=dict)),
            ("result",models.JSONField(default=dict)),
            ("provenance",models.JSONField(default=dict)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("session",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                related_name="individual_run",to="config.benchmarksession")),
            ("closing_checkpoint",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                related_name="individual_run",to="config.sessioncheckpoint")),
            ("solution",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="runs",to="config.measuredsolution")),
            ("solution_revision",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.catalogrevision")),
            ("recorded_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="benchmark_runs",to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="BenchmarkRunEvidence",fields=[
            ("id",models.BigAutoField(primary_key=True,serialize=False)),
            ("run",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="evidence_pins",to="config.benchmarkrun")),
            ("evidence",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="benchmark_run_pins",to="config.evidencelink")),
        ],options={"constraints":[models.UniqueConstraint(fields=("run","evidence"),name="uniq_benchmark_run_evidence")]}),
        migrations.RunSQL(GUARDS,reverse_sql=UNDO),
    ]
