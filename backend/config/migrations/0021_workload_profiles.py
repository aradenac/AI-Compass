"""DAP-01: additive, empty workload planning with protected historical versions."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import config.catalog_ids


PROTECT_HISTORY = """
CREATE TRIGGER workload_revision_immutable
BEFORE UPDATE OR DELETE ON config_workloadrevision FOR EACH ROW
EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER workload_allocation_immutable
BEFORE UPDATE OR DELETE ON config_workloadallocation FOR EACH ROW
EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""

UNPROTECT_HISTORY = """
DROP TRIGGER IF EXISTS workload_allocation_immutable ON config_workloadallocation;
DROP TRIGGER IF EXISTS workload_revision_immutable ON config_workloadrevision;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("config", "0020_feedback_discussions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="WorkloadProfile",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=config.catalog_ids.uuid7,
                                        editable=False, serialize=False)),
                ("public_id", models.CharField(max_length=120, unique=True)),
                ("kind", models.CharField(max_length=16, choices=[
                    ("role", "Job Role"), ("specialty", "Specialty"),
                    ("person", "Person"), ("cohort", "Planning Cohort")])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["kind", "public_id"]},
        ),
        migrations.CreateModel(
            name="WorkloadRevision",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=config.catalog_ids.uuid7,
                                        editable=False, serialize=False)),
                ("number", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=160)),
                ("headcount", models.PositiveIntegerField(default=1)),
                ("hourly_rate_eur", models.DecimalField(max_digits=10, decimal_places=2,
                                                        null=True, blank=True)),
                ("notes", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("profile", models.ForeignKey(to="config.workloadprofile", related_name="revisions",
                                              on_delete=django.db.models.deletion.PROTECT)),
                ("role", models.ForeignKey(to="config.workloadprofile", null=True, blank=True,
                                           related_name="role_dependents",
                                           on_delete=django.db.models.deletion.PROTECT)),
                ("specialty", models.ForeignKey(to="config.workloadprofile", null=True, blank=True,
                                                related_name="specialty_dependents",
                                                on_delete=django.db.models.deletion.PROTECT)),
                ("linked_user", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                                                  related_name="workload_revisions",
                                                  on_delete=django.db.models.deletion.PROTECT)),
                ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                                                 related_name="authored_workload_revisions",
                                                 on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={"ordering": ["profile", "number"]},
        ),
        migrations.CreateModel(
            name="WorkloadAllocation",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=config.catalog_ids.uuid7,
                                        editable=False, serialize=False)),
                ("annual_occurrences", models.DecimalField(max_digits=12, decimal_places=2,
                                                             null=True, blank=True)),
                ("baseline_human_hours", models.DecimalField(max_digits=8, decimal_places=2,
                                                               null=True, blank=True)),
                ("excluded", models.BooleanField(default=False)),
                ("revision", models.ForeignKey(to="config.workloadrevision", related_name="allocations",
                                               on_delete=django.db.models.deletion.PROTECT)),
                ("task", models.ForeignKey(to="config.tasknode", related_name="workload_allocations",
                                           on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={"ordering": ["task__item__public_id"]},
        ),
        migrations.AddConstraint(
            model_name="workloadrevision",
            constraint=models.UniqueConstraint(fields=["profile", "number"],
                                               name="uniq_workload_revision_number"),
        ),
        migrations.AddConstraint(
            model_name="workloadallocation",
            constraint=models.UniqueConstraint(fields=["revision", "task"],
                                               name="uniq_workload_revision_task"),
        ),
        migrations.RunSQL(PROTECT_HISTORY, reverse_sql=UNPROTECT_HISTORY),
    ]
