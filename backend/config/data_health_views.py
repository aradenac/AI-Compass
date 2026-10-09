"""PLAT-27: maintenance-only authenticated issue API and explicit scan action."""
from datetime import date

from django.contrib.auth import get_user_model
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .auth_views import capability, json_no_store, read_json
from .data_health_services import CATEGORIES, STATUSES, HealthScanInProgress, scan, triage
from .models import DataHealthIssue

RESTRICTED_SUBJECTS = {"evidence-blob", "evidence-link", "migration-receipt"}


def _serialize(issue):
    return {
        "id":issue.public_id,
        "category":issue.category,"severity":issue.severity,
        "subject_type":issue.subject_type,
        "subject_id":None if issue.subject_type in RESTRICTED_SUBJECTS else issue.subject_ref,
        "summary":issue.summary,"status":issue.status,
        "assigned_to":issue.assigned_to.username if issue.assigned_to_id else None,
        "exception_rationale":issue.exception_rationale,
        "review_after":str(issue.review_after) if issue.review_after else None,
        "first_detected_at":issue.first_detected_at.isoformat(),
        "last_detected_at":issue.last_detected_at.isoformat(),
        "detection_count":issue.detection_count,
        "check_version":issue.check_version,
        "last_scan_id":str(issue.last_scan_id) if issue.last_scan_id else None,
    }


@require_GET
@capability("maintenance_view")
@never_cache
def dashboard(request):
    from django.db.models import Count
    rows = DataHealthIssue.objects.values("severity","status").annotate(n=Count("id"))
    return json_no_store({
        "total":DataHealthIssue.objects.count(),
        "counts":[{"severity":r["severity"],"status":r["status"],"count":r["n"]}
                  for r in rows],
        "open":DataHealthIssue.objects.filter(status="open").count(),
        "exceptions":DataHealthIssue.objects.filter(status="exception").count(),
        "resolved":DataHealthIssue.objects.filter(status="resolved").count(),
        "latest_scan":str(DataHealthIssue.objects.order_by("-last_detected_at")
                         .values_list("last_scan_id", flat=True).first() or ""),
        "migration_preview":"/api/v1/maintenance/migrations",
    })


@require_GET
@capability("maintenance_view")
@never_cache
def issues(request):
    status = request.GET.get("status","all")
    severity = request.GET.get("severity","all")
    category = request.GET.get("category","all")
    if (status not in STATUSES | {"all"}
            or severity not in set(__import__("config.data_health_services", fromlist=["SEVERITIES"]).SEVERITIES.values()) | {"all"}
            or category not in CATEGORIES | {"all"}):
        return json_no_store({"error":"invalid_filter"},400)
    try:
        page = int(request.GET.get("page","1"))
        if not 1 <= page <= 10000:
            raise ValueError()
    except ValueError:
        return json_no_store({"error":"invalid_page"},400)
    q = DataHealthIssue.objects.select_related("assigned_to")
    if status != "all":
        q = q.filter(status=status)
    if severity != "all":
        q = q.filter(severity=severity)
    if category != "all":
        q = q.filter(category=category)
    q = q.order_by("-last_detected_at", "public_id")
    return json_no_store({"results":[_serialize(issue) for issue in q[(page-1)*50:page*50]],
                          "page":page,"page_size":50,"total":q.count()})


@require_GET
@capability("maintenance_view")
@never_cache
def detail(request, public_id):
    issue = get_object_or_404(DataHealthIssue.objects.select_related("assigned_to"),public_id=public_id)
    events = issue.events.select_related("actor").order_by("created_at","id")
    return json_no_store({"issue":_serialize(issue),"history":[{
        "at":event.created_at.isoformat(),
        "actor":event.actor.username if event.actor_id else "system",
        "action":event.action,"detail":event.detail,
    } for event in events]})


@require_POST
@csrf_protect
@capability("maintenance_triage")
@never_cache
def run_scan(request):
    payload = read_json(request)
    if payload is None or payload:
        return json_no_store({"error":"expected_empty_json"},400)
    try:
        result = scan(actor=request.user)
    except HealthScanInProgress:
        return json_no_store({"error":"scan_in_progress"},409)
    return json_no_store(result,201)


@require_http_methods(["PATCH"])
@csrf_protect
@capability("maintenance_triage")
@never_cache
def update_issue(request, public_id):
    payload = read_json(request)
    if payload is None or not payload or set(payload) - {"status","assigned_to","rationale","review_after"}:
        return json_no_store({"error":"invalid_payload"},400)
    status = payload.get("status")
    if status is not None and status not in STATUSES:
        return json_no_store({"error":"invalid_status"},400)
    assignee_marker = payload.get("assigned_to", "__absent__")
    assignee = None
    if assignee_marker != "__absent__":
        if assignee_marker is not None and (not isinstance(assignee_marker,str) or
                not 1 <= len(assignee_marker) <= 150):
            return json_no_store({"error":"invalid_assignee"},400)
        if assignee_marker is not None:
            assignee = get_user_model().objects.filter(username=assignee_marker,is_active=True).first()
            if assignee is None or not assignee.has_perm("auth.maintenance_view"):
                return json_no_store({"error":"assignee_requires_maintenance_view"},400)
    rationale = payload.get("rationale")
    if rationale is not None and (not isinstance(rationale,str) or len(rationale) > 1200):
        return json_no_store({"error":"invalid_rationale"},400)
    review_after = None
    if "review_after" in payload:
        raw = payload["review_after"]
        if not isinstance(raw,str):
            return json_no_store({"error":"invalid_review_date"},400)
        try:
            review_after = date.fromisoformat(raw)
        except ValueError:
            return json_no_store({"error":"invalid_review_date"},400)
        if review_after <= date.today():
            return json_no_store({"error":"review_date_must_be_future"},400)
    if status == "exception" and (not rationale or not rationale.strip() or not review_after):
        return json_no_store({"error":"exception_requires_rationale_and_review_date"},400)
    if status != "exception" and ("review_after" in payload or "rationale" in payload):
        return json_no_store({"error":"rationale_only_for_exception"},400)
    issue = get_object_or_404(DataHealthIssue, public_id=public_id)
    from .data_health_services import _UNSET
    try:
        updated, changed = triage(
            issue,actor=request.user,status=status,
            assignee=(_UNSET if assignee_marker == "__absent__" else assignee),
            rationale=rationale,review_after=review_after,
        )
    except ValueError as exc:
        return json_no_store({"error":str(exc)},400)
    return json_no_store({"issue":_serialize(updated),"changed":changed})


@require_GET
@capability("maintenance_view")
@never_cache
def migrations(request):
    """No direct production apply: only link to the governed operator procedure."""
    from .models import ProductionMigrationReceipt
    return json_no_store({
        "registered":["model-v1-to-v2@1"],
        "verified_receipt_count":ProductionMigrationReceipt.objects.count(),
        "production_apply":"disabled_in_web_api",
        "requires":"staging_frontend_acceptance_and_verified_recovery",
        "operator_guide":"docs/migration-production.md",
    })
