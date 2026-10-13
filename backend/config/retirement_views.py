"""FUT-18: maintenance/Governance retirement, orphan inventory and purge API.

Read/preview and destructive purge are separate permissions: a Data Maintainer's
read-only ability never implies physical-deletion authority.
"""
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .auth_views import capability, json_no_store, read_json
from .models import CatalogItem, PurgeCandidate, PurgeReceipt, RetirementEvent
from .retirement_services import (
    DEFAULT_GRACE_DAYS, PURGE_CLASSES, RetirementError, PurgeRefused,
    configure_policy, inventory, policy, preview, purge, restore, retire,
    serialize_policy, serialize_receipt,
)


@require_GET
@capability("maintenance_view")
@never_cache
def orphan_inventory(request):
    return json_no_store({"results": inventory()})


@require_GET
@capability("maintenance_view")
@never_cache
def purge_preview(request):
    return json_no_store(preview())


@require_GET
@capability("maintenance_view")
@never_cache
def purge_policy(request):
    return json_no_store({"policy": serialize_policy(policy()),
                          "eligible_classes": sorted(PURGE_CLASSES),
                          "default_grace_days": DEFAULT_GRACE_DAYS})


@require_http_methods(["PATCH", "PUT"])
@csrf_protect
@capability("purge_manage")
@never_cache
def update_policy(request):
    payload = read_json(request)
    if payload is None or set(payload) - {"enabled", "grace_days", "eligible_classes", "cadence_hours"}:
        return json_no_store({"error": "invalid_payload"}, 400)
    try:
        row = configure_policy(
            actor=request.user,
            enabled=bool(payload.get("enabled", False)),
            grace_days=payload.get("grace_days", DEFAULT_GRACE_DAYS),
            eligible_classes=payload.get("eligible_classes", []),
            cadence_hours=payload.get("cadence_hours", 168),
        )
    except RetirementError as exc:
        return json_no_store({"error": "invalid_policy", "detail": str(exc)}, 400)
    return json_no_store({"policy": serialize_policy(row)}, 201)


@require_POST
@csrf_protect
@capability("purge_manage")
@never_cache
def run_purge(request):
    payload = read_json(request)
    if payload is None or set(payload) - {"subjects", "confirm"}:
        return json_no_store({"error": "invalid_payload"}, 400)
    subjects = payload.get("subjects")
    if not isinstance(subjects, list) or not subjects or not all(
            isinstance(s, str) and 1 <= len(s) <= 140 for s in subjects):
        return json_no_store({"error": "invalid_subjects"}, 400)
    try:
        receipt = purge(actor=request.user, subjects=subjects,
                        token=payload.get("confirm"))
    except PurgeRefused as exc:
        return json_no_store({"error": "purge_refused", "detail": str(exc)}, 400)
    return json_no_store({"receipt": serialize_receipt(receipt)}, 201)


@require_GET
@capability("maintenance_view")
@never_cache
def purge_receipts(request):
    rows = PurgeReceipt.objects.order_by("-created_at")[:50]
    return json_no_store({"results": [serialize_receipt(r) for r in rows]})


def _serialize_retirement(record):
    return {"public_id": record.public_id, "item": record.item.public_id,
            "action": record.action, "reason": record.reason,
            "actor": record.actor.get_username(),
            "retired_at": record.retired_at.isoformat()}


@require_POST
@csrf_protect
@capability("retirement_manage")
@never_cache
def retire_item(request, public_id):
    payload = read_json(request)
    if payload is None or set(payload) - {"reason"}:
        return json_no_store({"error": "invalid_payload"}, 400)
    item = get_object_or_404(CatalogItem, public_id=public_id)
    try:
        record = retire(actor=request.user, item=item,
                        reason=payload.get("reason", "") or "")
    except RetirementError as exc:
        return json_no_store({"error": "retirement_refused", "detail": str(exc)}, 409)
    return json_no_store({"retirement": _serialize_retirement(record)}, 201)


@require_POST
@csrf_protect
@capability("retirement_manage")
@never_cache
def restore_item(request, public_id):
    payload = read_json(request)
    if payload is None or set(payload) - {"reason"}:
        return json_no_store({"error": "invalid_payload"}, 400)
    item = get_object_or_404(CatalogItem, public_id=public_id)
    try:
        restore(actor=request.user, item=item, reason=payload.get("reason", "") or "")
    except RetirementError as exc:
        return json_no_store({"error": "restore_refused", "detail": str(exc)}, 409)
    return json_no_store({"restored": public_id})


@require_GET
@capability("maintenance_view")
@never_cache
def retirement_history(request, public_id):
    item = get_object_or_404(CatalogItem, public_id=public_id)
    events = RetirementEvent.objects.filter(item=item).order_by("created_at")
    return json_no_store({"item": public_id, "history": [{
        "action": e.action, "reason": e.reason, "detail": e.detail,
        "actor": e.actor.get_username() if e.actor else None,
        "at": e.created_at.isoformat(),
    } for e in events]})
