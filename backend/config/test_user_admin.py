"""PLAT-28: permission boundaries, CSRF, role elevation, revocation and audit."""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.models import Session
from django.db import DatabaseError, transaction
from django.test import Client, TestCase

from .identity import ensure_roles
from .models import UserAccessAuditEvent

BASE = "/api/v1/admin/users"
PASSWORD = "LongSecretPhrase-2026-Testing!#"


class UserAdministrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        cls.admin = User.objects.create_user("accounts-admin", password=PASSWORD)
        cls.admin.groups.add(Group.objects.get(name="user-admin"))
        cls.maintainer = User.objects.create_user("data-operator", password=PASSWORD)
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))
        cls.platform = User.objects.create_user("platform-operator", password=PASSWORD)
        cls.platform.groups.add(Group.objects.get(name="platform-admin"))
        cls.dual = User.objects.create_user("dual-admin", password=PASSWORD)
        cls.dual.groups.add(Group.objects.get(name="user-admin"), Group.objects.get(name="platform-admin"))
        cls.member = User.objects.create_user("engineer", password=PASSWORD)
        cls.member.groups.add(Group.objects.get(name="contributor"))

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.csrf = self.client.cookies["csrftoken"].value
        self.client.force_login(self.admin)

    def post(self, payload, csrf=True):
        return self.client.post(BASE, data=json.dumps(payload), content_type="application/json",
            **({"HTTP_X_CSRFTOKEN": self.csrf} if csrf else {}))

    def patch(self, user_id, payload, csrf=True):
        return self.client.patch(f"{BASE}/{user_id}", data=json.dumps(payload),
            content_type="application/json",
            **({"HTTP_X_CSRFTOKEN": self.csrf} if csrf else {}))

    def test_create_list_search_and_protect_credentials(self):
        response = self.post({"username": "new-engineer", "email": "dev@example.test",
                              "roles": ["user"], "password": PASSWORD})
        self.assertEqual(response.status_code, 201, response.content)
        new = get_user_model().objects.get(username="new-engineer")
        self.assertTrue(new.check_password(PASSWORD))
        self.assertFalse(new.is_staff)
        self.assertFalse(new.is_superuser)
        self.assertEqual(list(new.groups.values_list("name", flat=True)), ["user"])
        self.assertNotIn("password", str(response.content).lower())
        self.assertEqual(self.client.get(BASE + "?search=new-eng&status=active").json()["total"], 1)
        self.assertEqual(self.client.get(BASE + "?search=new-eng&status=inactive").json()["total"], 0)
        self.assertEqual(self.client.get(BASE + "?page=0").status_code, 400)
        audit = self.client.get(BASE + "/audit").json()["results"]
        self.assertEqual(audit[0]["actor"], self.admin.username)
        self.assertEqual(audit[0]["subject"], new.username)
        self.assertEqual(audit[0]["action"], "account_created")
        self.assertNotIn(PASSWORD, json.dumps(audit))

    def test_grant_and_revoke_are_effective_on_subsequent_requests(self):
        engineer = self.member
        session = Client()
        session.force_login(engineer)
        self.assertEqual(session.get("/api/v1/models").status_code, 200)
        result = self.patch(engineer.pk, {"roles": ["data-maintainer"], "active": True})
        self.assertEqual(result.status_code, 200, result.content)
        self.assertTrue(result.json()["changed"])
        self.assertEqual(session.get("/api/v1/models").status_code, 403)
        self.assertEqual(session.get("/api/v1/auth/maintenance").status_code, 200)
        original_session_key = session.session.session_key
        self.assertTrue(Session.objects.filter(session_key=original_session_key).exists())
        self.assertEqual(self.patch(engineer.pk, {"active": False}).status_code, 200)
        self.assertFalse(Session.objects.filter(session_key=original_session_key).exists())
        self.assertFalse(get_user_model().objects.get(pk=engineer.pk).is_active)
        denied = session.get("/api/v1/auth/maintenance")
        self.assertEqual(denied.status_code, 401, denied.content)
        self.assertFalse(session.get("/api/v1/auth/me").json()["authenticated"])
        self.assertEqual(self.client.get(BASE + "?status=inactive&search=engineer").json()["total"], 1)
        self.assertEqual(self.patch(engineer.pk, {"active": True, "roles": ["user"]}).status_code, 200)
        # Revoked login session is not resurrected after reactivation.
        self.assertEqual(session.get("/api/v1/auth/maintenance").status_code, 401)
        self.assertEqual(self.patch(engineer.pk, {"roles": ["user"]}).json()["changed"], False)
        self.assertEqual([x.action for x in UserAccessAuditEvent.objects.filter(subject=engineer)],
                         ["account_updated", "account_updated", "account_updated"])

    def test_unauthorized_role_escalation_and_cross_role_denials(self):
        self.assertEqual(self.post({"username": "future-platform", "password": PASSWORD,
                                     "roles": ["platform-admin"]}).status_code, 403)
        self.assertEqual(self.patch(self.member.pk, {"roles": ["platform-admin"]}).status_code, 403)
        self.assertEqual(self.patch(self.platform.pk, {"active": False}).status_code, 403)
        self.assertEqual(self.patch(self.admin.pk, {"active": False}).status_code, 403)
        self.client.force_login(self.maintainer)
        self.assertEqual(self.client.get(BASE).status_code, 403)
        self.assertEqual(self.client.get(BASE + "/audit").status_code, 403)
        self.assertEqual(self.post({"username": "illegal", "password": PASSWORD, "roles": ["user"]}).status_code, 403)
        self.assertEqual(self.patch(self.member.pk, {"roles": ["user"]}).status_code, 403)
        self.client.force_login(self.platform)
        self.assertEqual(self.client.get(BASE).status_code, 403)
        self.assertEqual(self.patch(self.member.pk, {"roles": ["platform-admin"]}).status_code, 403)
        self.client.logout()
        self.client.get("/api/v1/auth/csrf")
        self.csrf = self.client.cookies["csrftoken"].value
        self.assertEqual(self.client.get(BASE).status_code, 401)
        self.assertEqual(self.client.get(BASE + "/audit").status_code, 401)
        self.assertEqual(self.patch(self.member.pk, {"active": False}).status_code, 401)
        self.assertFalse(get_user_model().objects.filter(username="illegal").exists())

    def test_dual_privilege_can_manage_platform_role_but_not_own(self):
        self.client.force_login(self.dual)
        result = self.patch(self.platform.pk, {"roles": ["platform-admin", "user-admin"]})
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(set(result.json()["user"]["roles"]), {"platform-admin", "user-admin"})
        self.assertEqual(self.patch(self.dual.pk, {"roles": ["contributor"]}).status_code, 403)

    def test_last_user_admin_cannot_be_removed(self):
        self.dual.groups.remove(Group.objects.get(name="user-admin"))
        User = get_user_model()
        delegated = User.objects.create_user("delegated", password=PASSWORD)
        delegated.user_permissions.add(Permission.objects.get(codename="users_manage"))
        self.client.force_login(delegated)
        self.assertEqual(self.patch(self.admin.pk, {"active": False}).status_code, 409)
        self.assertEqual(self.patch(self.admin.pk, {"roles": ["user"]}).status_code, 409)
        self.assertTrue(User.objects.get(pk=self.admin.pk).is_active)

    def test_csrf_input_validation_and_audit_append_only(self):
        self.assertEqual(self.post({"username": "no-csrf", "password": PASSWORD,
                                     "roles": ["user"]}, csrf=False).status_code, 403)
        self.assertEqual(self.patch(self.member.pk, {"active": False}, csrf=False).status_code, 403)
        self.assertEqual(self.post({"username": "bad-roles", "password": PASSWORD,
                                     "roles": ["user", "unrecognized"]}).status_code, 400)
        self.assertEqual(self.post({"username": "weak", "password": "123",
                                     "roles": ["user"]}).status_code, 400)
        self.assertEqual(self.post({"username": self.admin.username, "password": PASSWORD,
                                     "roles": ["user"]}).status_code, 409)
        self.assertEqual(self.patch(self.member.pk, {"active": "no"}).status_code, 400)
        self.assertEqual(self.patch(self.member.pk, {"roles": []}).status_code, 400)
        self.assertEqual(self.patch(99999999, {"active": False}).status_code, 404)
        self.assertEqual(self.client.delete(BASE + f"/{self.member.pk}",
                                           HTTP_X_CSRFTOKEN=self.csrf).status_code, 405)
        self.assertEqual(self.patch(self.member.pk, {"password": PASSWORD + "NEW"}).status_code, 200)
        event = UserAccessAuditEvent.objects.latest("created_at")
        self.assertEqual(event.details["credentials"], "reset")
        self.assertNotIn(PASSWORD, json.dumps(event.details))
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                UserAccessAuditEvent.objects.filter(pk=event.pk).delete()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                UserAccessAuditEvent.objects.filter(pk=event.pk).update(details={})
        self.assertEqual(UserAccessAuditEvent.objects.count(), 1)

    def test_staff_and_direct_django_superuser_accounts_are_protected(self):
        self.member.is_staff = True
        self.member.save(update_fields=["is_staff"])
        self.assertEqual(self.patch(self.member.pk, {"active": False}).status_code, 403)
        self.member.is_staff = False
        self.member.is_superuser = True
        self.member.save(update_fields=["is_staff", "is_superuser"])
        self.assertEqual(self.patch(self.member.pk, {"roles": ["user"]}).status_code, 403)
