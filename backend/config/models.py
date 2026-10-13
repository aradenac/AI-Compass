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


class UserEnvironmentRevision(models.Model):
    """Self-declared OS availability history; append-only and never an entitlement."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="environment_revisions")
    number = models.PositiveIntegerField()
    available_os = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "number"], name="uniq_user_environment_revision")]
        ordering = ["user_id", "number"]


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

class CampaignPricingPin(models.Model):
    """Immutable chosen pricing offer revision for one real campaign technical source."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    snapshot = models.ForeignKey(CampaignSnapshot, on_delete=models.PROTECT,
                                 related_name="pricing_pins")
    source_key = models.CharField(max_length=160)
    component = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    offer = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    offer_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["snapshot", "source_key"], name="uniq_campaign_pricing_source")]
        ordering = ["snapshot_id", "source_key"]


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


class SessionPricingPin(models.Model):
    """Immutable exact commercial choice for a Task-centred Test Case session."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    session = models.ForeignKey(BenchmarkSession, on_delete=models.PROTECT,
                                related_name="pricing_pins")
    source_key = models.CharField(max_length=160)
    component = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    offer = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    offer_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["session", "source_key"], name="uniq_session_pricing_source")]
        ordering = ["session_id", "source_key"]


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


class CompositeBenchmarkRun(models.Model):
    """One immutable Framework-wide observation, with no individual Solution FK."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    session = models.OneToOneField(BenchmarkSession, on_delete=models.PROTECT,
                                   related_name="composite_run")
    closing_checkpoint = models.OneToOneField(SessionCheckpoint, on_delete=models.PROTECT,
                                               related_name="composite_run")
    framework = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    framework_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    outcome = models.CharField(max_length=12)
    metrics = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    provenance = models.JSONField(default=dict)
    participant_snapshots = models.JSONField(default=list)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="composite_benchmark_runs")
    created_at = models.DateTimeField(auto_now_add=True)


class CompositeRunParticipant(models.Model):
    """Relational pin to the precise campaign participant revision and role."""
    id = models.BigAutoField(primary_key=True)
    run = models.ForeignKey(CompositeBenchmarkRun, on_delete=models.PROTECT,
                            related_name="participant_pins")
    participant_pin = models.ForeignKey(CampaignParticipantPin, on_delete=models.PROTECT,
                                        related_name="composite_run_memberships")
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("run","participant_pin"),
                                    name="uniq_composite_run_member"),
            models.UniqueConstraint(fields=("run","position"),
                                    name="uniq_composite_run_position"),
        ]
        ordering = ["position"]


class CompositeRunEvidence(models.Model):
    """Immutable references to the existing content-checked #17 evidence store."""
    id = models.BigAutoField(primary_key=True)
    run = models.ForeignKey(CompositeBenchmarkRun, on_delete=models.PROTECT,
                            related_name="evidence_pins")
    evidence = models.ForeignKey(EvidenceLink, on_delete=models.PROTECT,
                                 related_name="composite_run_pins")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("run","evidence"), name="uniq_composite_run_evidence"),
        ]



class RunAmendment(models.Model):
    """Append-only correction/withdrawal of one original Run. r001 is the raw Run."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    individual_run = models.ForeignKey(BenchmarkRun, null=True, blank=True,
        on_delete=models.PROTECT, related_name="amendments")
    composite_run = models.ForeignKey(CompositeBenchmarkRun, null=True, blank=True,
        on_delete=models.PROTECT, related_name="amendments")
    audit_event = models.OneToOneField(CatalogAuditEvent, on_delete=models.PROTECT,
                                        related_name="run_amendment")
    number = models.PositiveIntegerField()
    action = models.CharField(max_length=16)  # corrected | withdrawn
    outcome = models.CharField(max_length=12)
    metrics = models.JSONField(default=dict)
    reason = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="run_amendments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(individual_run__isnull=False, composite_run__isnull=True) |
                           models.Q(individual_run__isnull=True, composite_run__isnull=False)),
                name="run_amendment_exactly_one_target"),
            models.UniqueConstraint(fields=["individual_run", "number"],
                                    name="uniq_individual_run_amendment_number"),
            models.UniqueConstraint(fields=["composite_run", "number"],
                                    name="uniq_composite_run_amendment_number"),
            models.CheckConstraint(condition=models.Q(number__gte=2),
                                   name="run_amendment_number_gte_2"),
        ]

class WatchSourcePin(models.Model):
    """Immutable many-to-many provenance: Watch Entry revision -> Source exact revision."""
    id = models.BigAutoField(primary_key=True)
    entry_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT,
                                       related_name="watch_source_pins")
    source = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    source_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT,
                                        related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("entry_revision", "source"), name="uniq_watch_source_revision"),
        ]


class ForecastSnapshot(models.Model):
    """Immutable theoretical setup tied to one forecast revision, never a measured Solution."""
    revision = models.OneToOneField(CatalogRevision, primary_key=True, on_delete=models.PROTECT,
                                    related_name="forecast_snapshot")
    task = models.ForeignKey(TaskNode, on_delete=models.PROTECT, related_name="+")
    task_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    model = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    model_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    provider = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    provider_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    harness = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    harness_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    configuration = models.JSONField(default=dict)


class ForecastWatchPin(models.Model):
    """Exact Watch Entry revision explicitly supporting one immutable forecast."""
    id = models.BigAutoField(primary_key=True)
    snapshot = models.ForeignKey(ForecastSnapshot, on_delete=models.PROTECT,
                                 related_name="watch_pins")
    watch = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    watch_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("snapshot", "watch"), name="uniq_forecast_watch"),
        ]


class CampaignForecastOrigin(models.Model):
    """Never infer observed measurements from this historical forecasting origin."""
    campaign_snapshot = models.OneToOneField(CampaignSnapshot, primary_key=True,
        on_delete=models.PROTECT, related_name="forecast_origin")
    forecast_snapshot = models.ForeignKey(ForecastSnapshot, on_delete=models.PROTECT,
        related_name="validation_campaigns")


class CampaignForecastWatchPin(models.Model):
    """Immutable preselected signals, copied when a Campaign revision is appended."""
    id = models.BigAutoField(primary_key=True)
    origin = models.ForeignKey(CampaignForecastOrigin, on_delete=models.PROTECT,
        related_name="watch_pins")
    watch = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    watch_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("origin", "watch"), name="uniq_campaign_forecast_watch"),
        ]


class EvaluationSnapshot(models.Model):
    """One immutable interpretation; source Runs and their metrics are not rewritten."""
    revision = models.OneToOneField(CatalogRevision, primary_key=True, on_delete=models.PROTECT,
                                    related_name="evaluation_snapshot")
    scoring_method = models.ForeignKey(ObjectTypeVersion, on_delete=models.PROTECT,
                                        related_name="evaluation_snapshots")
    scoring_config = models.JSONField(default=dict)


class EvaluationIndividualRunPin(models.Model):
    """Exact original individual run plus captured experimental method/provenance."""
    id = models.BigAutoField(primary_key=True)
    snapshot = models.ForeignKey(EvaluationSnapshot, on_delete=models.PROTECT,
                                 related_name="individual_pins")
    run = models.ForeignKey(BenchmarkRun, on_delete=models.PROTECT, related_name="evaluation_pins")
    method_definition = models.ForeignKey(ObjectTypeVersion, on_delete=models.PROTECT,
                                           related_name="+")
    input_context = models.JSONField(default=dict)
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("snapshot", "run"), name="uniq_evaluation_individual_run"),
            models.UniqueConstraint(fields=("snapshot", "position"), name="uniq_evaluation_individual_order"),
        ]


class EvaluationCompositeRunPin(models.Model):
    """Composite workflow stays separate from all individual solution estimates."""
    id = models.BigAutoField(primary_key=True)
    snapshot = models.ForeignKey(EvaluationSnapshot, on_delete=models.PROTECT,
                                 related_name="composite_pins")
    run = models.ForeignKey(CompositeBenchmarkRun, on_delete=models.PROTECT, related_name="evaluation_pins")
    method_definition = models.ForeignKey(ObjectTypeVersion, on_delete=models.PROTECT,
                                           related_name="+")
    input_context = models.JSONField(default=dict)
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("snapshot", "run"), name="uniq_evaluation_composite_run"),
            models.UniqueConstraint(fields=("snapshot", "position"), name="uniq_evaluation_composite_order"),
        ]


class RecommendationSnapshot(models.Model):
    """Exact immutable task/individual-solution decision and reviewer provenance."""
    revision = models.OneToOneField(CatalogRevision, primary_key=True, on_delete=models.PROTECT,
                                    related_name="recommendation_snapshot")
    task = models.ForeignKey(TaskNode, on_delete=models.PROTECT, related_name="+")
    task_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    solution = models.ForeignKey(MeasuredSolution, on_delete=models.PROTECT, related_name="+")
    solution_revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT, related_name="+")
    evaluation = models.ForeignKey(EvaluationSnapshot, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="recommendations")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)


class RecommendationRunPin(models.Model):
    """Original measured individual Run; composite runs cannot be solution evidence."""
    id = models.BigAutoField(primary_key=True)
    snapshot = models.ForeignKey(RecommendationSnapshot, on_delete=models.PROTECT,
                                 related_name="run_pins")
    run = models.ForeignKey(BenchmarkRun, on_delete=models.PROTECT, related_name="recommendation_pins")
    acknowledged_amendment = models.ForeignKey(RunAmendment, null=True, blank=True,
        on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("snapshot", "run"), name="uniq_recommendation_run"),
        ]


class DiscussionThread(models.Model):
    """Immutable feedback conversation with optionally pinned catalog object context."""
    item = models.OneToOneField(CatalogItem, primary_key=True, on_delete=models.PROTECT,
                                related_name="discussion_thread")
    context_item = models.ForeignKey(CatalogItem, null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="+")
    context_revision = models.ForeignKey(CatalogRevision, null=True, blank=True,
                                         on_delete=models.PROTECT, related_name="+")


class DiscussionMessage(models.Model):
    """Permanent identity and parent FK; text/visibility/corrections are catalog revisions."""
    item = models.OneToOneField(CatalogItem, primary_key=True, on_delete=models.PROTECT,
                                related_name="discussion_message")
    thread = models.ForeignKey(DiscussionThread, on_delete=models.PROTECT,
                               related_name="messages")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="replies")


class WorkloadProfile(models.Model):
    """Stable planning identity. Not an AI Compass account or a Task."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=16, choices=[
        ("role", "Job Role"), ("specialty", "Specialty"),
        ("person", "Person"), ("cohort", "Planning Cohort"),
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "public_id"]


class WorkloadRevision(models.Model):
    """Append-only planning snapshot; old rate and membership never disappear."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    profile = models.ForeignKey(WorkloadProfile, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=160)
    role = models.ForeignKey(WorkloadProfile, null=True, blank=True,
                             on_delete=models.PROTECT, related_name="role_dependents")
    specialty = models.ForeignKey(WorkloadProfile, null=True, blank=True,
                                  on_delete=models.PROTECT, related_name="specialty_dependents")
    linked_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="workload_revisions")
    headcount = models.PositiveIntegerField(default=1)
    hourly_rate_eur = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="authored_workload_revisions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profile", "number"], name="uniq_workload_revision_number"),
        ]
        ordering = ["profile", "number"]


class WorkloadAllocation(models.Model):
    """Original annual Task estimates; null is unknown, 0 is explicit zero."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    revision = models.ForeignKey(WorkloadRevision, on_delete=models.PROTECT, related_name="allocations")
    task = models.ForeignKey(TaskNode, on_delete=models.PROTECT, related_name="workload_allocations")
    annual_occurrences = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    baseline_human_hours = models.DecimalField(max_digits=8, decimal_places=2,
                                               null=True, blank=True)
    excluded = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["revision", "task"], name="uniq_workload_revision_task"),
        ]
        ordering = ["task__item__public_id"]



class OpportunityScenario(models.Model):
    """Stable planning scenario identity; exactly one scoped DAP-01 population."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    profile = models.ForeignKey(WorkloadProfile, on_delete=models.PROTECT,
                                related_name="opportunity_scenarios")
    created_at = models.DateTimeField(auto_now_add=True)


class OpportunitySnapshot(models.Model):
    """Immutable scenario choice, inputs and derived annual potential at one point in time.

    GET /current recalculates from effective sources; it does not mutate this snapshot.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    scenario = models.ForeignKey(OpportunityScenario, on_delete=models.PROTECT,
                                 related_name="snapshots")
    number = models.PositiveIntegerField()
    algorithm = models.CharField(max_length=48, default="dap-opportunity-v1")
    assumptions = models.JSONField(default=dict)
    projection = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="opportunity_snapshots")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["scenario", "number"], name="uniq_opportunity_scenario_revision")]
        ordering = ["scenario", "number"]


class ExternalImportBinding(models.Model):
    """Stable external identity map; its last-import pointer advances on new revisions."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    source_system = models.CharField(max_length=80)
    source_key = models.CharField(max_length=128)
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT,
                             related_name="external_import_bindings")
    last_import_revision = models.ForeignKey(
        CatalogRevision, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source_system", "source_key"],
                                               name="uniq_external_source_record")]


class ExternalImportBatch(models.Model):
    """Durable exact-input idempotency journal, never mutated/deleted."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    source_system = models.CharField(max_length=80)
    input_sha256 = models.CharField(max_length=64, unique=True)
    row_count = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ExternalImportEvent(models.Model):
    """Immutable per-row result linking target revision and retained source bytes."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    batch = models.ForeignKey(ExternalImportBatch, on_delete=models.PROTECT,
                              related_name="events")
    binding = models.ForeignKey(ExternalImportBinding, on_delete=models.PROTECT,
                                related_name="events")
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT,
                             related_name="external_import_events")
    revision = models.ForeignKey(CatalogRevision, on_delete=models.PROTECT,
                                 related_name="external_import_events")
    evidence = models.ForeignKey(EvidenceLink, null=True, blank=True,
                                 on_delete=models.PROTECT, related_name="+")
    source_key = models.CharField(max_length=128)
    row_sha256 = models.CharField(max_length=64)
    action = models.CharField(max_length=12, choices=[
        ("created", "Created"), ("revised", "Revised"), ("unchanged", "Unchanged")
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["batch", "source_key"],
                                               name="uniq_external_import_batch_row")]
        ordering = ["created_at", "id"]


class DeploymentTarget(models.Model):
    """Stable, deliberately selected target: never an AI Compass role grant."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    population = models.ForeignKey(WorkloadProfile, on_delete=models.PROTECT,
                                   related_name="deployment_targets")
    task = models.ForeignKey(TaskNode, on_delete=models.PROTECT, related_name="+")
    candidate = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=12, choices=[("benchmark", "Benchmark"), ("forecast", "Forecast")])
    origin = models.ForeignKey(OpportunitySnapshot, null=True, blank=True,
                               on_delete=models.PROTECT, related_name="deployment_targets")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="created_deployment_targets")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["population", "task", "candidate", "kind"],
            name="uniq_deployment_target_scope")]


class DeploymentRevision(models.Model):
    """Immutable target scope and exact external-component/guide pins."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    target = models.ForeignKey(DeploymentTarget, on_delete=models.PROTECT,
                               related_name="revisions")
    number = models.PositiveIntegerField()
    selection = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="deployment_revisions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["target", "number"], name="uniq_deployment_target_revision")]


class DeploymentEvent(models.Model):
    """Append-only manual claims; neither passwords nor actual provider grants."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    target = models.ForeignKey(DeploymentTarget, on_delete=models.PROTECT,
                               related_name="events")
    target_revision = models.ForeignKey(DeploymentRevision, on_delete=models.PROTECT,
                                        related_name="+")
    seat_key = models.CharField(max_length=64)
    beneficiary = models.ForeignKey(WorkloadProfile, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    component = models.ForeignKey(CatalogItem, null=True, blank=True,
                                  on_delete=models.PROTECT, related_name="+")
    component_revision = models.ForeignKey(CatalogRevision, null=True, blank=True,
                                           on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=24)
    evidence_reference = models.CharField(max_length=300, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="deployment_events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class BudgetPlan(models.Model):
    """Permanent, explicitly selected resource request; no purchasing or IAM."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    profile = models.ForeignKey(WorkloadProfile, on_delete=models.PROTECT,
                                related_name="resource_budgets")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="created_resource_budgets")
    created_at = models.DateTimeField(auto_now_add=True)


class BudgetRevision(models.Model):
    """Append-only source-pinned planning decision and frozen cost/quantity projection."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    budget = models.ForeignKey(BudgetPlan, on_delete=models.PROTECT,
                               related_name="revisions")
    number = models.PositiveIntegerField()
    algorithm = models.CharField(max_length=48, default="dap-resource-v1")
    assumptions = models.JSONField(default=dict)
    projection = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="resource_budget_revisions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["budget", "number"], name="uniq_resource_budget_revision")]
        ordering = ["budget", "number"]


class RetirementRecord(models.Model):
    """FUT-18: append-only logical retirement of one versioned business object.

    Logical retirement hides an object from current default catalogs while
    preserving its stable public id, immutable revisions and historical
    references. It is NOT physical erasure and never cascades a delete.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    item = models.OneToOneField(CatalogItem, on_delete=models.PROTECT,
                                related_name="retirement")
    action = models.CharField(max_length=16)  # retired|restored
    reason = models.CharField(max_length=600, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="retirement_records")
    retired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["retired_at", "id"]


class RetirementEvent(models.Model):
    """Append-only tombstone/revocation trail; reapplied after a restore."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT,
                             related_name="retirement_events")
    action = models.CharField(max_length=16)  # retired|restored|purged|blocked
    reason = models.CharField(max_length=600, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="+")
    detail = models.JSONField(default=dict)  # never blob bytes or secrets
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class PurgePolicy(models.Model):
    """FUT-18: single versioned, auditable retention policy; disabled by default.

    Grace duration and enabled state are administrative decisions, never a
    hardcoded universal rule. Changes are audited through PurgePolicyRevision.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    is_active = models.BooleanField(default=False)
    enabled = models.BooleanField(default=False)  # automatic GC off by default
    grace_days = models.PositiveIntegerField(default=30)  # illustrative, not forced
    eligible_classes = models.JSONField(default=list)  # subset of PURGE_CLASSES
    cadence_hours = models.PositiveIntegerField(default=168)
    version = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-version", "id"]


class PurgeCandidate(models.Model):
    """FUT-18: durable inventoried candidate with its immutable preview guard."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=24)  # evidence_blob|managed_record
    subject = models.CharField(max_length=140)  # blob sha256 or record public id
    eligible_at = models.DateTimeField()
    first_seen_at = models.DateTimeField(auto_now_add=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    blockers = models.JSONField(default=list)  # protected-reference / policy reasons
    preview = models.JSONField(default=dict)   # immutable dry-run snapshot
    state = models.CharField(max_length=16, default="candidate")  # candidate|purged|blocked

    class Meta:
        ordering = ["first_seen_at", "id"]


class PurgeReceipt(models.Model):
    """FUT-18: durable, attributable purge result; never a silent deletion."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    job_key = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="+")
    reclaimed_bytes = models.PositiveBigIntegerField(default=0)
    purged_count = models.PositiveIntegerField(default=0)
    blocked_count = models.PositiveIntegerField(default=0)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class ArchiveJob(models.Model):
    """FUT-19: durable, server-managed archive build; never an HTTP-lifetime job.

    The artifact is produced by a separate process invoked by the API (a
    management command), so a large confidential archive is never serialized in
    API request memory. State is persisted so a client or operator can poll
    progress, sizes, integrity and failure reason.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=16)  # native|full_recovery
    state = models.CharField(max_length=16, default="queued")  # queued|running|complete|failed
    reason = models.CharField(max_length=120, blank=True)  # machine-readable failure reason
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.deletion.PROTECT, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    artifact_path = models.CharField(max_length=300, blank=True)
    manifest = models.JSONField(default=dict)  # verification summary, no secrets

    class Meta:
        ordering = ["requested_at", "id"]


class ArchiveGrant(models.Model):
    """FUT-19: short-lived, revocable, artifact-scoped download bearer token.

    Only the SHA-256 digest of the random token is stored. The raw token is
    revealed exactly once, through an authenticated CSRF-protected operation,
    and is never written to audit, logs or a URL/query string.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    public_id = models.CharField(max_length=120, unique=True)
    job = models.ForeignKey(ArchiveJob, on_delete=models.deletion.PROTECT,
                            related_name="grants")
    token_digest = models.CharField(max_length=64, unique=True)
    issued_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.deletion.PROTECT, related_name="+")
    scope = models.CharField(max_length=32, default="download")
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["issued_at", "id"]


class ArchiveAccessEvent(models.Model):
    """FUT-19: append-only attributable audit of archive request/grant/transfer.

    Records who did what to which artifact; its JSON detail must never carry a
    raw bearer token, byte range of confidential content or other secret.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.deletion.PROTECT, related_name="+")
    job = models.ForeignKey(ArchiveJob, null=True, blank=True,
                            on_delete=models.deletion.PROTECT, related_name="+")
    action = models.CharField(max_length=32)  # requested|grant_issued|grant_revoked|downloaded|denied
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class CapacityPolicy(models.Model):
    """FUT-20: small versioned, auditable platform-operator capacity policy.

    Only soft, administrable thresholds live here. Physical technical limits
    (free disk, DB integrity, upload parser and archive decompression guards) are
    NOT stored: they are detected and explained, never self-granted. A new row
    supersedes the previous active one; a policy change never rewrites pinned
    historical data.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    is_active = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    evidence_warn_bytes = models.PositiveBigIntegerField(default=8 * 1024 ** 3)
    disk_warn_percent = models.PositiveIntegerField(default=80)
    archive_concurrency_warn = models.PositiveIntegerField(default=4)
    upload_quota_warn_bytes = models.PositiveBigIntegerField(default=2 * 1024 ** 3)
    threshold_factors = models.JSONField(default=dict)  # optional per-metric overrides
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-version", "id"]


class CapacityPolicyEvent(models.Model):
    """FUT-20: append-only who/when/old/new audit of every policy change."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=32)  # updated|reset
    previous = models.JSONField(default=dict)
    applied = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class AccessThrottle(models.Model):
    """FUT-20: durable, DB-backed failed-login counter for Internet profiles.

    A minimal keyed counter so abuse controls survive process/worker restarts and
    need no speculative Redis/broker. A key is one-way hashed; no password or
    secret is ever stored.
    """
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    key_digest = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["updated_at", "id"]
