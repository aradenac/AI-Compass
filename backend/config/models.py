"""Immutable Model catalog identities and revisioned JSON properties."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .catalog_ids import uuid7


class ObjectTypeVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    type_slug = models.SlugField(max_length=40)
    version = models.PositiveIntegerField()
    json_schema = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["type_slug", "version"], name="uniq_object_type_version"),
        ]
        ordering = ["type_slug", "version"]


class CatalogItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    type_slug = models.SlugField(max_length=40, default="model")
    current_revision = models.ForeignKey(
        "CatalogRevision", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "public_id"]


class CatalogRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    schema_version = models.ForeignKey(ObjectTypeVersion, on_delete=models.PROTECT, related_name="revisions")
    display_name = models.CharField(max_length=160)
    properties = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "number"], name="uniq_item_revision_number"),
        ]
        ordering = ["item", "number"]


class CatalogAuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="audit_events")
    revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
