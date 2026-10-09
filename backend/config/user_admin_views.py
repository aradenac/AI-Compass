"""PLAT-28: audited, least-privilege management of real Django accounts.

This API is intentionally independent of business_read and maintenance_view.
"""
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction, connection
from django.http import HttpResponseNotAllowed
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .auth_views import capability, json_no_store, read_json
from .identity import ROLES
from .models import UserAccessAuditEvent

User = get_user_model()
ADMIN_LOCK = 280028  # Serialize role changes and last-administrator protection.


def _error(message, status=400):
    return json_no_store({"error": message}, status=status)


def _roles(user):
    return sorted(user.groups.values_list("name", flat=True))


def _record(user):
    return {"id": user.pk, "username": user.username, "email": user.email,
            "active": user.is_active, "roles": _roles(user),
            "created_at": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None}


def _validate_roles(value, actor):
    if not isinstance(value, list) or not value or len(value) != len(set(
            repr(v) for v in value)) or not all(isinstance(v, str) and v in ROLES for v in value):
        raise ValueError("invalid_roles")
    if "platform-admin" in value and not actor.has_perm("auth.platform_manage"):
        raise PermissionError("platform_role_requires_platform_manage")
    return sorted(value)


def _can_modify_target(actor, target, new_roles):
    if actor.pk == target.pk:
        raise PermissionError("cannot_manage_own_account")
    if target.is_staff or target.is_superuser or target.user_permissions.exists():
        raise PermissionError("privileged_django_account_protected")
    current = _roles(target)
    if any(r not in ROLES for r in current):
        raise PermissionError("nonstandard_role_protected")
    if "platform-admin" in current or "platform-admin" in new_roles:
        if not actor.has_perm("auth.platform_manage"):
            raise PermissionError("platform_role_requires_platform_manage")


def _set_roles(user, roles):
    user.groups.set(Group.objects.filter(name__in=roles))


def _lock():
    # One lock for create/edit: last active account with users.manage can never be disabled.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [ADMIN_LOCK])


def _has_active_admin(excluding=None):
    admins = User.objects.filter(is_active=True, groups__name="user-admin").distinct()
    if excluding is not None:
        admins = admins.exclude(pk=excluding)
    return admins.exists()


@require_http_methods(["GET", "POST"])
@csrf_protect
@capability("users_manage")
@never_cache
def collection(request):
    if request.method == "GET":
        query = request.GET.get("search", "").strip()
        status = request.GET.get("status", "all")
        if len(query) > 100 or status not in ("all", "active", "inactive"):
            return _error("invalid_filters")
        rows = User.objects.all().order_by("username", "pk")
        if query:
            from django.db.models import Q
            rows = rows.filter(Q(username__icontains=query) | Q(email__icontains=query))
        if status != "all":
            rows = rows.filter(is_active=(status == "active"))
        # Paged results; explicit total permits clients to display truncation.
        try:
            page = int(request.GET.get("page", "1"))
            if page < 1 or page > 10000:
                raise ValueError()
        except ValueError:
            return _error("invalid_page")
        offset = (page - 1) * 50
        return json_no_store({"results": [_record(x) for x in rows[offset:offset + 50]],
                              "total": rows.count(), "page": page, "page_size": 50,
                              "available_roles": sorted(ROLES)})

    data = read_json(request)
    if data is None or set(data) - {"username", "email", "password", "roles"}:
        return _error("invalid_payload")
    username, email, password = data.get("username"), data.get("email", ""), data.get("password")
    if not isinstance(username, str) or not username.strip() or username != username.strip() or len(username) > 150:
        return _error("invalid_username")
    if not isinstance(email, str) or len(email) > 254:
        return _error("invalid_email")
    if not isinstance(password, str) or len(password) > 4096:
        return _error("password_required")
    try:
        roles = _validate_roles(data.get("roles"), request.user)
    except ValueError as exc:
        return _error(str(exc))
    except PermissionError as exc:
        return _error(str(exc), 403)
    candidate = User(username=username, email=email)
    try:
        candidate.full_clean(exclude=["password"], validate_unique=False)
        password_validation.validate_password(password, candidate)
    except Exception as exc:
        from django.core.exceptions import ValidationError
        if isinstance(exc, ValidationError):
            return _error("invalid_account: " + "; ".join(exc.messages))
        raise
    try:
        with transaction.atomic():
            _lock()
            candidate.set_password(password)
            candidate.is_staff = False
            candidate.is_superuser = False
            candidate.save()
            _set_roles(candidate, roles)
            UserAccessAuditEvent.objects.create(actor=request.user, subject=candidate,
                action="account_created", details={"roles": roles, "active": True})
    except IntegrityError:
        return _error("username_exists", 409)
    return json_no_store({"user": _record(candidate)}, 201)


@require_http_methods(["PATCH"])
@csrf_protect
@capability("users_manage")
@never_cache
def detail(request, user_id):
    data = read_json(request)
    if data is None or not data or set(data) - {"active", "roles", "password"}:
        return _error("invalid_payload")
    if "active" in data and not isinstance(data["active"], bool):
        return _error("invalid_active")
    if "password" in data and (not isinstance(data["password"], str) or len(data["password"]) > 4096):
        return _error("invalid_password")
    try:
        with transaction.atomic():
            _lock()
            target = User.objects.select_for_update().filter(pk=user_id).first()
            if target is None:
                return _error("user_not_found", 404)
            old_roles = _roles(target)
            roles = (_validate_roles(data["roles"], request.user) if "roles" in data else old_roles)
            _can_modify_target(request.user, target, roles)
            new_active = data.get("active", target.is_active)
            if (target.is_active and "user-admin" in old_roles and
                    (not new_active or "user-admin" not in roles) and
                    not _has_active_admin(excluding=target.pk)):
                return _error("last_user_admin_protected", 409)
            changes = {}
            if new_active != target.is_active:
                changes["active"] = {"from": target.is_active, "to": new_active}
                target.is_active = new_active
            if roles != old_roles:
                changes["roles"] = {"from": old_roles, "to": roles}
            if "password" in data:
                try:
                    password_validation.validate_password(data["password"], target)
                except Exception as exc:
                    from django.core.exceptions import ValidationError
                    if isinstance(exc, ValidationError):
                        return _error("invalid_password: " + "; ".join(exc.messages))
                    raise
                target.set_password(data["password"])
                changes["credentials"] = "reset"  # Never persist or echo secrets.
            if not changes:
                return json_no_store({"user": _record(target), "changed": False})
            target.save()
            if "roles" in changes:
                _set_roles(target, roles)
            UserAccessAuditEvent.objects.create(actor=request.user, subject=target,
                action="account_updated", details=changes)
            return json_no_store({"user": _record(target), "changed": True})
    except ValueError as exc:
        return _error(str(exc))
    except PermissionError as exc:
        return _error(str(exc), 403)


@require_GET
@capability("users_manage")
@never_cache
def audit(request):
    events = UserAccessAuditEvent.objects.select_related("actor", "subject").order_by("-created_at", "-id")[:100]
    return json_no_store({"results": [
        {"id": str(event.pk), "at": event.created_at.isoformat(),
         "actor": event.actor.username, "subject": event.subject.username,
         "action": event.action, "details": event.details} for event in events
    ]})
