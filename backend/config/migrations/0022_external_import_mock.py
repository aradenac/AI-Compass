"""PLAT-33: additive external-source binding and immutable per-batch journals."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import config.catalog_ids


class Migration(migrations.Migration):
    dependencies = [
        ("config", "0021_workload_profiles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="ExternalImportBinding",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=config.catalog_ids.uuid7,
                                        editable=False, serialize=False)),
                ("source_system", models.CharField(max_length=80)),
                ("source_key", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("item", models.ForeignKey(to="config.catalogitem", related_name="external_import_bindings",
                                          on_delete=django.db.models.deletion.PROTECT)),
                ("last_import_revision", models.ForeignKey(to="config.catalogrevision", related_name="+",
                                                           on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name="ExternalImportBatch",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=config.catalog_ids.uuid7,
                                        editable=False, serialize=False)),
                ("source_system", models.CharField(max_length=80)),
                ("input_sha256", models.CharField(max_length=64, unique=True)),
                ("row_count", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                                            on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name="ExternalImportEvent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=config.catalog_ids.uuid7,
                                        editable=False, serialize=False)),
                ("source_key", models.CharField(max_length=128)),
                ("row_sha256", models.CharField(max_length=64)),
                ("action", models.CharField(max_length=12, choices=[
                    ("created", "Created"), ("revised", "Revised"), ("unchanged", "Unchanged")])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("batch", models.ForeignKey(to="config.externalimportbatch", related_name="events",
                                            on_delete=django.db.models.deletion.PROTECT)),
                ("binding", models.ForeignKey(to="config.externalimportbinding", related_name="events",
                                              on_delete=django.db.models.deletion.PROTECT)),
                ("item", models.ForeignKey(to="config.catalogitem", related_name="external_import_events",
                                           on_delete=django.db.models.deletion.PROTECT)),
                ("revision", models.ForeignKey(to="config.catalogrevision", related_name="external_import_events",
                                               on_delete=django.db.models.deletion.PROTECT)),
                ("evidence", models.ForeignKey(to="config.evidencelink", null=True, blank=True, related_name="+",
                                               on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="externalimportbinding",
            constraint=models.UniqueConstraint(fields=["source_system", "source_key"],
                                               name="uniq_external_source_record"),
        ),
        migrations.AddConstraint(
            model_name="externalimportevent",
            constraint=models.UniqueConstraint(fields=["batch", "source_key"],
                                               name="uniq_external_import_batch_row"),
        ),
        migrations.RunSQL(
            """
            CREATE TRIGGER immutable_external_import_batch BEFORE UPDATE OR DELETE
            ON config_externalimportbatch FOR EACH ROW
            EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_external_import_event BEFORE UPDATE OR DELETE
            ON config_externalimportevent FOR EACH ROW
            EXECUTE FUNCTION ai_compass_no_revision_mutation();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS immutable_external_import_event ON config_externalimportevent;
            DROP TRIGGER IF EXISTS immutable_external_import_batch ON config_externalimportbatch;
            """,
        ),
    ]
