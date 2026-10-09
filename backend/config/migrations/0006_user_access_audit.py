"""PLAT-28: append-only account-administration events (no business-data conversion)."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids

class Migration(migrations.Migration):
    dependencies = [
        ("config", "0005_task_taxonomy"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="UserAccessAuditEvent",
            fields=[
                ("id", models.UUIDField(default=config.catalog_ids.uuid7, editable=False,
                                        primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=32)),
                ("details", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            related_name="+", to=settings.AUTH_USER_MODEL)),
                ("subject", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="access_audit_events",
                                              to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.RunSQL(
            "CREATE TRIGGER immutable_user_access_audit BEFORE UPDATE OR DELETE "
            "ON config_useraccessauditevent FOR EACH ROW "
            "EXECUTE FUNCTION ai_compass_no_revision_mutation();",
            reverse_sql="DROP TRIGGER IF EXISTS immutable_user_access_audit ON config_useraccessauditevent;",
        ),
    ]
