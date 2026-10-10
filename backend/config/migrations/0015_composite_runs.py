"""PLAT-16: additive immutable composite Framework run tables and reference guards."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from config.catalog_ids import uuid7

GUARDS="""
CREATE FUNCTION ai_compass_composite_run_insert() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  IF NEW.outcome NOT IN ('accepted', 'failed') THEN
    RAISE EXCEPTION 'Composite outcome must be accepted or failed'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM config_benchmarksession s
    JOIN config_campaignsnapshot cs ON cs.revision_id=s.campaign_snapshot_id
    JOIN config_catalogitem f ON f.id=cs.framework_id AND f.type_slug='framework'
    JOIN config_catalogrevision fr ON fr.id=cs.framework_revision_id AND fr.item_id=f.id
    JOIN config_sessioncheckpoint c ON c.id=NEW.closing_checkpoint_id
    WHERE s.id=NEW.session_id AND c.session_id=s.id
      AND c.action='closed' AND c.state->>'status'='closed'
      AND NEW.framework_id=f.id AND NEW.framework_revision_id=fr.id
      AND jsonb_typeof(s.selected_participants)='array'
      AND jsonb_array_length(s.selected_participants)>=2
  ) THEN RAISE EXCEPTION 'Composite run must close a multi-participant Framework session with exact revision'; END IF;
  IF EXISTS (SELECT 1 FROM config_benchmarkrun i WHERE i.session_id=NEW.session_id) THEN
    RAISE EXCEPTION 'Session already has an individual run'; END IF;
  RETURN NEW;
END $body$;
CREATE TRIGGER valid_composite_run BEFORE INSERT ON config_compositebenchmarkrun
  FOR EACH ROW EXECUTE FUNCTION ai_compass_composite_run_insert();

CREATE FUNCTION ai_compass_composite_member_insert() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM config_compositebenchmarkrun r
   JOIN config_benchmarksession s ON s.id=r.session_id
   JOIN config_campaignparticipantpin p ON p.id=NEW.participant_pin_id
   JOIN config_campaignparticipantidentity pi ON pi.id=p.participant_id
   WHERE r.id=NEW.run_id AND p.snapshot_id=s.campaign_snapshot_id
      AND s.selected_participants ? pi.public_id
 ) THEN RAISE EXCEPTION 'Participant must be selected in this exact campaign revision'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_composite_member BEFORE INSERT ON config_compositerunparticipant
  FOR EACH ROW EXECUTE FUNCTION ai_compass_composite_member_insert();

CREATE FUNCTION ai_compass_composite_members_complete() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE required_count integer;
DECLARE actual_count integer;
BEGIN
 SELECT jsonb_array_length(s.selected_participants) INTO required_count
 FROM config_compositebenchmarkrun r JOIN config_benchmarksession s ON s.id=r.session_id
 WHERE r.id=NEW.id;
 SELECT COUNT(*) INTO actual_count FROM config_compositerunparticipant WHERE run_id=NEW.id;
 IF actual_count IS DISTINCT FROM required_count THEN
   RAISE EXCEPTION 'Composite run must pin every selected participant exactly once'; END IF;
 RETURN NEW;
END $body$;
CREATE CONSTRAINT TRIGGER complete_composite_members AFTER INSERT ON config_compositebenchmarkrun
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
  EXECUTE FUNCTION ai_compass_composite_members_complete();

CREATE FUNCTION ai_compass_composite_evidence_insert() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM config_compositebenchmarkrun r
   JOIN config_benchmarksession s ON s.id=r.session_id
   JOIN config_campaignsnapshot cs ON cs.revision_id=s.campaign_snapshot_id
   JOIN config_catalogrevision cr ON cr.id=cs.revision_id
   JOIN config_campaigncasepin cp ON cp.id=s.case_pin_id
   JOIN config_evidencelink l ON l.id=NEW.evidence_id
   WHERE r.id=NEW.run_id
     AND (l.item_id=cr.item_id OR l.item_id=cp.test_case_id)
 ) THEN RAISE EXCEPTION 'Composite evidence must refer to original campaign or Test Case'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_composite_evidence BEFORE INSERT ON config_compositerunevidence
  FOR EACH ROW EXECUTE FUNCTION ai_compass_composite_evidence_insert();

CREATE TRIGGER immutable_composite_run BEFORE UPDATE OR DELETE ON config_compositebenchmarkrun
  FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_composite_member BEFORE UPDATE OR DELETE ON config_compositerunparticipant
  FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_composite_evidence BEFORE UPDATE OR DELETE ON config_compositerunevidence
  FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""

UNDO="""
DROP TRIGGER IF EXISTS immutable_composite_evidence ON config_compositerunevidence;
DROP TRIGGER IF EXISTS immutable_composite_member ON config_compositerunparticipant;
DROP TRIGGER IF EXISTS immutable_composite_run ON config_compositebenchmarkrun;
DROP TRIGGER IF EXISTS valid_composite_evidence ON config_compositerunevidence;
DROP FUNCTION IF EXISTS ai_compass_composite_evidence_insert();
DROP TRIGGER IF EXISTS complete_composite_members ON config_compositebenchmarkrun;
DROP FUNCTION IF EXISTS ai_compass_composite_members_complete();
DROP TRIGGER IF EXISTS valid_composite_member ON config_compositerunparticipant;
DROP FUNCTION IF EXISTS ai_compass_composite_member_insert();
DROP TRIGGER IF EXISTS valid_composite_run ON config_compositebenchmarkrun;
DROP FUNCTION IF EXISTS ai_compass_composite_run_insert();
"""

class Migration(migrations.Migration):
    dependencies=[("config","0014_individual_benchmark_runs"),
                  migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="CompositeBenchmarkRun",fields=[
            ("id",models.UUIDField(primary_key=True,default=uuid7,editable=False,serialize=False)),
            ("public_id",models.CharField(max_length=120,unique=True)),
            ("outcome",models.CharField(max_length=12)),
            ("metrics",models.JSONField(default=dict)),
            ("result",models.JSONField(default=dict)),
            ("provenance",models.JSONField(default=dict)),
            ("participant_snapshots",models.JSONField(default=list)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("session",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                related_name="composite_run",to="config.benchmarksession")),
            ("closing_checkpoint",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                related_name="composite_run",to="config.sessioncheckpoint")),
            ("framework",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.catalogitem")),
            ("framework_revision",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="+",to="config.catalogrevision")),
            ("recorded_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="composite_benchmark_runs",to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="CompositeRunParticipant",fields=[
            ("id",models.BigAutoField(primary_key=True,serialize=False)),
            ("position",models.PositiveIntegerField()),
            ("run",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="participant_pins",to="config.compositebenchmarkrun")),
            ("participant_pin",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="composite_run_memberships",to="config.campaignparticipantpin")),
        ],options={"ordering":["position"],"constraints":[
            models.UniqueConstraint(fields=("run","participant_pin"),name="uniq_composite_run_member"),
            models.UniqueConstraint(fields=("run","position"),name="uniq_composite_run_position"),
        ]}),
        migrations.CreateModel(name="CompositeRunEvidence",fields=[
            ("id",models.BigAutoField(primary_key=True,serialize=False)),
            ("run",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="evidence_pins",to="config.compositebenchmarkrun")),
            ("evidence",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="composite_run_pins",to="config.evidencelink")),
        ],options={"constraints":[
            models.UniqueConstraint(fields=("run","evidence"),name="uniq_composite_run_evidence"),
        ]}),
        migrations.RunSQL(GUARDS,reverse_sql=UNDO),
    ]
