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


class EvidenceBlob(models.Model):
    """Immutable content-addressed payload metadata; bytes live on private volume."""
    sha256 = models.CharField(primary_key=True, max_length=64)
    size = models.PositiveBigIntegerField()
    media_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)


class EvidenceLink(models.Model):
    """Immutable attribution per usage, even when two usages share identical bytes."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    blob = models.ForeignKey(EvidenceBlob, on_delete=models.PROTECT, related_name="links")
    # Stable FK to any currently supported catalog item; other domain targets
    # may be added to this same link model as the platform grows.
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="evidence_links")
    revision = models.ForeignKey(
        CatalogRevision, null=True, blank=True, on_delete=models.PROTECT, related_name="evidence_links"
    )
    original_filename = models.CharField(max_length=180)
    source = models.CharField(max_length=600, blank=True)
    provenance = models.JSONField(default=dict)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class TaskNode(models.Model):
    """Current relational placement for a versioned engineering taxonomy node.

    CatalogItem owns permanent tsk-* identity and immutable content revisions.
    The current placement is materialized for fast tree and FK queries; every
    changed placement is preserved by TaskStructureRevision.
    """
    item = models.OneToOneField(
        CatalogItem, primary_key=True, on_delete=models.PROTECT, related_name="task_node"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "item_id"]


class TaskStructureRevision(models.Model):
    """Append-only parent/order snapshot associated with a CatalogRevision."""
    revision = models.OneToOneField(
        CatalogRevision, primary_key=True, on_delete=models.PROTECT,
        related_name="task_structure",
    )
    task = models.ForeignKey(TaskNode, on_delete=models.PROTECT, related_name="structure_history")
    parent = models.ForeignKey(
        TaskNode, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    position = models.PositiveIntegerField()


class UserAccessAuditEvent(models.Model):
    """Immutable record of account lifecycle and role/credential administration."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="access_audit_events")
    action = models.CharField(max_length=32)
    details = models.JSONField(default=dict)  # Includes no plaintext or hashed credentials.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class ProductionMigrationReceipt(models.Model):
    """Append-only per-object production migration receipt with pinned provenance."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="migration_receipts")
    source_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    target_revision = models.OneToOneField(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    candidate_id = models.CharField(max_length=16)
    migration_key = models.CharField(max_length=80)
    migration_sha256 = models.CharField(max_length=64)
    app_commit = models.CharField(max_length=40)
    recovery_id = models.CharField(max_length=80)
    recovery_manifest_sha256 = models.CharField(max_length=64)
    approved_report_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
