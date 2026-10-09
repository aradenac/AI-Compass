"""PLAT-09 server taxonomy: authority, cycles, stable paths, history and ordering."""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase

from config.identity import ensure_roles
from config.models import CatalogItem, CatalogRevision, TaskNode, TaskStructureRevision

BASE = "/api/v1/tasks"
PASSWORD = "Test-Passphrase-2026-For-Taxonomy!"


class TaskTaxonomyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        cls.writer = get_user_model().objects.create_user("task-writer", password=PASSWORD)
        cls.writer.groups.add(Group.objects.get(name="contributor"))
        cls.reader = get_user_model().objects.create_user("task-reader", password=PASSWORD)
        cls.reader.groups.add(Group.objects.get(name="user"))

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.client.force_login(self.writer)
        self.csrf = self.client.cookies["csrftoken"].value

    def post(self, body, csrf=True):
        headers = {"HTTP_X_CSRFTOKEN": self.csrf} if csrf else {}
        return self.client.post(BASE, json.dumps(body), content_type="application/json", **headers)

    def patch(self, id, body, csrf=True):
        headers = {"HTTP_X_CSRFTOKEN": self.csrf} if csrf else {}
        return self.client.patch(BASE + "/" + id, json.dumps(body), content_type="application/json", **headers)

    def create(self, name, parent=None, before=None, properties=None):
        result = self.post({"name": name, "parent_id": parent, "before": before,
                            "properties": properties or {}})
        self.assertEqual(result.status_code, 201, result.content)
        return result.json()

    def test_server_is_empty_and_requires_real_identity(self):
        self.assertEqual(self.client.get(BASE).json(), {"results": []})
        anon = Client()
        self.assertEqual(anon.get(BASE).status_code, 401)
        self.assertEqual(anon.post(BASE, "{}",
            content_type="application/json").status_code, 401)
        self.assertEqual(CatalogItem.objects.filter(type_slug="task").count(), 0)

    def test_parent_move_rename_history_unknown_json_and_paths(self):
        root = self.create("Software Development", properties={
            "phase": "SWE", "future_extension": {"nested": ["preserve", None]}})
        child = self.create("Embedded", parent=root["id"])
        sibling = self.create("Systems Engineering")
        grandchild = self.create("Driver KSZ8851", parent=child["id"])
        self.assertTrue(all(row["id"].startswith("tsk-") for row in (root, child, sibling, grandchild)))
        # Must preserve UUID and public ID while revising content and ancestry.
        update = self.patch(child["id"], {
            "expected_revision": child["revision"], "name": "Embedded MCU",
            "parent_id": sibling["id"], "properties": {"desc": "RTOS and MCU"},
        })
        self.assertEqual(update.status_code, 200, update.content)
        revised = update.json()["task"]
        self.assertEqual(revised["revision"], "r002")
        self.assertEqual(revised["uuid"], child["uuid"])
        self.assertEqual(revised["id"], child["id"])
        self.assertEqual(revised["parent_id"], sibling["id"])
        self.assertEqual(self.client.get(BASE + "/" + grandchild["id"]).json()["parent_id"], child["id"])
        self.assertEqual(self.client.get(BASE + "/" + child["id"] + "/revisions/1").json()["parent_id"], root["id"])
        self.assertEqual(self.client.get(BASE + "/" + child["id"] + "/revisions/2").json()["parent_id"], sibling["id"])
        self.assertEqual(self.client.get(BASE + "/" + child["id"] + "/revisions").json()["revisions"][0]["name"], "Embedded")
        self.assertEqual(self.client.get(BASE + "/" + root["id"]).json()["properties"]["future_extension"],
                         {"nested": ["preserve", None]})
        self.assertEqual(self.patch(child["id"], {"expected_revision": "r001", "name": "stale"}).status_code, 409)
        # Neither rename nor reparent changes a permanent child link.
        self.assertEqual(TaskNode.objects.filter(parent__item__public_id=child["id"]).count(), 1)

    def test_order_shifts_append_revisions_and_reject_bad_ancestry(self):
        root = self.create("Root")
        a = self.create("A", parent=root["id"])
        b = self.create("B", parent=root["id"])
        c = self.create("C", parent=root["id"], before=b["id"])
        self.assertEqual(c["position"], 1)
        rows = {x["name"]: x for x in self.client.get(BASE).json()["results"]}
        self.assertEqual([rows[x]["position"] for x in ("A", "C", "B")], [0, 1, 2])
        self.assertEqual(rows["B"]["revision"], "r002")
        self.assertEqual(self.client.get(BASE + "/" + b["id"] + "/revisions/1").json()["position"], 1)
        self.assertEqual(self.client.get(BASE + "/" + b["id"] + "/revisions/2").json()["position"], 2)
        move = self.patch(a["id"], {"expected_revision": rows["A"]["revision"],
                                     "parent_id": root["id"], "before": b["id"]})
        self.assertEqual(move.status_code, 200)
        self.assertEqual(move.json()["task"]["position"], 1)
        expected = [("C", 0), ("A", 1), ("B", 2)]
        actual = sorted((row["name"], row["position"]) for row in self.client.get(BASE).json()["results"]
                        if row["parent_id"] == root["id"])
        self.assertEqual(sorted(expected), actual)
        self.assertEqual(self.patch(root["id"], {"expected_revision": "r001",
            "parent_id": a["id"]}).status_code, 400)
        self.assertEqual(self.patch(a["id"], {"expected_revision": "r002",
            "parent_id": "tsk-non-existent"}).status_code, 400)
        self.assertEqual(self.patch(a["id"], {"expected_revision": "r002",
            "parent_id": a["id"]}).status_code, 400)
        self.assertEqual(self.post({"name": "X", "before": b["id"]}).status_code, 400)
        self.assertEqual(self.client.get(BASE + "/" + root["id"]).json()["parent_id"], None)

    def test_csrf_read_only_user_and_forbidden_payloads(self):
        root = self.create("Root")
        self.assertEqual(self.post({"name": "CSRF"}, csrf=False).status_code, 403)
        self.assertEqual(self.patch(root["id"], {"expected_revision": "r001", "name": "Bad"},
                                    csrf=False).status_code, 403)
        self.assertEqual(self.post({"name": "N", "unexpected": 123}).status_code, 400)
        self.assertEqual(self.post({"name": "N", "properties": {"baseline": -5}}).status_code, 400)
        self.assertEqual(self.patch(root["id"], {"expected_revision": "r001", "name": 12}).status_code, 400)
        self.assertEqual(self.client.delete(BASE + "/" + root["id"]).status_code, 405)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(BASE).status_code, 200)
        self.assertEqual(self.client.get(BASE + "/" + root["id"] + "/revisions").status_code, 200)
        self.assertEqual(self.post({"name": "Denied"}).status_code, 403)
        self.assertEqual(self.patch(root["id"], {"expected_revision": "r001",
            "name": "Denied"}).status_code, 403)
        self.assertEqual(self.client.get(BASE + "/" + root["id"]).json()["name"], "Root")

    def test_structure_history_is_immutable_at_db_level(self):
        node = self.create("Root")
        row = TaskStructureRevision.objects.get(revision__item__public_id=node["id"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                row.position = 100
                row.save(update_fields=["position"])
        self.assertEqual(TaskStructureRevision.objects.get(pk=row.pk).position, 0)
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=node["id"]).count(), 1)

    def test_idempotent_patch_does_not_append_version(self):
        root = self.create("Root", properties={"custom": {"opaque": True}})
        res = self.patch(root["id"], {"expected_revision": root["revision"], "properties": {}})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertFalse(res.json()["changed"])
        self.assertEqual(self.client.get(BASE + "/" + root["id"]).json()["revision"], "r001")
