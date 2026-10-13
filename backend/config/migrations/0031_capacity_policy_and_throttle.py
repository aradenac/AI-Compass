"""FUT-20: bounded capacity policy, its audit trail and a durable login throttle.

Additive only. CapacityPolicyEvent is append-only (mutation rejected by trigger);
AccessThrottle is a mutable operational counter keyed by a one-way digest. No
pinned historical data is rewritten by a policy change.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids


class Migration(migrations.Migration):
    dependencies = [("config", "0030_archive_jobs_and_grants"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="CapacityPolicy", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("is_active", models.BooleanField(default=False)),
            ("version", models.PositiveIntegerField(default=1)),
            ("evidence_warn_bytes", models.PositiveBigIntegerField(default=8 * 1024 ** 3)),
            ("disk_warn_percent", models.PositiveIntegerField(default=80)),
            ("archive_concurrency_warn", models.PositiveIntegerField(default=4)),
            ("upload_quota_warn_bytes", models.PositiveBigIntegerField(default=2 * 1024 ** 3)),
            ("threshold_factors", models.JSONField(default=dict)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("updated_by", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
        ], options={"ordering": ["-version", "id"]}),
        migrations.CreateModel(name="CapacityPolicyEvent", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("action", models.CharField(max_length=32)),
            ("previous", models.JSONField(default=dict)),
            ("applied", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
        ], options={"ordering": ["created_at", "id"]}),
        migrations.CreateModel(name="AccessThrottle", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("key_digest", models.CharField(max_length=64, unique=True)),
            ("failures", models.PositiveIntegerField(default=0)),
            ("locked_until", models.DateTimeField(null=True, blank=True)),
            ("last_failure_at", models.DateTimeField(null=True, blank=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"ordering": ["updated_at", "id"]}),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_capacity_policy_event BEFORE UPDATE OR DELETE
              ON config_capacitypolicyevent FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
        """, reverse_sql="""
            DROP TRIGGER IF EXISTS immutable_capacity_policy_event ON config_capacitypolicyevent;
        """),
    ]
