"""FUT-19: durable archive jobs, scoped download grants and access audit.

Additive only. ArchiveAccessEvent is append-only (mutation rejected by trigger);
a grant row is mutable only to record expiry/revocation/last use, never to
change its bound artifact or token digest.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids


class Migration(migrations.Migration):
    dependencies = [("config", "0029_retirement_and_purge"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="ArchiveJob", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("public_id", models.CharField(max_length=120, unique=True)),
            ("kind", models.CharField(max_length=16)),
            ("state", models.CharField(max_length=16, default="queued")),
            ("reason", models.CharField(max_length=120, blank=True)),
            ("requested_at", models.DateTimeField(auto_now_add=True)),
            ("started_at", models.DateTimeField(null=True, blank=True)),
            ("completed_at", models.DateTimeField(null=True, blank=True)),
            ("size_bytes", models.PositiveBigIntegerField(default=0)),
            ("sha256", models.CharField(max_length=64, blank=True)),
            ("artifact_path", models.CharField(max_length=300, blank=True)),
            ("manifest", models.JSONField(default=dict)),
            ("requested_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
        ], options={"ordering": ["requested_at", "id"]}),
        migrations.CreateModel(name="ArchiveGrant", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("public_id", models.CharField(max_length=120, unique=True)),
            ("token_digest", models.CharField(max_length=64, unique=True)),
            ("scope", models.CharField(max_length=32, default="download")),
            ("issued_at", models.DateTimeField(auto_now_add=True)),
            ("expires_at", models.DateTimeField()),
            ("revoked_at", models.DateTimeField(null=True, blank=True)),
            ("last_used_at", models.DateTimeField(null=True, blank=True)),
            ("issued_to", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
            ("job", models.ForeignKey(to="config.archivejob",
                on_delete=django.db.models.deletion.PROTECT, related_name="grants")),
        ], options={"ordering": ["issued_at", "id"]}),
        migrations.CreateModel(name="ArchiveAccessEvent", fields=[
            ("id", models.UUIDField(primary_key=True, editable=False, serialize=False,
                                    default=config.catalog_ids.uuid7)),
            ("action", models.CharField(max_length=32)),
            ("detail", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
            ("job", models.ForeignKey(to="config.archivejob", null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="+")),
        ], options={"ordering": ["created_at", "id"]}),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_archive_access_event BEFORE UPDATE OR DELETE
              ON config_archiveaccessevent FOR EACH ROW
              EXECUTE FUNCTION ai_compass_no_revision_mutation();
        """, reverse_sql="""
            DROP TRIGGER IF EXISTS immutable_archive_access_event ON config_archiveaccessevent;
        """),
    ]
