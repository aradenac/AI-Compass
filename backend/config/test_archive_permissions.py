"""FUT-02: read-only platform and maintenance roles must not create/get archives."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase

from .identity import ensure_roles
from .models import UserAccessAuditEvent

ROOT = "/api/v1/archives/native"
INVENTORY = "/api/v1/archives"


class ArchiveRoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U = get_user_model()
        cls.viewer = U.objects.create_user("platform-readonly", password="non-production")
        cls.viewer.user_permissions.add(Permission.objects.get(codename="platform_view"))
        cls.controller = U.objects.create_user("platform-manage-not-export", password="non-production")
        cls.controller.user_permissions.add(Permission.objects.get(codename="platform_manage"))
        cls.maintainer = U.objects.create_user("data-maintainer-readonly", password="non-production")
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))
        cls.operator = U.objects.create_user("archive-operator-only", password="non-production")
        cls.operator.groups.add(Group.objects.get(name="archive-operator"))
        cls.platform = U.objects.create_user("platform-admin-archive", password="non-production")
        cls.platform.groups.add(Group.objects.get(name="platform-admin"))

    def test_inventory_is_not_export_authorization(self):
        c = Client()
        self.assertEqual(c.get(INVENTORY).status_code, 401)
        self.assertEqual(c.get(ROOT).status_code, 401)
        for user in (self.viewer, self.controller, self.maintainer):
            c.force_login(user)
            self.assertEqual(c.get(ROOT).status_code, 403)
        c.force_login(self.viewer)
        status = c.get(INVENTORY)
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["native"]["can_export"])
        self.assertEqual(status.json()["complete_recovery"]["http_download"], "not_yet_available")
        self.assertNotIn("password", status.content.decode())
        c.force_login(self.maintainer)
        self.assertEqual(c.get(INVENTORY).status_code, 403)

    def test_explicit_export_grant_and_disabled_identity_are_checked_before_build(self):
        with patch("config.archive_views.build_native_export") as build:
            c = Client()
            for user in (self.operator, self.platform):
                c.force_login(user)
                self.assertTrue(c.get(INVENTORY).json()["native"]["can_export"])
                self.assertEqual(c.get(ROOT + "?unsafe=1").status_code, 400)
                build.assert_not_called()
            c.force_login(self.operator)
            self.operator.is_active = False
            self.operator.save(update_fields=["is_active"])
            self.assertEqual(c.get(ROOT).status_code, 401)
            build.assert_not_called()

    def test_role_baseline_has_distinct_archive_permission(self):
        self.assertFalse(self.viewer.has_perm("auth.archive_export"))
        self.assertFalse(self.controller.has_perm("auth.archive_export"))
        self.assertTrue(self.operator.has_perm("auth.archive_export"))
        self.assertTrue(self.platform.has_perm("auth.archive_export"))
