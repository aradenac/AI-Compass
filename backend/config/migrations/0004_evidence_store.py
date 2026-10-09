"""Append-only evidence metadata with strict revision-to-item identity guards."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import config.catalog_ids

GUARDS = """
CREATE TRIGGER immutable_evidence_blob BEFORE UPDATE OR DELETE ON config_evidenceblob
FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();

CREATE TRIGGER immutable_evidence_link BEFORE UPDATE OR DELETE ON config_evidencelink
FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();

CREATE OR REPLACE FUNCTION ai_compass_validate_evidence_target() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.revision_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM config_catalogrevision r
    WHERE r.id = NEW.revision_id AND r.item_id = NEW.item_id
  ) THEN
    RAISE EXCEPTION 'Evidence revision must belong to its target catalog item';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER evidence_link_target_guard BEFORE INSERT ON config_evidencelink
FOR EACH ROW EXECUTE FUNCTION ai_compass_validate_evidence_target();
"""

DROP_GUARDS = """
DROP TRIGGER IF EXISTS evidence_link_target_guard ON config_evidencelink;
DROP TRIGGER IF EXISTS immutable_evidence_link ON config_evidencelink;
DROP TRIGGER IF EXISTS immutable_evidence_blob ON config_evidenceblob;
DROP FUNCTION IF EXISTS ai_compass_validate_evidence_target();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("config", "0003_technology_catalog_schemas"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="EvidenceBlob",
            fields=[
                ("sha256", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("size", models.PositiveBigIntegerField()),
                ("media_type", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="EvidenceLink",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=config.catalog_ids.uuid7,
                                        editable=False, serialize=False)),
                ("original_filename", models.CharField(max_length=180)),
                ("source", models.CharField(max_length=600, blank=True)),
                ("provenance", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("blob", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                         related_name="links", to="config.evidenceblob")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                         related_name="evidence_links", to="config.catalogitem")),
                ("revision", models.ForeignKey(null=True, blank=True,
                         on_delete=django.db.models.deletion.PROTECT,
                         related_name="evidence_links", to="config.catalogrevision")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                         to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.RunSQL(GUARDS, reverse_sql=DROP_GUARDS),
    ]
