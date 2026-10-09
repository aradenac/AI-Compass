"""Regression coverage for PLAT-01 infrastructure and PLAT-02 RBAC/session flows."""
import io
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase

from .identity import ROLES, ensure_roles

BASE = "/api/v1/auth/"
PASSWORD = "LongSecretPhrase-2026-Testing!#"  # Test fixtures ONLY, never bootstrap secrets.


class HealthEndpointTests(TestCase):
    def test_health_reports_a_healthy_database(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_unknown_business_api_is_not_demo_data(self):
        self.assertEqual(self.client.get("/api/v1/models").status_code, 404)


class RoleAndCsrfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        for role in ROLES:
            user = User.objects.create_user(username=role, password=PASSWORD)
            user.groups.add(Group.objects.get(name=role))
        inactive = User.objects.create_user(username="inactive", password=PASSWORD)
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get(BASE + "csrf")

    def post(self, path, payload=None, csrf=True):
        headers = {}
        if csrf and "csrftoken" in self.client.cookies:
            headers["HTTP_X_CSRFTOKEN"] = self.client.cookies["csrftoken"].value
        return self.client.post(
            BASE + path,
            data=json.dumps(payload if payload is not None else {}),
            content_type="application/json",
            **headers,
        )

    def sign_in(self, username, password=PASSWORD):
        return self.post("login", {"username": username, "password": password})

    def test_anonymous_is_denied_by_all_role_boundaries(self):
        for path in ("sandbox", "maintenance", "user-admin", "platform"):
            self.assertEqual(self.client.get(BASE + path).status_code, 401, path)
        self.assertEqual(self.post("sandbox/write").status_code, 401)
        self.assertEqual(self.client.get(BASE + "me").json()["authenticated"], False)

    def test_login_requires_real_csrf_and_uses_a_httponly_session(self):
        self.assertEqual(self.post("login", {"username": "contributor", "password": PASSWORD}, csrf=False).status_code, 403)
        login = self.sign_in("contributor")
        self.assertEqual(login.status_code, 200)
        self.assertIn("contributor", login.json()["roles"])
        self.assertIn("business_write", login.json()["permissions"])
        self.assertTrue(self.client.cookies["sessionid"]["httponly"])
        self.assertIn("no-store", login["Cache-Control"])

    def test_bad_login_and_inactive_user_are_denied(self):
        self.assertEqual(self.sign_in("contributor", "incorrect").status_code, 401)
        self.assertEqual(self.sign_in("inactive").status_code, 401)
        self.assertFalse(self.client.get(BASE + "me").json()["authenticated"])

    def test_contributor_can_change_only_its_own_example_session(self):
        self.assertEqual(self.sign_in("contributor").status_code, 200)
        self.assertEqual(self.client.get(BASE + "sandbox").json()["write_count"], 0)
        self.assertEqual(self.post("sandbox/write").json()["write_count"], 1)
        self.assertEqual(self.client.get(BASE + "sandbox").json()["write_count"], 1)
        self.assertEqual(self.client.get(BASE + "maintenance").status_code, 403)
        self.assertEqual(self.client.get(BASE + "user-admin").status_code, 403)
        self.assertEqual(self.client.get(BASE + "platform").status_code, 403)

        # Direct API requests remain protected even after the UI hid buttons.
        self.assertEqual(self.post("sandbox/write", csrf=False).status_code, 403)

    def test_data_maintainer_has_no_business_or_user_admin_rights(self):
        self.assertEqual(self.sign_in("data-maintainer").status_code, 200)
        self.assertEqual(self.client.get(BASE + "maintenance").status_code, 200)
        self.assertEqual(self.client.get(BASE + "sandbox").status_code, 403)
        self.assertEqual(self.post("sandbox/write").status_code, 403)
        self.assertEqual(self.client.get(BASE + "user-admin").status_code, 403)
        self.assertEqual(self.client.get(BASE + "platform").status_code, 403)

    def test_user_admin_and_platform_admin_are_separate(self):
        self.assertEqual(self.sign_in("user-admin").status_code, 200)
        self.assertEqual(self.client.get(BASE + "user-admin").status_code, 200)
        self.assertEqual(self.client.get(BASE + "maintenance").status_code, 403)
        self.assertEqual(self.client.get(BASE + "platform").status_code, 403)
        self.assertEqual(self.sign_in("platform-admin").status_code, 200)
        self.assertEqual(self.client.get(BASE + "platform").status_code, 200)
        self.assertEqual(self.client.get(BASE + "user-admin").status_code, 403)

    def test_reviewer_cannot_mutate_business_resource(self):
        self.assertEqual(self.sign_in("reviewer").status_code, 200)
        self.assertEqual(self.client.get(BASE + "sandbox").status_code, 200)
        self.assertEqual(self.post("sandbox/write").status_code, 403)

    def test_logout_is_csrf_protected_and_revokes_session(self):
        self.assertEqual(self.sign_in("data-maintainer").status_code, 200)
        self.assertEqual(self.post("logout", csrf=False).status_code, 403)
        self.assertEqual(self.client.get(BASE + "maintenance").status_code, 200)
        self.assertEqual(self.post("logout").status_code, 200)
        self.assertEqual(self.client.get(BASE + "maintenance").status_code, 401)
        self.assertFalse(self.client.get(BASE + "me").json()["authenticated"])

    def test_malformed_login_payload_is_rejected(self):
        self.assertEqual(self.post("login", {"username": 5, "password": "test"}).status_code, 400)
        self.assertEqual(self.client.post(BASE + "login", "not json", content_type="application/json",
                         HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value).status_code, 400)


class BootstrapTests(TestCase):
    def test_role_bootstrap_is_idempotent_and_not_hierarchical(self):
        ensure_roles()
        ensure_roles()
        self.assertEqual(Group.objects.filter(name__in=ROLES).count(), len(ROLES))
        maintainer = Group.objects.get(name="data-maintainer")
        grants = set(maintainer.permissions.values_list("codename", flat=True))
        self.assertIn("maintenance_view", grants)
        self.assertNotIn("business_write", grants)
        self.assertNotIn("users_manage", grants)
        self.assertTrue(Permission.objects.filter(codename="users_manage").exists())

    def test_safe_noninteractive_account_creation_refuses_overwrite(self):
        with patch("sys.stdin", io.StringIO(PASSWORD + "\n")):
            call_command(
                "bootstrap_identity", "--username", "operator-test",
                "--role", "platform-admin", "--password-stdin", stdout=io.StringIO(),
            )
        user = get_user_model().objects.get(username="operator-test")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["platform-admin"])
        with patch("sys.stdin", io.StringIO(PASSWORD + "\n")):
            with self.assertRaises(CommandError):
                call_command(
                    "bootstrap_identity", "--username", "operator-test",
                    "--role", "user-admin", "--password-stdin", stdout=io.StringIO(),
                )
        user.refresh_from_db()
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["platform-admin"])
