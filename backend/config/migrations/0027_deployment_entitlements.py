"""FUT-15: additive immutable external entitlement and deliberate deployment ledger."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids

UUID=lambda:models.UUIDField(primary_key=True,serialize=False,editable=False,
                              default=config.catalog_ids.uuid7)
PROTECT=django.db.models.deletion.PROTECT

class Migration(migrations.Migration):
    dependencies=[("config","0026_dap_opportunity"),
                  migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="DeploymentTarget",fields=[
            ("id",UUID()),("public_id",models.CharField(max_length=120,unique=True)),
            ("candidate_kind",models.CharField(max_length=16)),
            ("configuration",models.JSONField(default=dict)),
            ("purpose",models.CharField(max_length=16)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("population",models.ForeignKey(to="config.workloadprofile",
                on_delete=PROTECT,related_name="deployment_targets")),
            ("scenario",models.ForeignKey(to="config.opportunityscenario",
                on_delete=PROTECT,related_name="deployment_targets")),
            ("scenario_snapshot",models.ForeignKey(to="config.opportunitysnapshot",
                on_delete=PROTECT,related_name="deployment_targets")),
            ("task",models.ForeignKey(to="config.tasknode",
                on_delete=PROTECT,related_name="+")),
            ("candidate",models.ForeignKey(to="config.catalogitem",
                on_delete=PROTECT,related_name="+")),
            ("created_by",models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=PROTECT,related_name="deployment_targets")),
        ]),
        migrations.CreateModel(name="DeploymentBeneficiary",fields=[
            ("id",UUID()),
            ("target",models.ForeignKey(to="config.deploymenttarget",
                on_delete=PROTECT,related_name="beneficiaries")),
            ("person",models.ForeignKey(to="config.workloadprofile",
                on_delete=PROTECT,related_name="deployment_beneficiaries")),
        ]),
        migrations.CreateModel(name="ExternalEntitlement",fields=[
            ("id",UUID()),("public_id",models.CharField(max_length=120,unique=True)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("person",models.ForeignKey(to="config.workloadprofile",
                on_delete=PROTECT,related_name="external_entitlements")),
            ("component",models.ForeignKey(to="config.catalogitem",
                on_delete=PROTECT,related_name="external_entitlements")),
        ]),
        migrations.CreateModel(name="EntitlementEvent",fields=[
            ("id",UUID()),("number",models.PositiveIntegerField()),
            ("status",models.CharField(max_length=32)),
            ("reference",models.CharField(max_length=400)),
            ("reason",models.CharField(max_length=500)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("entitlement",models.ForeignKey(to="config.externalentitlement",
                on_delete=PROTECT,related_name="events")),
            ("actor",models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=PROTECT,related_name="external_entitlement_events")),
        ],options={"ordering":["number"]}),
        migrations.CreateModel(name="DeploymentMilestone",fields=[
            ("id",UUID()),("number",models.PositiveIntegerField()),
            ("action",models.CharField(max_length=32)),
            ("evidence_reference",models.CharField(max_length=400)),
            ("details",models.JSONField(default=dict)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("beneficiary",models.ForeignKey(to="config.deploymentbeneficiary",
                on_delete=PROTECT,related_name="milestones")),
            ("actor",models.ForeignKey(to=settings.AUTH_USER_MODEL,
                on_delete=PROTECT,related_name="deployment_milestones")),
        ],options={"ordering":["number"]}),
        migrations.AddConstraint("deploymentbeneficiary",models.UniqueConstraint(
            fields=["target","person"],name="uniq_deployment_beneficiary")),
        migrations.AddConstraint("externalentitlement",models.UniqueConstraint(
            fields=["person","component"],name="uniq_person_external_component")),
        migrations.AddConstraint("entitlementevent",models.UniqueConstraint(
            fields=["entitlement","number"],name="uniq_entitlement_event_seq")),
        migrations.AddConstraint("deploymentmilestone",models.UniqueConstraint(
            fields=["beneficiary","number"],name="uniq_deployment_milestone_seq")),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_deployment_target BEFORE UPDATE OR DELETE
              ON config_deploymenttarget FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_deployment_beneficiary BEFORE UPDATE OR DELETE
              ON config_deploymentbeneficiary FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_external_entitlement BEFORE UPDATE OR DELETE
              ON config_externalentitlement FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_entitlement_event BEFORE UPDATE OR DELETE
              ON config_entitlementevent FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE TRIGGER immutable_deployment_milestone BEFORE UPDATE OR DELETE
              ON config_deploymentmilestone FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
        """,reverse_sql="""
            DROP TRIGGER IF EXISTS immutable_deployment_target ON config_deploymenttarget;
            DROP TRIGGER IF EXISTS immutable_deployment_beneficiary ON config_deploymentbeneficiary;
            DROP TRIGGER IF EXISTS immutable_external_entitlement ON config_externalentitlement;
            DROP TRIGGER IF EXISTS immutable_entitlement_event ON config_entitlementevent;
            DROP TRIGGER IF EXISTS immutable_deployment_milestone ON config_deploymentmilestone;
        """),
    ]
