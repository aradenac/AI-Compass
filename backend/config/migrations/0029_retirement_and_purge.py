"""FUT-18: logical retirement, orphan inventory, privileged purge and policy.

Additive only. Retirement/tombstone/receipt rows are append-only; the policy is
the single mutable administrative record (auditable through revisions).
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids


class Migration(migrations.Migration):
    dependencies = [("config", "0028_resource_budgets"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="RetirementRecord", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("public_id", models.CharField(max_length=120, unique=True)),
            ("action", models.CharField(max_length=16)),
            ("reason", models.CharField(max_length=600, blank=True)),
            ("retired_at", models.DateTimeField(auto_now_add=True)),
            ("item", models.OneToOneField(to="config.catalogitem",
                on_delete=django.db.models.deletion.PROTECT, related_name="retirement")),
            ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="retirement_records")),
        ], options={"ordering": ["retired_at", "id"]}),
        migrations.CreateModel(name="RetirementEvent", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("action", models.CharField(max_length=16)),
            ("reason", models.CharField(max_length=600, blank=True)),
            ("detail", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("item", models.ForeignKey(to="config.catalogitem",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="retirement_events")),
            ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
        ], options={"ordering": ["created_at", "id"]}),
        migrations.CreateModel(name="PurgePolicy", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("is_active", models.BooleanField(default=False)),
            ("enabled", models.BooleanField(default=False)),
            ("grace_days", models.PositiveIntegerField(default=30)),
            ("eligible_classes", models.JSONField(default=list)),
            ("cadence_hours", models.PositiveIntegerField(default=168)),
            ("version", models.PositiveIntegerField(default=1)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("updated_by", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
        ], options={"ordering": ["-version", "id"]}),
        migrations.CreateModel(name="PurgeCandidate", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("public_id", models.CharField(max_length=120, unique=True)),
            ("kind", models.CharField(max_length=24)),
            ("subject", models.CharField(max_length=140)),
            ("eligible_at", models.DateTimeField()),
            ("first_seen_at", models.DateTimeField(auto_now_add=True)),
            ("size_bytes", models.PositiveBigIntegerField(default=0)),
            ("blockers", models.JSONField(default=list)),
            ("preview", models.JSONField(default=dict)),
            ("state", models.CharField(max_length=16, default="candidate")),
        ], options={"ordering": ["first_seen_at", "id"]}),
        migrations.CreateModel(name="PurgeReceipt", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("public_id", models.CharField(max_length=120, unique=True)),
            ("job_key", models.CharField(max_length=64)),
            ("reclaimed_bytes", models.PositiveBigIntegerField(default=0)),
            ("purged_count", models.PositiveIntegerField(default=0)),
            ("blocked_count", models.PositiveIntegerField(default=0)),
            ("detail", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
        ], options={"ordering": ["created_at", "id"]}),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_retirement_event BEFORE UPDATE OR DELETE
              ON config_retirementevent FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_purge_receipt BEFORE UPDATE OR DELETE
              ON config_purgereceipt FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
        """, reverse_sql="""
            DROP TRIGGER IF EXISTS immutable_purge_receipt ON config_purgereceipt;
            DROP TRIGGER IF EXISTS immutable_retirement_event ON config_retirementevent;
        """),
        # FUT-18 privileged physical purge (spec 6.3.4): an unreferenced evidence
        # blob may be removed *only* under the transaction-local guard set by the
        # purge service. UPDATE stays forbidden everywhere; the exception is
        # DELETE-only, opt-in per transaction, and cannot be reached by any
        # ordinary request path.
        migrations.RunSQL("""
            CREATE OR REPLACE FUNCTION ai_compass_no_revision_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_OP = 'DELETE'
                 AND TG_TABLE_NAME = 'config_evidenceblob'
                 AND current_setting('ai_compass.purge_blob', true) = 'on' THEN
                RETURN OLD;
              END IF;
              RAISE EXCEPTION 'Immutable catalog history cannot be modified or deleted';
            END $$;
        """, reverse_sql="""
            CREATE OR REPLACE FUNCTION ai_compass_no_revision_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              RAISE EXCEPTION 'Immutable catalog history cannot be modified or deleted';
            END $$;
        """),
    ]
