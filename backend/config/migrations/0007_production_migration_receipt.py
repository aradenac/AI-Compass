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
            """
            CREATE TRIGGER immutable_production_migration_receipt BEFORE UPDATE OR DELETE
                ON config_productionmigrationreceipt FOR EACH ROW
                EXECUTE FUNCTION ai_compass_no_revision_mutation();

            CREATE FUNCTION ai_compass_validate_production_promotion() RETURNS trigger
            LANGUAGE plpgsql AS $
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM config_catalogrevision src
                  JOIN config_catalogrevision dst ON dst.id=NEW.target_revision_id
                  JOIN config_objecttypeversion s ON s.id=src.schema_version_id
                  JOIN config_objecttypeversion t ON t.id=dst.schema_version_id
                WHERE src.id=NEW.source_revision_id
                  AND src.item_id=NEW.item_id AND dst.item_id=NEW.item_id
                  AND dst.number=src.number + 1
                  AND s.type_slug='model' AND s.version=1
                  AND t.type_slug='model' AND t.version=2
              ) THEN
                RAISE EXCEPTION 'Production promotion must link successive v1/v2 revisions of one Model';
              END IF;
              RETURN NEW;
            END $;

            CREATE TRIGGER validate_production_migration_receipt
              BEFORE INSERT ON config_productionmigrationreceipt FOR EACH ROW
              EXECUTE FUNCTION ai_compass_validate_production_promotion();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS validate_production_migration_receipt ON config_productionmigrationreceipt;
            DROP FUNCTION IF EXISTS ai_compass_validate_production_promotion();
            DROP TRIGGER IF EXISTS immutable_production_migration_receipt ON config_productionmigrationreceipt;
            """,
        ),
    ]
