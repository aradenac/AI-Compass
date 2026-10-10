"""FUT-05: new immutable offer type and relational campaign price selections.

No historical campaign revision is rewritten or assigned guessed prices.
"""
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids

OFFER_SCHEMA = {
    "$schema":"https://json-schema.org/draft/2020-12/schema",
    "type":"object",
    "properties":{
        "component_id":{"type":"string"},
        "billing_owner":{"type":"string"},
        "currency":{"type":"string","minLength":3,"maxLength":3},
        "source":{"type":"string"},
        "checked_on":{"type":"string"},
        "effective_from":{"type":["string","null"]},
        "effective_to":{"type":["string","null"]},
        "status":{"enum":["active","retired","unknown"]},
        "terms":{"type":"string"},
        "tax_treatment":{"enum":["included","excluded","unknown"]},
        "applicability":{"type":"object"},
        "lines":{"type":"array","minItems":1,"maxItems":32,"items":{"type":"object"}}
    },
    "required":["component_id","billing_owner","currency","source","checked_on","status","lines"],
    "additionalProperties":False
}

def register_schema(apps, editor):
    registry=apps.get_model("config","ObjectTypeVersion")
    registry.objects.using(editor.connection.alias).create(
        type_slug="pricing_offer",version=1,json_schema=OFFER_SCHEMA)


class Migration(migrations.Migration):
    dependencies=[("config","0022_external_import_mock")]
    operations=[
        migrations.CreateModel(
            name="CampaignPricingPin",
            fields=[
                ("id",models.UUIDField(primary_key=True,default=config.catalog_ids.uuid7,
                                        editable=False,serialize=False)),
                ("source_key",models.CharField(max_length=160)),
                ("snapshot",models.ForeignKey(to="config.campaignsnapshot",
                    on_delete=django.db.models.deletion.PROTECT,related_name="pricing_pins")),
                ("component",models.ForeignKey(to="config.catalogitem",
                    on_delete=django.db.models.deletion.PROTECT,related_name="+")),
                ("offer",models.ForeignKey(to="config.catalogitem",
                    on_delete=django.db.models.deletion.PROTECT,related_name="+")),
                ("offer_revision",models.ForeignKey(to="config.catalogrevision",
                    on_delete=django.db.models.deletion.PROTECT,related_name="+")),
            ],
            options={"ordering":["snapshot_id","source_key"]}
        ),
        migrations.AddConstraint(
            model_name="campaignpricingpin",
            constraint=models.UniqueConstraint(fields=["snapshot","source_key"],
                 name="uniq_campaign_pricing_source")
        ),
        migrations.CreateModel(
            name="SessionPricingPin",
            fields=[
                ("id",models.UUIDField(primary_key=True,default=config.catalog_ids.uuid7,
                                        editable=False,serialize=False)),
                ("source_key",models.CharField(max_length=160)),
                ("session",models.ForeignKey(to="config.benchmarksession",
                    on_delete=django.db.models.deletion.PROTECT,related_name="pricing_pins")),
                ("component",models.ForeignKey(to="config.catalogitem",
                    on_delete=django.db.models.deletion.PROTECT,related_name="+")),
                ("offer",models.ForeignKey(to="config.catalogitem",
                    on_delete=django.db.models.deletion.PROTECT,related_name="+")),
                ("offer_revision",models.ForeignKey(to="config.catalogrevision",
                    on_delete=django.db.models.deletion.PROTECT,related_name="+")),
            ],
            options={"ordering":["session_id","source_key"]},
        ),
        migrations.AddConstraint(
            model_name="sessionpricingpin",
            constraint=models.UniqueConstraint(fields=["session","source_key"],
                name="uniq_session_pricing_source"),
        ),
        migrations.RunPython(register_schema,reverse_code=migrations.RunPython.noop),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_campaign_pricing_pin BEFORE UPDATE OR DELETE
            ON config_campaignpricingpin FOR EACH ROW
            EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE FUNCTION ai_compass_validate_campaign_pricing_pin() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              IF NOT EXISTS (
                  SELECT 1 FROM config_catalogrevision r
                  JOIN config_catalogitem i ON i.id=r.item_id
                  WHERE r.id=NEW.offer_revision_id AND i.id=NEW.offer_id
                  AND i.type_slug='pricing_offer'
              ) THEN
                RAISE EXCEPTION 'Offer revision must belong to the pinned pricing offer';
              END IF;
              IF NOT EXISTS (
                  SELECT 1 FROM config_catalogitem c
                  JOIN config_catalogrevision r ON r.id=NEW.offer_revision_id
                  WHERE c.id=NEW.component_id AND
                        c.public_id=(r.properties->>'component_id') AND
                        c.type_slug IN ('model','provider','harness','framework')
              ) THEN
                RAISE EXCEPTION 'Pricing offer is not applicable to the pinned component';
              END IF;
              RETURN NEW;
            END;
            $$;
            CREATE TRIGGER validate_campaign_pricing_pin BEFORE INSERT
            ON config_campaignpricingpin FOR EACH ROW
            EXECUTE FUNCTION ai_compass_validate_campaign_pricing_pin();
            CREATE TRIGGER immutable_session_pricing_pin BEFORE UPDATE OR DELETE
            ON config_sessionpricingpin FOR EACH ROW
            EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER validate_session_pricing_pin BEFORE INSERT
            ON config_sessionpricingpin FOR EACH ROW
            EXECUTE FUNCTION ai_compass_validate_campaign_pricing_pin();
        """,reverse_sql="""
            DROP TRIGGER IF EXISTS validate_session_pricing_pin ON config_sessionpricingpin;
            DROP TRIGGER IF EXISTS immutable_session_pricing_pin ON config_sessionpricingpin;
            DROP TRIGGER IF EXISTS validate_campaign_pricing_pin ON config_campaignpricingpin;
            DROP FUNCTION IF EXISTS ai_compass_validate_campaign_pricing_pin();
            DROP TRIGGER IF EXISTS immutable_campaign_pricing_pin ON config_campaignpricingpin;
        """)
    ]
