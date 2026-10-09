"""PLAT-27: additive maintenance issue projection and immutable decisions."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import config.catalog_ids

class Migration(migrations.Migration):
    dependencies = [
        ("config", "0007_production_migration_receipt"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="DataHealthIssue",
            fields=[
                ("id", models.UUIDField(default=config.catalog_ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ("public_id", models.CharField(max_length=120, unique=True)),
                ("dedupe_key", models.CharField(max_length=64, unique=True)),
                ("category", models.CharField(max_length=48)),
                ("severity", models.CharField(max_length=16)),
                ("subject_type", models.CharField(max_length=32)),
                ("subject_ref", models.CharField(max_length=120)),
                ("summary", models.CharField(max_length=240)),
                ("status", models.CharField(max_length=16, default="open")),
                ("exception_rationale", models.TextField(blank=True)),
                ("review_after", models.DateField(blank=True, null=True)),
                ("first_detected_at", models.DateTimeField(auto_now_add=True)),
                ("last_detected_at", models.DateTimeField(auto_now_add=True)),
                ("last_scan_id", models.UUIDField(blank=True, null=True)),
                ("detection_count", models.PositiveIntegerField(default=1)),
                ("check_version", models.CharField(max_length=48, default="data-health@1")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                       related_name="data_health_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-last_detected_at","public_id"]},
        ),
        migrations.CreateModel(
            name="DataHealthEvent",
            fields=[
                ("id", models.UUIDField(default=config.catalog_ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=32)),
                ("detail", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("issue", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="config.datahealthissue")),
            ],
            options={"ordering":["created_at","id"]},
        ),
        migrations.RunSQL(
            "CREATE TRIGGER immutable_data_health_event BEFORE UPDATE OR DELETE "
            "ON config_datahealthevent FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();",
            reverse_sql="DROP TRIGGER IF EXISTS immutable_data_health_event ON config_datahealthevent;",
        ),
    ]
