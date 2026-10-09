"""Shared append-only catalog event emitter; future domains extend the projection.

Business events must be committed together with their immutable source revision.
"""
from django.db import transaction
from .models import CatalogAuditEvent


def record_catalog_event(*, item, revision, actor, action):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Audit writes must share their business transaction")
    if revision.item_id != item.pk:
        raise ValueError("Audit revision must belong to its catalog object")
    if not isinstance(action, str) or not 1 <= len(action) <= 32:
        raise ValueError("Invalid audit action")
    return CatalogAuditEvent.objects.create(
        item=item, revision=revision, actor=actor, action=action,
    )
