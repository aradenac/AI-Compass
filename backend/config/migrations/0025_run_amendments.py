"""FUT-11: additive Run corrections; never rewrite original observations."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import config.catalog_ids


class Migration(migrations.Migration):
    dependencies = [("config", "0024_user_environments"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="RunAmendment",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, editable=False,
                                         default=config.catalog_ids.uuid7)),
                ("number", models.PositiveIntegerField()),
                ("action", models.CharField(max_length=16)),
                ("outcome", models.CharField(max_length=12)),
                ("metrics", models.JSONField(default=dict)),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="run_amendments")),
                ("individual_run", models.ForeignKey(to="config.benchmarkrun",
                    null=True, blank=True,on_delete=django.db.models.deletion.PROTECT,
                    related_name="amendments")),
                ("composite_run", models.ForeignKey(to="config.compositebenchmarkrun",
                    null=True, blank=True,on_delete=django.db.models.deletion.PROTECT,
                    related_name="amendments")),
            ],
        ),
        migrations.AddConstraint("runamendment", models.CheckConstraint(
            condition=(models.Q(individual_run__isnull=False,composite_run__isnull=True) |
                       models.Q(individual_run__isnull=True,composite_run__isnull=False)),
            name="run_amendment_exactly_one_target")),
        migrations.AddConstraint("runamendment", models.UniqueConstraint(
            fields=["individual_run","number"],name="uniq_individual_run_amendment_number")),
        migrations.AddConstraint("runamendment", models.UniqueConstraint(
            fields=["composite_run","number"],name="uniq_composite_run_amendment_number")),
        migrations.AddConstraint("runamendment", models.CheckConstraint(
            condition=models.Q(number__gte=2),name="run_amendment_number_gte_2")),
        migrations.RunSQL("""
            CREATE TRIGGER immutable_run_amendment BEFORE UPDATE OR DELETE
            ON config_runamendment FOR EACH ROW
            EXECUTE FUNCTION ai_compass_no_revision_mutation();
            CREATE FUNCTION ai_compass_validate_run_amendment() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              IF NEW.action NOT IN ('corrected','withdrawn') OR
                 NEW.outcome NOT IN ('accepted','failed') OR
                 length(btrim(NEW.reason)) < 8 OR length(NEW.reason) > 2000
              THEN RAISE EXCEPTION 'Invalid Run amendment'; END IF;
              RETURN NEW;
            END $$;
            CREATE TRIGGER valid_run_amendment BEFORE INSERT
            ON config_runamendment FOR EACH ROW
            EXECUTE FUNCTION ai_compass_validate_run_amendment();
        """,reverse_sql="""
            DROP TRIGGER IF EXISTS valid_run_amendment ON config_runamendment;
            DROP FUNCTION IF EXISTS ai_compass_validate_run_amendment();
            DROP TRIGGER IF EXISTS immutable_run_amendment ON config_runamendment;
        """),
    ]
