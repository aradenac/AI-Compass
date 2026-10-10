"""Independent role grants for AI Compass. Roles are NOT a hierarchy."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

# Permissions intentionally belong to the built-in auth content type until
# domain models exist; this creates no ad-hoc domain migration in PLAT-02.
PERMISSIONS = {
    "business_read": "Read permitted business records",
    "business_write": "Create or revise permitted business records",
    "publication_review": "Review and publish permitted records",
    "maintenance_view": "Inspect permitted data-health information",
    "maintenance_triage": "Triage permitted maintenance issues",
    "users_view": "Inspect accounts with authorized scope",
    "users_manage": "Manage accounts and group grants",
    "platform_view": "Inspect platform health and operations",
    "platform_manage": "Operate permitted platform configuration",
    "planning_view": "Inspect confidential workload planning profiles and rates",
    "planning_manage": "Create and revise confidential planning profiles",
}

ROLES = {
    "user": ("business_read",),
    "contributor": ("business_read", "business_write"),
    "reviewer": ("business_read", "publication_review"),
    "data-maintainer": ("maintenance_view", "maintenance_triage"),
    "user-admin": ("users_view", "users_manage"),
    "platform-admin": ("platform_view", "platform_manage"),
    "deployment-planner": ("planning_view", "planning_manage"),
}


@transaction.atomic
def ensure_roles():
    """Seed baseline roles idempotently, without deleting site-added grants."""
    content_type = ContentType.objects.get_for_model(get_user_model())
    permissions = {}
    for codename, label in PERMISSIONS.items():
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": label},
        )
        permissions[codename] = permission
    for name, capabilities in ROLES.items():
        group, _ = Group.objects.get_or_create(name=name)
        group.permissions.add(*(permissions[codename] for codename in capabilities))
