"""PLAT-21: append-only interpretive evaluations and exact measured Run FK inputs.

No forecast or observed run is altered. No automatic score computation.
"""
import django.db.models.deletion
from django.db import migrations,models

SCHEMA={
 "$schema":"https://json-schema.org/draft/2020-12/schema",
 "type":"object",
 "properties":{
  "assessment":{"type":"string","enum":["supported","unsupported","inconclusive"]},
  "notes":{"type":"string","maxLength":20000},
  "limitations":{"type":"string","maxLength":10000},
  "comparability":{"type":"string","enum":["comparable","mixed_methods","incomplete_metrics","mixed_methods_and_incomplete_metrics"]},
  "missing_fields":{"type":"array","items":{"type":"string"}},
  "evidence_class":{"const":"interpretation"},
 },"required":["assessment","notes","comparability","missing_fields","evidence_class"],
 "additionalProperties":True,
}
METHOD={
 "kind":"descriptive_comparison",
 "version":1,
 "aggregation":"none",
 "description":"Record stated evaluation and exact original Run metrics; do not calculate novel weighted scores",
 "supported_metrics":["quality_score","information_utility_score","cost_eur",
                      "tokens_total","human_total_minutes","interaction_agent_minutes"],
}
GUARDS="""
CREATE FUNCTION ai_compass_validate_evaluation_snapshot() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM config_catalogrevision r JOIN config_catalogitem i ON i.id=r.item_id
   WHERE r.id=NEW.revision_id AND i.type_slug='evaluation') OR
   NOT EXISTS (
   SELECT 1 FROM config_objecttypeversion v WHERE v.id=NEW.scoring_method_id
     AND v.type_slug='evaluation_scoring_method' AND v.version=1)
 THEN RAISE EXCEPTION 'Invalid evaluation revision or scoring protocol'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_evaluation_snapshot BEFORE INSERT ON config_evaluationsnapshot
 FOR EACH ROW EXECUTE FUNCTION ai_compass_validate_evaluation_snapshot();

CREATE FUNCTION ai_compass_validate_evaluation_pin() RETURNS trigger
LANGUAGE plpgsql AS $body$
BEGIN
 IF TG_TABLE_NAME='config_evaluationindividualrunpin' THEN
   IF NOT EXISTS (SELECT 1 FROM config_benchmarkrun r JOIN config_benchmarksession s ON s.id=r.session_id
     WHERE r.id=NEW.run_id AND s.method_definition_id=NEW.method_definition_id)
     THEN RAISE EXCEPTION 'Individual Run experimental method does not match'; END IF;
 ELSIF TG_TABLE_NAME='config_evaluationcompositerunpin' THEN
   IF NOT EXISTS (SELECT 1 FROM config_compositebenchmarkrun r JOIN config_benchmarksession s ON s.id=r.session_id
     WHERE r.id=NEW.run_id AND s.method_definition_id=NEW.method_definition_id)
     THEN RAISE EXCEPTION 'Composite Run experimental method does not match'; END IF;
 END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_evaluation_individual_pin BEFORE INSERT ON config_evaluationindividualrunpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_validate_evaluation_pin();
CREATE TRIGGER valid_evaluation_composite_pin BEFORE INSERT ON config_evaluationcompositerunpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_validate_evaluation_pin();

CREATE TRIGGER immutable_evaluation_snapshot BEFORE UPDATE OR DELETE ON config_evaluationsnapshot
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_evaluation_individual_pin BEFORE UPDATE OR DELETE ON config_evaluationindividualrunpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_evaluation_composite_pin BEFORE UPDATE OR DELETE ON config_evaluationcompositerunpin
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""
UNDO="""
DROP TRIGGER IF EXISTS immutable_evaluation_composite_pin ON config_evaluationcompositerunpin;
DROP TRIGGER IF EXISTS immutable_evaluation_individual_pin ON config_evaluationindividualrunpin;
DROP TRIGGER IF EXISTS immutable_evaluation_snapshot ON config_evaluationsnapshot;
DROP TRIGGER IF EXISTS valid_evaluation_composite_pin ON config_evaluationcompositerunpin;
DROP TRIGGER IF EXISTS valid_evaluation_individual_pin ON config_evaluationindividualrunpin;
DROP FUNCTION IF EXISTS ai_compass_validate_evaluation_pin();
DROP TRIGGER IF EXISTS valid_evaluation_snapshot ON config_evaluationsnapshot;
DROP FUNCTION IF EXISTS ai_compass_validate_evaluation_snapshot();
"""
def register(apps,editor):
    cls=apps.get_model("config","ObjectTypeVersion")
    cls.objects.using(editor.connection.alias).create(type_slug="evaluation",version=1,json_schema=SCHEMA)
    cls.objects.using(editor.connection.alias).create(type_slug="evaluation_scoring_method",version=1,
                                                     json_schema=METHOD)

protect=django.db.models.deletion.PROTECT

class Migration(migrations.Migration):
 dependencies=[("config","0017_theoretical_forecasts")]
 operations=[
  migrations.RunPython(register,migrations.RunPython.noop),
  migrations.CreateModel(name="EvaluationSnapshot",fields=[
    ("revision",models.OneToOneField(primary_key=True,serialize=False,
       to="config.catalogrevision",related_name="evaluation_snapshot",on_delete=protect)),
    ("scoring_method",models.ForeignKey(to="config.objecttypeversion",
       related_name="evaluation_snapshots",on_delete=protect)),
    ("scoring_config",models.JSONField(default=dict)),
  ]),
  migrations.CreateModel(name="EvaluationIndividualRunPin",fields=[
    ("id",models.BigAutoField(primary_key=True,serialize=False)),
    ("position",models.PositiveIntegerField()),
    ("input_context",models.JSONField(default=dict)),
    ("snapshot",models.ForeignKey(to="config.evaluationsnapshot",
       related_name="individual_pins",on_delete=protect)),
    ("run",models.ForeignKey(to="config.benchmarkrun",related_name="evaluation_pins",
       on_delete=protect)),
    ("method_definition",models.ForeignKey(to="config.objecttypeversion",related_name="+",
       on_delete=protect)),
  ],options={"constraints":[
    models.UniqueConstraint(fields=("snapshot","run"),name="uniq_evaluation_individual_run"),
    models.UniqueConstraint(fields=("snapshot","position"),name="uniq_evaluation_individual_order")]}),
  migrations.CreateModel(name="EvaluationCompositeRunPin",fields=[
    ("id",models.BigAutoField(primary_key=True,serialize=False)),
    ("position",models.PositiveIntegerField()),
    ("input_context",models.JSONField(default=dict)),
    ("snapshot",models.ForeignKey(to="config.evaluationsnapshot",
       related_name="composite_pins",on_delete=protect)),
    ("run",models.ForeignKey(to="config.compositebenchmarkrun",related_name="evaluation_pins",
       on_delete=protect)),
    ("method_definition",models.ForeignKey(to="config.objecttypeversion",related_name="+",
       on_delete=protect)),
  ],options={"constraints":[
    models.UniqueConstraint(fields=("snapshot","run"),name="uniq_evaluation_composite_run"),
    models.UniqueConstraint(fields=("snapshot","position"),name="uniq_evaluation_composite_order")]}),
  migrations.RunSQL(GUARDS,reverse_sql=UNDO),
 ]
