"""PLAT-26 additive migration receipt table, protected from mutation."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids

class Migration(migrations.Migration):
    dependencies = [
        ("config", "0006_user_access_audit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="ProductionMigrationReceipt",
            fields=[
                ("id", models.UUIDField(default=config.catalog_ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ("candidate_id", models.CharField(max_length=16)),
                ("migration_key", models.CharField(max_length=80)),
                ("migration_sha256", models.CharField(max_length=64)),
                ("app_commit", models.CharField(max_length=40)),
                ("recovery_id", models.CharField(max_length=80)),
                ("recovery_manifest_sha256", models.CharField(max_length=64)),
                ("approved_report_sha256", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="migration_receipts", to="config.catalogitem")),
                ("source_revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="config.catalogrevision")),
                ("target_revision", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="config.catalogrevision")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.RunSQL(
            "CREATE TRIGGER immutable_production_migration_receipt BEFORE UPDATE OR DELETE "
            "ON config_productionmigrationreceipt FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();",
            reverse_sql="DROP TRIGGER IF EXISTS immutable_production_migration_receipt ON config_productionmigrationreceipt;",
        ),
    ]
