"""FUT-06: append-only self-declared environments; no backfill of historical users.

The original v1 Harness and Framework schemas and catalog revisions remain
immutable. Supported OS lives in their versioned properties extension, with
service-layer checks before a usable/published revision can be asserted.
"""
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids


class Migration(migrations.Migration):
    dependencies = [("config", "0023_pricing_offers")]
    operations = [
        migrations.CreateModel(
            name="UserEnvironmentRevision",
            fields=[
                ("id", models.UUIDField(primary_key=True, editable=False,
                    default=config.catalog_ids.uuid7, serialize=False)),
                ("number", models.PositiveIntegerField()),
                ("available_os", models.JSONField()),
                ("user", models.ForeignKey(to="auth.user",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="environment_revisions")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["user_id", "number"]},
        ),
        migrations.AddConstraint(
            model_name="userenvironmentrevision",
            constraint=models.UniqueConstraint(fields=["user", "number"],
                                                name="uniq_user_environment_revision"),
        ),
        migrations.RunSQL(
            """
            CREATE TRIGGER immutable_user_environment_revision
            BEFORE UPDATE OR DELETE ON config_userenvironmentrevision
            FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
            """,
            reverse_sql="""DROP TRIGGER IF EXISTS immutable_user_environment_revision
                ON config_userenvironmentrevision;""",
        ),
    ]
