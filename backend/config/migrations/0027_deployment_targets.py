"""FUT-15: additive deployment targeting and immutable manual verification journal."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids


class Migration(migrations.Migration):
    dependencies = [("config", "0026_dap_opportunity"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="DeploymentTarget", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False,
                                    default=config.catalog_ids.uuid7, serialize=False)),
            ("public_id", models.CharField(max_length=120, unique=True)),
            ("kind", models.CharField(max_length=12, choices=[
                ("benchmark", "Benchmark"), ("forecast", "Forecast")])),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("population", models.ForeignKey(to="config.workloadprofile",
                on_delete=django.db.models.deletion.PROTECT, related_name="deployment_targets")),
            ("task", models.ForeignKey(to="config.tasknode",
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
            ("candidate", models.ForeignKey(to="config.catalogitem",
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
            ("origin", models.ForeignKey(to="config.opportunitysnapshot",
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="deployment_targets")),
            ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_deployment_targets")),
        ]),
        migrations.CreateModel(name="DeploymentRevision", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False,
                                    default=config.catalog_ids.uuid7, serialize=False)),
            ("number", models.PositiveIntegerField()),
            ("selection", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("target", models.ForeignKey(to="config.deploymenttarget",
                on_delete=django.db.models.deletion.PROTECT, related_name="revisions")),
            ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT, related_name="deployment_revisions")),
        ]),
        migrations.CreateModel(name="DeploymentEvent", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False,
                                    default=config.catalog_ids.uuid7, serialize=False)),
            ("seat_key", models.CharField(max_length=64)),
            ("action", models.CharField(max_length=24)),
            ("evidence_reference", models.CharField(max_length=300, blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("target", models.ForeignKey(to="config.deploymenttarget",
                on_delete=django.db.models.deletion.PROTECT, related_name="events")),
            ("target_revision", models.ForeignKey(to="config.deploymentrevision",
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
            ("beneficiary", models.ForeignKey(to="config.workloadprofile",
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="+")),
            ("component", models.ForeignKey(to="config.catalogitem",
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="+")),
            ("component_revision", models.ForeignKey(to="config.catalogrevision",
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="+")),
            ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT, related_name="deployment_events")),
        ], options={"ordering": ["created_at", "id"]}),
        migrations.AddConstraint("deploymenttarget", models.UniqueConstraint(
            fields=["population", "task", "candidate", "kind"],
            name="uniq_deployment_target_scope")),
        migrations.AddConstraint("deploymentrevision", models.UniqueConstraint(
            fields=["target", "number"], name="uniq_deployment_target_revision")),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_deployment_target BEFORE UPDATE OR DELETE
              ON config_deploymenttarget FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_deployment_revision BEFORE UPDATE OR DELETE
              ON config_deploymentrevision FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_deployment_event BEFORE UPDATE OR DELETE
              ON config_deploymentevent FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
        """, reverse_sql="""
            DROP TRIGGER IF EXISTS immutable_deployment_event ON config_deploymentevent;
            DROP TRIGGER IF EXISTS immutable_deployment_revision ON config_deploymentrevision;
            DROP TRIGGER IF EXISTS immutable_deployment_target ON config_deploymenttarget;
        """),
    ]
