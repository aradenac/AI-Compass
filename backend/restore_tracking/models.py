"""Non-exported operational receipts for disposable native archive restoration."""
from django.db import models


class NativeRestore(models.Model):
    archive_sha256 = models.CharField(primary_key=True, max_length=64)
    state = models.CharField(max_length=16, default="prepared")
    subject_map = models.JSONField(default=dict)
    schema_map = models.JSONField(default=dict)
    counts = models.JSONField(default=dict)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class NativeRestoreEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    restore = models.ForeignKey(NativeRestore, on_delete=models.PROTECT, related_name="events")
    action = models.CharField(max_length=24)
    operator = models.CharField(max_length=150)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
