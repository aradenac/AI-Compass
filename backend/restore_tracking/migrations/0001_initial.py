from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="NativeRestore",
            fields=[
                ("archive_sha256", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("state", models.CharField(default="prepared", max_length=16)),
                ("subject_map", models.JSONField(default=dict)),
                ("schema_map", models.JSONField(default=dict)),
                ("counts", models.JSONField(default=dict)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="NativeRestoreEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=24)),
                ("operator", models.CharField(max_length=150)),
                ("detail", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("restore", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="events", to="restore_tracking.nativerestore")),
            ],
        ),
    ]
