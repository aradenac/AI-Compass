"""UX-R06: read-only published Workgroup Updates endpoint.

Business-read is required and is the only capability used; this endpoint grants
no Workgroup editing, planning, publication or administrative access, and it
never returns a cross-mode or Demo value.
"""
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .auth_views import capability, json_no_store
from . import updates_services as svc


@require_GET
@never_cache
@capability("business_read")
def collection(request):
    if request.GET:
        return json_no_store({"error": "invalid_filter"}, 400)
    return json_no_store(svc.collection())
