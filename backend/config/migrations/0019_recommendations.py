"""PLAT-22: additive, versioned recommendations pinned to exact evaluation and runs."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations,models

SCHEMA={
 "$schema":"https://json-schema.org/draft/2020-12/schema",
 "type":"object",
 "properties":{
  "state":{"type":"string","enum":["draft","in_review","published","unpublished"]},
  "decision":{"type":"string","enum":["recommended","conditional","not_recommended"]},
  "rationale":{"type":"string","minLength":1,"maxLength":16000},
  "limitations":{"type":"string","maxLength":10000},
  "review_note":{"type":"string","maxLength":10000},
  "publication_note":{"type":"string","maxLength":10000},
  "evidence_class":{"const":"recommendation"},
 },"required":["state","decision","rationale","limitations","evidence_class"],
 "additionalProperties":True,
}
GUARDS="""
CREATE FUNCTION ai_compass_recommendation_check() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM config_catalogrevision r
   JOIN config_catalogitem i ON i.id=r.item_id
   WHERE r.id=NEW.revision_id AND i.type_slug='recommendation')
 THEN RAISE EXCEPTION 'Invalid recommendation revision'; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM config_tasknode t
   JOIN config_catalogrevision r ON r.item_id=t.item_id
   WHERE t.item_id=NEW.task_id AND r.id=NEW.task_revision_id)
 THEN RAISE EXCEPTION 'Recommendation task pin mismatch'; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM config_measuredsolution s
   JOIN config_catalogrevision r ON r.item_id=s.item_id
   WHERE s.item_id=NEW.solution_id AND r.id=NEW.solution_revision_id)
 THEN RAISE EXCEPTION 'Recommendation Solution revision mismatch'; END IF;
 IF NEW.evaluation_id IS NOT NULL AND NOT EXISTS (
   SELECT 1 FROM config_evaluationsnapshot s
   JOIN config_catalogrevision r ON r.id=s.revision_id
   JOIN config_catalogitem i ON i.id=r.item_id
   WHERE s.revision_id=NEW.evaluation_id AND i.type_slug='evaluation')
 THEN RAISE EXCEPTION 'Recommendation Evaluation revision mismatch'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_recommendation_snapshot BEFORE INSERT ON config_recommendationsnapshot
 FOR EACH ROW EXECUTE FUNCTION ai_compass_recommendation_check();

CREATE FUNCTION ai_compass_recommendation_run_check() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM config_recommendationsnapshot s
   JOIN config_benchmarkrun r ON r.id=NEW.run_id
   JOIN config_benchmarksession ses ON ses.id=r.session_id
   JOIN config_campaigncasepin cp ON cp.id=ses.case_pin_id
   JOIN config_testcase tc ON tc.item_id=cp.test_case_id
   WHERE s.revision_id=NEW.snapshot_id AND r.solution_id=s.solution_id
   AND tc.task_id=s.task_id)
 THEN RAISE EXCEPTION 'Recommendation Run must match pinned Task and individual Solution'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_recommendation_run BEFORE INSERT ON config_recommendationrunpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_recommendation_run_check();

CREATE TRIGGER immutable_recommendation_snapshot BEFORE UPDATE OR DELETE
 ON config_recommendationsnapshot FOR EACH ROW
 EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_recommendation_run BEFORE UPDATE OR DELETE
 ON config_recommendationrunpin FOR EACH ROW
 EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""
UNDO="""
DROP TRIGGER IF EXISTS immutable_recommendation_run ON config_recommendationrunpin;
DROP TRIGGER IF EXISTS immutable_recommendation_snapshot ON config_recommendationsnapshot;
DROP TRIGGER IF EXISTS valid_recommendation_run ON config_recommendationrunpin;
DROP TRIGGER IF EXISTS valid_recommendation_snapshot ON config_recommendationsnapshot;
DROP FUNCTION IF EXISTS ai_compass_recommendation_run_check();
DROP FUNCTION IF EXISTS ai_compass_recommendation_check();
"""
def register(apps,editor):
    apps.get_model("config","ObjectTypeVersion").objects.using(editor.connection.alias).create(
        type_slug="recommendation",version=1,json_schema=SCHEMA)

protect=django.db.models.deletion.PROTECT

class Migration(migrations.Migration):
 dependencies=[("config","0018_versioned_evaluations"),
               migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
 operations=[
  migrations.RunPython(register,migrations.RunPython.noop),
  migrations.CreateModel(name="RecommendationSnapshot",fields=[
   ("revision",models.OneToOneField(to="config.catalogrevision",primary_key=True,
         serialize=False,related_name="recommendation_snapshot",on_delete=protect)),
   ("task",models.ForeignKey(to="config.tasknode",related_name="+",on_delete=protect)),
   ("task_revision",models.ForeignKey(to="config.catalogrevision",related_name="+",on_delete=protect)),
   ("solution",models.ForeignKey(to="config.measuredsolution",related_name="+",on_delete=protect)),
   ("solution_revision",models.ForeignKey(to="config.catalogrevision",related_name="+",on_delete=protect)),
   ("evaluation",models.ForeignKey(to="config.evaluationsnapshot",null=True,blank=True,
                                   related_name="recommendations",on_delete=protect)),
   ("reviewed_by",models.ForeignKey(to=settings.AUTH_USER_MODEL,null=True,blank=True,
                                   related_name="+",on_delete=protect)),
   ("reviewed_at",models.DateTimeField(null=True,blank=True)),
  ]),
  migrations.CreateModel(name="RecommendationRunPin",fields=[
   ("id",models.BigAutoField(primary_key=True,serialize=False)),
   ("snapshot",models.ForeignKey(to="config.recommendationsnapshot",
       related_name="run_pins",on_delete=protect)),
   ("run",models.ForeignKey(to="config.benchmarkrun",
       related_name="recommendation_pins",on_delete=protect)),
  ],options={"constraints":[models.UniqueConstraint(fields=("snapshot","run"),
       name="uniq_recommendation_run")]}),
  migrations.RunSQL(GUARDS,reverse_sql=UNDO),
 ]
