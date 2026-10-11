"""FUT-01: additive, stable v1 API compatibility declaration and error representation.

The existing /api/v1 business endpoints remain unchanged. Clients negotiate
before login/data requests; missing/invalid major versions fail closed.
"""
from django.http import JsonResponse

API_MAJOR = 1
API_MIN_MAJOR = 1
API_MAX_MAJOR = 1
CONTRACT_SCHEMA = "ai-compass/api-contract@1"


def contract_document():
    return {
        "schema": CONTRACT_SCHEMA,
        "api_major": API_MAJOR,
        "supported_client_api_majors": [1],
        "min_client_api_major": API_MIN_MAJOR,
        "max_client_api_major": API_MAX_MAJOR,
        "compatible": True,
        "capabilities": ["health", "auth", "models", "catalog", "tasks",
                         "test_cases", "campaigns", "runs", "evidence", "results",
                         "updates"],
        "error_contract": "ai-compass/api-error@1",
    }


def error_payload(code, detail="", *, status=400):
    """Opt-in, typed errors for new endpoints; old {error: "code"} stays supported."""
    return JsonResponse({
        "error": {"schema": "ai-compass/api-error@1", "code": str(code),
                  "detail": str(detail)},
    }, status=status)
