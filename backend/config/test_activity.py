"""PLAT-24: correlated immutable events, scoped reads, bounded exports and CSRF-safe reads."""
import csv
import io
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase
from django.utils import timezone

from .identity import ensure_roles
from .models import CatalogAuditEvent, CatalogItem, CatalogRevision, UserAccessAuditEvent

BASE = "/api/v1/activity"
PASSWORD = "Test-FeeD-Passphrase-2026-Test!"


class ActivityFeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        cls.writer = User.objects.create_user(username="feed-writer", password=PASSWORD)
        cls.writer.groups.add(Group.objects.get(name="contributor"))
        cls.reader = User.objects.create_user(username="feed-reader", password=PASSWORD)
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maintainer = User.objects.create_user(username="feed-maintainer", password=PASSWORD)
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))
        cls.admin = User.objects.create_user(username="feed-admin", password=PASSWORD)
        cls.admin.groups.add(Group.objects.get(name="user-admin"))
        cls.dual = User.objects.create_user(username="feed-dual", password=PASSWORD)
        cls.dual.groups.add(Group.objects.get(name="contributor"), Group.objects.get(name="user-admin"))

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.client.force_login(self.writer)
        self.csrf = self.client.cookies["csrftoken"].value

    def post(self, path, data):
        return self.client.post(path, data=json.dumps(data), content_type="application/json",
                                HTTP_X_CSRFTOKEN=self.csrf)

    def make_model(self, name="=1+2"):
        res = self.post("/api/v1/models", {"name": name, "properties": {"publication": "draft"}})
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()

    def test_no_fabricated_events_and_model_create_edit_publish_correlation(self):
        self.assertEqual(self.client.get(BASE).json()["results"], [])
        self.assertEqual(CatalogAuditEvent.objects.count(), 0)
        model = self.make_model()
        self.assertEqual(self.client.get(BASE).json()["results"][0]["operation"], "created")
        first = self.client.get(BASE).json()["results"][0]
        self.assertEqual(first["object_id"], model["id"])
        self.assertEqual(first["revision"], "r001")
        self.assertEqual(first["revision_id"], str(CatalogRevision.objects.get(number=1).pk))
        self.assertEqual(first["outcome"], "succeeded")
        self.assertEqual(first["actor"], "feed-writer")
        self.assertIsNone(first["actor_roles_at_event"])  # no fabricated historical role
        self.assertIsNone(first["business_unit"])
        self.assertEqual(self.client.get(BASE + "/" + first["id"]).json()["event"], first)
        change = self.post("/api/v1/models/" + model["id"] + "/revisions",
                           {"expected_revision": "r001", "name": "Driver agent"})
        self.assertEqual(change.status_code, 201, change.content)
        publish = self.post("/api/v1/models/" + model["id"] + "/revisions",
                            {"expected_revision": "r002", "properties": {"publication": "published"}})
        self.assertEqual(publish.status_code, 201, publish.content)
        data = self.client.get(BASE).json()["results"]
        self.assertEqual([e["operation"] for e in data], ["published", "revised", "created"])
        self.assertEqual([e["revision"] for e in data], ["r003", "r002", "r001"])
        self.assertEqual(len({e["revision_id"] for e in data}), 3)
        self.assertTrue(all(e["object_id"] == model["id"] for e in data))
        self.assertEqual(CatalogRevision.objects.count(), 3)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CatalogAuditEvent.objects.filter(id=data[0]["id"]).delete()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CatalogAuditEvent.objects.filter(id=data[0]["id"]).update(action="tampered")

    def test_role_boundaries_and_account_changes_never_leak_to_business_reader(self):
        model = self.make_model("Visible model")
        self.client.force_login(self.admin)
        new = self.post("/api/v1/admin/users",
                        {"username": "account-target", "password": PASSWORD, "roles": ["user"]})
        self.assertEqual(new.status_code, 201, new.content)
        target = new.json()["user"]
        updated = self.client.patch("/api/v1/admin/users/" + str(target["id"]),
            data=json.dumps({"active": False}), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(UserAccessAuditEvent.objects.count(), 2)
        access = self.client.get(BASE).json()["results"]
        self.assertEqual([r["operation"] for r in access],
                         ["account_updated", "account_created"])
        self.assertTrue(all(r["object_type"] == "access" for r in access))
        self.assertTrue(all(r["revision_id"] is None for r in access))
        self.assertEqual(self.client.get(BASE + "?type=model").status_code, 403)
        self.assertEqual(self.client.get(BASE + "/export?type=model").status_code, 403)
        self.assertEqual(self.client.get(BASE + "/export").json()["results"], access)
        detail = self.client.get(BASE + "/" + access[0]["id"]).json()
        self.assertEqual(detail["changes"]["active"]["to"], False)
        self.assertNotIn("password", json.dumps(detail))
        self.client.force_login(self.reader)
        visible = self.client.get(BASE).json()["results"]
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["object_id"], model["id"])
        self.assertEqual(self.client.get(BASE + "?type=access").status_code, 403)
        self.assertEqual(self.client.get(BASE + "/export?type=access").status_code, 403)
        self.assertEqual(self.client.get(BASE + "/" + access[0]["id"]).status_code, 404)
        self.assertNotIn("account-target", self.client.get(BASE + "/export?format=json").content.decode())
        self.client.force_login(self.maintainer)
        self.assertEqual(self.client.get(BASE).status_code, 403)
        self.assertEqual(self.client.get(BASE + "/export").status_code, 403)
        self.assertEqual(self.client.get(BASE + "/" + access[0]["id"]).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(BASE).status_code, 401)
        self.assertEqual(self.client.get(BASE + "/export").status_code, 401)

    def test_account_audit_allowlist_never_leaks_private_fields(self):
        event = UserAccessAuditEvent.objects.create(
            actor=self.admin, subject=self.reader, action="account_updated",
            details={"credentials": "reset", "private_token": "DO_NOT_SHOW",
                     "email": "private@example.test", "active": {"to": False}})
        self.client.force_login(self.admin)
        detail = self.client.get(BASE + "/" + str(event.id)).json()
        self.assertEqual(detail["changes"], {"active": {"to": False}})
        self.assertNotIn("DO_NOT_SHOW", self.client.get(BASE + "/export?format=json").content.decode())
        self.assertNotIn("private@example.test", self.client.get(BASE + "/export?format=csv").content.decode())

    def test_filters_csv_injection_and_json_exact_order(self):
        model = self.make_model()
        self.make_model("Another source")
        first = self.client.get(BASE + "?type=model&actor=feed-writer").json()["results"]
        self.assertEqual(len(first), 2)
        self.assertEqual(self.client.get(BASE + "?actor=nobody").json()["results"], [])
        self.assertEqual(len(self.client.get(BASE + "?action=created").json()["results"]), 2)
        now = timezone.now()
        old = (now - timedelta(days=365)).isoformat().replace("+00:00", "Z")
        future = (now + timedelta(days=365)).isoformat().replace("+00:00", "Z")
        self.assertEqual(self.client.get(BASE + "?from=" + future).json()["results"], [])
        self.assertEqual(len(self.client.get(BASE + "?from=" + old + "&to=" + future).json()["results"]), 2)
        self.assertEqual(self.client.get(BASE + "?from=2026-01-01T12:00:00").status_code, 400)
        self.assertEqual(self.client.get(BASE + "?from=" + future + "&to=" + old).status_code, 400)
        self.assertEqual(self.client.get(BASE + "?page=21").status_code, 400)
        self.assertEqual(self.client.get(BASE + "?unknown=anything").status_code, 400)
        self.assertEqual(self.client.get(BASE + "?type=unknown").status_code, 400)
        self.assertEqual(self.client.get(BASE + "/export?format=txt").status_code, 400)
        json_response = self.client.get(BASE + "/export?format=json&actor=feed-writer")
        self.assertEqual(json_response.status_code, 200)
        self.assertIn("no-store", json_response["Cache-Control"])
        json_ids = [x["id"] for x in json.loads(json_response.content)["results"]]
        self.assertEqual(json_ids, [x["id"] for x in first])
        csv_response = self.client.get(BASE + "/export?format=csv&actor=feed-writer")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("attachment;", csv_response["Content-Disposition"])
        rows = list(csv.DictReader(io.StringIO(csv_response.content.decode())))
        self.assertEqual([row["id"] for row in rows], json_ids)
        self.assertTrue(any(row["object_name"] == "'=1+2" for row in rows))
        self.assertEqual(CatalogItem.objects.count(), 2)
        self.assertEqual(CatalogRevision.objects.count(), 2)

    def test_bounded_paging_and_refuse_silent_partial_export(self):
        model = self.make_model("Many events")
        item = CatalogItem.objects.get(public_id=model["id"])
        event = CatalogAuditEvent.objects.get(item=item)
        # Enough committed-like append-only events to exercise the hard export limit.
        CatalogAuditEvent.objects.bulk_create([
            CatalogAuditEvent(item=item, revision=event.revision, actor=self.writer, action="observed")
            for _ in range(1001)
        ])
        page1 = self.client.get(BASE)
        self.assertEqual(page1.status_code, 200)
        self.assertEqual(len(page1.json()["results"]), 50)
        self.assertTrue(page1.json()["has_more"])
        self.assertTrue(page1.json()["limited"])
        ids = [x["id"] for x in page1.json()["results"]]
        next_page = self.client.get(BASE + "?page=2").json()["results"]
        self.assertFalse(set(ids) & {r["id"] for r in next_page})
        self.assertEqual(self.client.get(BASE + "/export").status_code, 422)
        self.assertEqual(self.client.get(BASE + "/export?format=csv").status_code, 422)
        self.assertEqual(len(self.client.get(BASE + "/export?actor=nobody").json()["results"]), 0)
