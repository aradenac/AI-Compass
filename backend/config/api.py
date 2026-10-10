"""Health-only API for the first infrastructure increment."""
from django.db import DatabaseError, connection
from ninja import NinjaAPI
from .release_contract import contract_document

api = NinjaAPI(title="AI Compass API", version="1.0.0", urls_namespace="api_v1")


@api.get("/health", response={200: dict, 503: dict}, auth=None)
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return 503, {"status": "unavailable", "database": "unavailable"}
    return 200, {"status": "ok", "database": "ok"}


@api.get("/contract", response={200: dict}, auth=None)
def contract(request):
    """Version/capability handshake; safe before authentication."""
    return contract_document()
