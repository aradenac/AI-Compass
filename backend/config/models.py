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


class CampaignSnapshot(models.Model):
    """Immutable, relationally pinned metadata for one campaign catalog revision."""
    revision = models.OneToOneField(
        CatalogRevision, primary_key=True, on_delete=models.PROTECT,
        related_name="campaign_snapshot")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="owned_campaign_snapshots")
    method_definition = models.ForeignKey(ObjectTypeVersion, on_delete=models.PROTECT,
                                          related_name="campaign_snapshots")
    fixed_task = models.ForeignKey(TaskNode, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    fixed_task_revision = models.ForeignKey(CatalogRevision, null=True, blank=True,
                                            on_delete=models.PROTECT, related_name="+")
    guide = models.ForeignKey(CatalogItem, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="+")
    guide_revision = models.ForeignKey(CatalogRevision, null=True, blank=True,
                                       on_delete=models.PROTECT, related_name="+")
    configuration = models.JSONField(default=dict)
    framework = models.ForeignKey(CatalogItem, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name="+")
    framework_revision = models.ForeignKey(CatalogRevision, null=True, blank=True,
                                           on_delete=models.PROTECT, related_name="+")


class CampaignCasePin(models.Model):
    snapshot = models.ForeignKey(CampaignSnapshot, on_delete=models.PROTECT,
                                 related_name="case_pins")
    test_case = models.ForeignKey(TestCase, on_delete=models.PROTECT, related_name="+")
    revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["snapshot", "test_case"], name="uniq_campaign_snapshot_case")]


class CampaignComponentPin(models.Model):
    snapshot = models.ForeignKey(CampaignSnapshot, on_delete=models.PROTECT,
                                 related_name="component_pins")
    kind = models.CharField(max_length=12)
    component = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["snapshot", "kind"], name="uniq_campaign_snapshot_component")]

class CampaignParticipantIdentity(models.Model):
    """Permanent, immutable participant identity owned by exactly one campaign."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    campaign = models.ForeignKey(CatalogItem, on_delete=models.PROTECT,
                                 related_name="participant_identities")


class CampaignParticipantPin(models.Model):
    """One exact configuration of a participant in an immutable campaign revision."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    snapshot = models.ForeignKey(CampaignSnapshot, on_delete=models.PROTECT,
                                 related_name="participant_pins")
    participant = models.ForeignKey(CampaignParticipantIdentity, on_delete=models.PROTECT,
                                    related_name="snapshots")
    position = models.PositiveIntegerField()
    label = models.CharField(max_length=160)
    role = models.CharField(max_length=160)
    model = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    model_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    provider = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    provider_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    harness = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    harness_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    configuration_version = models.CharField(max_length=160)
    settings = models.JSONField(default=dict)
    properties = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "participant"],
                                    name="uniq_campaign_participant_revision"),
            models.UniqueConstraint(fields=["snapshot", "position"],
                                    name="uniq_campaign_participant_order"),
        ]
        ordering = ["position", "participant__public_id"]


class BenchmarkSession(models.Model):
    """Permanent session identity, frozen experimental design and original references.

    All fields are immutable. Current state is the latest append-only checkpoint.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    campaign_snapshot = models.ForeignKey(CampaignSnapshot, on_delete=models.PROTECT,
                                          related_name="benchmark_sessions")
    case_pin = models.ForeignKey(CampaignCasePin, on_delete=models.PROTECT,
                                 related_name="benchmark_sessions")
    guide = models.ForeignKey(CatalogItem, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="+")
    guide_revision = models.ForeignKey(CatalogRevision, null=True, blank=True,
                                       on_delete=models.PROTECT, related_name="+")
    method_definition = models.ForeignKey(ObjectTypeVersion, on_delete=models.PROTECT,
                                          related_name="benchmark_sessions")
    method_descriptor = models.JSONField(default=dict)
    selected_participants = models.JSONField(default=list)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="benchmark_sessions")
    created_at = models.DateTimeField(auto_now_add=True)


class SessionCheckpoint(models.Model):
    """One server-confirmed, immutable step/action; never rewrite earlier drafts."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    session = models.ForeignKey(BenchmarkSession, on_delete=models.PROTECT,
                                related_name="checkpoints")
    number = models.PositiveIntegerField()
    action = models.CharField(max_length=32)
    state = models.JSONField(default=dict)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="+")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("session", "number"),
                                                 name="uniq_session_checkpoint")]
        ordering = ["number"]


class SessionCheckpointEvidence(models.Model):
    """Real #17 immutable evidence links pinned at each session checkpoint."""
    id = models.BigAutoField(primary_key=True)
    checkpoint = models.ForeignKey(SessionCheckpoint, on_delete=models.PROTECT,
                                   related_name="evidence_pins")
    evidence = models.ForeignKey(EvidenceLink, on_delete=models.PROTECT,
                                 related_name="session_checkpoint_pins")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("checkpoint", "evidence"),
                                                 name="uniq_session_checkpoint_evidence")]


class SessionSolutionPin(models.Model):
    """Immutable individual setup pinned at session creation."""
    session = models.OneToOneField(BenchmarkSession, primary_key=True, on_delete=models.PROTECT,
                                   related_name="individual_setup")
    model = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    model_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    provider = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    provider_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    harness = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    harness_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    configuration_version = models.CharField(max_length=160, default="1")
    settings = models.JSONField(default=dict)
    properties = models.JSONField(default=dict)


class MeasuredSolution(models.Model):
    """Exactly one measured identity per canonical versioned setup fingerprint."""
    item = models.OneToOneField(CatalogItem, primary_key=True, on_delete=models.PROTECT,
                                related_name="measured_solution")
    fingerprint = models.CharField(max_length=64, unique=True)


class BenchmarkRun(models.Model):
    """Accepted or failed observation, never edited or deleted."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    session = models.OneToOneField(BenchmarkSession, on_delete=models.PROTECT,
                                   related_name="individual_run")
    closing_checkpoint = models.OneToOneField(SessionCheckpoint, on_delete=models.PROTECT,
                                                related_name="individual_run")
    solution = models.ForeignKey(MeasuredSolution, on_delete=models.PROTECT,
                                 related_name="runs")
    solution_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT,
                                          related_name="+")
    outcome = models.CharField(max_length=12)
    metrics = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    provenance = models.JSONField(default=dict)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="benchmark_runs")
    created_at = models.DateTimeField(auto_now_add=True)


class BenchmarkRunEvidence(models.Model):
    id = models.BigAutoField(primary_key=True)
    run = models.ForeignKey(BenchmarkRun, on_delete=models.PROTECT, related_name="evidence_pins")
    evidence = models.ForeignKey(EvidenceLink, on_delete=models.PROTECT, related_name="benchmark_run_pins")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("run", "evidence"), name="uniq_benchmark_run_evidence")]
