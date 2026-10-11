"""FUT-16: safe additive, append-only resource planning; no commerce/IAM writes."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids


class Migration(migrations.Migration):
    dependencies = [("config", "0027_deployment_targets"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="BudgetPlan", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("public_id", models.CharField(max_length=120, unique=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("profile", models.ForeignKey(to="config.workloadprofile",
                on_delete=django.db.models.deletion.PROTECT, related_name="resource_budgets")),
            ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_resource_budgets")),
        ]),
        migrations.CreateModel(name="BudgetRevision", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("number", models.PositiveIntegerField()),
            ("algorithm", models.CharField(max_length=48, default="dap-resource-v1")),
            ("assumptions", models.JSONField(default=dict)),
            ("projection", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("budget", models.ForeignKey(to="config.budgetplan",
                on_delete=django.db.models.deletion.PROTECT, related_name="revisions")),
            ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="resource_budget_revisions")),
        ], options={"ordering": ["budget", "number"]}),
        migrations.AddConstraint("budgetrevision", models.UniqueConstraint(
            fields=["budget", "number"], name="uniq_resource_budget_revision")),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_budget_plan BEFORE UPDATE OR DELETE
              ON config_budgetplan FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_budget_revision BEFORE UPDATE OR DELETE
              ON config_budgetrevision FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
        """, reverse_sql="""
            DROP TRIGGER IF EXISTS immutable_budget_revision ON config_budgetrevision;
            DROP TRIGGER IF EXISTS immutable_budget_plan ON config_budgetplan;
        """),
    ]
