"""PLAT-14: additive immutable session drafts, method pins and checkpoint evidence."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from config.catalog_ids import uuid7

GUARDS = """
CREATE FUNCTION ai_compass_check_session() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM config_campaigncasepin cp
    WHERE cp.id=NEW.case_pin_id AND cp.snapshot_id=NEW.campaign_snapshot_id
  ) THEN RAISE EXCEPTION 'Session Test Case must belong to frozen campaign revision'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM config_campaignsnapshot cs
    WHERE cs.revision_id=NEW.campaign_snapshot_id AND cs.method_definition_id=NEW.method_definition_id
  ) THEN RAISE EXCEPTION 'Session experimental method must match pinned campaign'; END IF;
  IF (NEW.guide_id IS NULL) <> (NEW.guide_revision_id IS NULL) THEN
    RAISE EXCEPTION 'Session guide identity and revision are inseparable'; END IF;
  IF NEW.guide_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i ON i.id=r.item_id
    WHERE r.id=NEW.guide_revision_id AND i.id=NEW.guide_id AND i.type_slug='setup_guide'
  ) THEN RAISE EXCEPTION 'Session guide revision mismatch'; END IF;
  RETURN NEW;
END $body$;
CREATE TRIGGER benchmark_session_reference_guard BEFORE INSERT ON config_benchmarksession
FOR EACH ROW EXECUTE FUNCTION ai_compass_check_session();

CREATE FUNCTION ai_compass_check_session_evidence() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM config_sessioncheckpoint cp
    JOIN config_benchmarksession s ON s.id=cp.session_id
    JOIN config_campaignsnapshot cs ON cs.revision_id=s.campaign_snapshot_id
    JOIN config_catalogrevision cr ON cr.id=cs.revision_id
    JOIN config_campaigncasepin tc ON tc.id=s.case_pin_id
    JOIN config_evidencelink l ON l.id=NEW.evidence_id
    WHERE cp.id=NEW.checkpoint_id AND
      (l.item_id=cr.item_id OR l.item_id=tc.test_case_id)
  ) THEN RAISE EXCEPTION 'Session evidence must be attached to the campaign or Test Case'; END IF;
  RETURN NEW;
END $body$;
CREATE TRIGGER benchmark_session_evidence_guard BEFORE INSERT ON config_sessioncheckpointevidence
FOR EACH ROW EXECUTE FUNCTION ai_compass_check_session_evidence();

CREATE TRIGGER immutable_benchmark_session BEFORE UPDATE OR DELETE
ON config_benchmarksession FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_session_checkpoint BEFORE UPDATE OR DELETE
ON config_sessioncheckpoint FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_session_checkpoint_evidence BEFORE UPDATE OR DELETE
ON config_sessioncheckpointevidence FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""

UNDO = """
DROP TRIGGER IF EXISTS immutable_session_checkpoint_evidence ON config_sessioncheckpointevidence;
DROP TRIGGER IF EXISTS immutable_session_checkpoint ON config_sessioncheckpoint;
DROP TRIGGER IF EXISTS immutable_benchmark_session ON config_benchmarksession;
DROP TRIGGER IF EXISTS benchmark_session_evidence_guard ON config_sessioncheckpointevidence;
DROP FUNCTION IF EXISTS ai_compass_check_session_evidence();
DROP TRIGGER IF EXISTS benchmark_session_reference_guard ON config_benchmarksession;
DROP FUNCTION IF EXISTS ai_compass_check_session();
"""

class Migration(migrations.Migration):
    dependencies = [("config", "0012_framework_participants"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="BenchmarkSession",fields=[
            ("id", models.UUIDField(primary_key=True,default=uuid7,editable=False,serialize=False)),
            ("public_id", models.CharField(max_length=120,unique=True)),
            ("method_descriptor",models.JSONField(default=dict)),
            ("selected_participants",models.JSONField(default=list)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("campaign_snapshot",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="benchmark_sessions",to="config.campaignsnapshot")),
            ("case_pin",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="benchmark_sessions",to="config.campaigncasepin")),
            ("guide",models.ForeignKey(null=True,blank=True,on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.catalogitem")),
            ("guide_revision",models.ForeignKey(null=True,blank=True,on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.catalogrevision")),
            ("method_definition",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="benchmark_sessions",to="config.objecttypeversion")),
            ("created_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="benchmark_sessions",to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="SessionCheckpoint",fields=[
            ("id",models.UUIDField(primary_key=True,default=uuid7,editable=False,serialize=False)),
            ("number",models.PositiveIntegerField()),
            ("action",models.CharField(max_length=32)),
            ("state",models.JSONField(default=dict)),
            ("saved_at",models.DateTimeField(auto_now_add=True)),
            ("actor",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to=settings.AUTH_USER_MODEL)),
            ("session",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="checkpoints",to="config.benchmarksession")),
        ],options={"ordering":["number"],"constraints":[models.UniqueConstraint(
            fields=("session","number"),name="uniq_session_checkpoint")]}),
        migrations.CreateModel(name="SessionCheckpointEvidence",fields=[
            ("id",models.BigAutoField(primary_key=True,serialize=False)),
            ("checkpoint",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="evidence_pins",to="config.sessioncheckpoint")),
            ("evidence",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="session_checkpoint_pins",to="config.evidencelink")),
        ],options={"constraints":[models.UniqueConstraint(
            fields=("checkpoint","evidence"),name="uniq_session_checkpoint_evidence")]}),
        migrations.RunSQL(GUARDS,reverse_sql=UNDO),
    ]
