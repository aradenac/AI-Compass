"""FUT-13: additive immutable, rate-confidential opportunity scenarios."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids

class Migration(migrations.Migration):
    dependencies = [("config","0025_run_amendments"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="OpportunityScenario",fields=[
            ("id",models.UUIDField(primary_key=True,serialize=False,editable=False,
                                    default=config.catalog_ids.uuid7)),
            ("public_id",models.CharField(max_length=120,unique=True)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("profile",models.ForeignKey(to="config.workloadprofile",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="opportunity_scenarios")),
        ]),
        migrations.CreateModel(name="OpportunitySnapshot",fields=[
            ("id",models.UUIDField(primary_key=True,serialize=False,editable=False,
                                    default=config.catalog_ids.uuid7)),
            ("number",models.PositiveIntegerField()),
            ("algorithm",models.CharField(max_length=48,default="dap-opportunity-v1")),
            ("assumptions",models.JSONField(default=dict)),
            ("projection",models.JSONField(default=dict)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("created_by",models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="opportunity_snapshots")),
            ("scenario",models.ForeignKey(to="config.opportunityscenario",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="snapshots")),
        ],options={"ordering":["scenario","number"]}),
        migrations.AddConstraint("opportunitysnapshot",models.UniqueConstraint(
            fields=["scenario","number"],name="uniq_opportunity_scenario_revision")),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_opportunity_snapshot BEFORE UPDATE OR DELETE
              ON config_opportunitysnapshot FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_opportunity_scenario BEFORE UPDATE OR DELETE
              ON config_opportunityscenario FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
        """,reverse_sql="""
            DROP TRIGGER IF EXISTS immutable_opportunity_snapshot ON config_opportunitysnapshot;
            DROP TRIGGER IF EXISTS immutable_opportunity_scenario ON config_opportunityscenario;
        """),
    ]
