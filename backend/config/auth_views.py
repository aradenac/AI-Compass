"""CSRF-protected, same-origin Django-session authentication endpoints."""
import json
from functools import wraps

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

CAPABILITY_NAMESPACE = "auth."


def json_no_store(payload, status=200):
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


def capability(code):
    """Enforce permissions server-side on ALL HTTP paths (including direct API)."""
    def decorate(view):
        @wraps(view)
        def guarded(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return json_no_store({"error": "authentication_required"}, status=401)
            if not request.user.has_perm(CAPABILITY_NAMESPACE + code):
                return json_no_store({"error": "permission_denied"}, status=403)
            return view(request, *args, **kwargs)
        return guarded
    return decorate


def account_payload(user):
    return {
        "authenticated": True,
        "username": user.get_username(),
        "roles": sorted(user.groups.values_list("name", flat=True)),
        "permissions": sorted(
            code.removeprefix(CAPABILITY_NAMESPACE)
            for code in user.get_all_permissions()
            if code.startswith(CAPABILITY_NAMESPACE)
        ),
    }


@require_GET
@ensure_csrf_cookie
@never_cache
def csrf_token(request):
    return json_no_store({"csrfToken": get_token(request)})


@require_GET
@never_cache
def account(request):
    if not request.user.is_authenticated:
        return json_no_store({"authenticated": False, "roles": [], "permissions": []})
    return json_no_store(account_payload(request.user))


def read_json(request):
    if len(request.body) > 4096:
        return None
    try:
        value = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


@require_POST
@csrf_protect
@never_cache
def sign_in(request):
    payload = read_json(request)
    if payload is None:
        return json_no_store({"error": "invalid_payload"}, status=400)
    username, password = payload.get("username"), payload.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return json_no_store({"error": "invalid_payload"}, status=400)
    if len(username) > 150 or len(password) > 4096:
        return json_no_store({"error": "invalid_credentials"}, status=401)
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return json_no_store({"error": "invalid_credentials"}, status=401)
    login(request, user)
    return json_no_store(account_payload(user))


@require_POST
@csrf_protect
@never_cache
def sign_out(request):
    logout(request)
    return json_no_store({"authenticated": False})


@require_GET
@capability("business_read")
@never_cache
def sandbox(request):
    return json_no_store({
        "kind": "permission_sandbox",
        "note": "PLAT-02 authorization example, not a catalog record.",
        "write_count": request.session.get("business_write_probe_count", 0),
    })


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def sandbox_update(request):
    count = request.session.get("business_write_probe_count", 0) + 1
    request.session["business_write_probe_count"] = count
    return json_no_store({"write_count": count, "persisted_in": "authenticated_session"})


@require_GET
@capability("maintenance_view")
@never_cache
def maintenance_landing(request):
    return json_no_store({
        "workspace": "Maintenance & Governance",
        "message": "Identity verified. Data-health checks arrive in PLAT-27.",
    })


@require_GET
@capability("users_manage")
@never_cache
def user_admin_landing(request):
    return json_no_store({
        "workspace": "Users & Access",
        "message": "Permission granted. Account-management UI arrives in PLAT-28.",
    })


@require_GET
@capability("platform_view")
@never_cache
def platform_landing(request):
    return json_no_store({
        "workspace": "Platform Operations",
        "message": "Operator access verified. Deployment is managed from the host.",
    })
