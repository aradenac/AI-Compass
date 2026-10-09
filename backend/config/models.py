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


class DataHealthIssue(models.Model):
    """Mutable triage projection; all status changes have immutable linked events."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    dedupe_key = models.CharField(max_length=64, unique=True)
    category = models.CharField(max_length=48)
    severity = models.CharField(max_length=16)
    subject_type = models.CharField(max_length=32)
    subject_ref = models.CharField(max_length=120)  # private for restricted evidence
    summary = models.CharField(max_length=240)
    status = models.CharField(max_length=16, default="open")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="data_health_assignments")
    exception_rationale = models.TextField(blank=True)
    review_after = models.DateField(null=True, blank=True)
    first_detected_at = models.DateTimeField(auto_now_add=True)
    last_detected_at = models.DateTimeField(auto_now_add=True)
    last_scan_id = models.UUIDField(null=True, blank=True)
    detection_count = models.PositiveIntegerField(default=1)
    check_version = models.CharField(max_length=48, default="data-health@1")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_detected_at", "public_id"]


class DataHealthEvent(models.Model):
    """Append-only issue provenance, state changes, and attributable decisions."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    issue = models.ForeignKey(DataHealthIssue, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=32)
    detail = models.JSONField(default=dict)  # never includes blob bytes or credentials
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class TestCase(models.Model):
    """Reusable experimental challenge, NOT a node in the engineering task tree."""
    item = models.OneToOneField(CatalogItem, primary_key=True, on_delete=models.PROTECT,
                                related_name="test_case")
    task = models.ForeignKey(TaskNode, on_delete=models.PROTECT, related_name="test_cases")
    task_revision_at_creation = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT,
                                                  related_name="+")
    fork_parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="forks")
    fork_source_revision = models.ForeignKey(CatalogRevision, null=True, blank=True,
                                              on_delete=models.PROTECT, related_name="+")
    case_version = models.CharField(max_length=160)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fork_parent", "case_version"],
                                    name="uniq_test_case_fork_version"),
        ]
        ordering = ["item__public_id"]
