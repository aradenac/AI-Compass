"""PLAT-06: end-to-end typed catalog CRUD, RBAC, immutability and isolation."""
import json
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from .identity import ensure_roles
from .models import CatalogAuditEvent, CatalogItem, CatalogRevision, ObjectTypeVersion

CONFIG = {
    "provider": ("prv", {"hosting": "cloud", "access": "API", "pricing": "PAYG",
                          "custom": {"region": None, "levels": [1, 2]}}),
    "harness": ("hrn", {"interface": "cli", "integrations": ["terminal", "editor"],
                         "custom": {"nested": [True, None]}}),
    "framework": ("frm", {"process": "Plan-Implement-Review", "orchestration": "n8n",
                           "stages": ["plan", "implement", "review"],
                           "custom": {"participants": [{"role": "planner"}]}}),
}


class TypedCatalogApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        user = get_user_model()
        cls.writer = user.objects.create_user(username="catalog-writer", password="test")
        cls.writer.groups.add(Group.objects.get(name="contributor"))
        cls.reader = user.objects.create_user(username="catalog-reader", password="test")
        cls.reader.groups.add(Group.objects.get(name="reviewer"))
        cls.no_read = user.objects.create_user(username="catalog-maintainer", password="test")
        cls.no_read.groups.add(Group.objects.get(name="data-maintainer"))

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.writer)

    def collection(self, kind):
        return f"/api/v1/catalog/{kind}"

    def post(self, path, body, client=None):
        return (client or self.client).post(
            path, json.dumps(body), content_type="application/json",
        )

    def test_all_types_create_revise_history_and_cross_session(self):
        self.assertEqual(CatalogItem.objects.count(), 0)
        created = {}
        for kind, (prefix, props) in CONFIG.items():
            url = self.collection(kind)
            self.assertEqual(self.client.get(url).json()["results"], [])
            response = self.post(url, {"name": kind.title(), "properties": props})
            self.assertEqual(response.status_code, 201, response.content)
            item = response.json()
            self.assertTrue(item["id"].startswith(prefix + "-"))
            self.assertEqual(uuid.UUID(item["uuid"]).version, 7)
            self.assertEqual(item["schema_version"], 1)
            self.assertEqual(item["revision"], "r001")
            self.assertEqual(item["compatibility"]["status"], "current")
            self.assertEqual(item["properties"], props)
            self.assertEqual(response["Location"], url + "/" + item["id"])
            created[kind] = item
            one = self.client.get(url + "/" + item["id"]).json()
            self.assertEqual(one["properties"], props)
            self.assertEqual(len(self.client.get(url).json()["results"]), 1)
            self.assertEqual(self.client.get(url + "/" + item["id"] + "/revisions").json()["revisions"][0]["properties"], props)
            reader = Client()
            reader.force_login(self.reader)
            self.assertEqual(reader.get(url).json()["results"][0]["id"], item["id"])
            self.assertEqual(reader.get(url + "/" + item["id"]).json()["properties"], props)
            revised = self.post(url + "/" + item["id"] + "/revisions", {
                "expected_revision": "r001", "name": kind.title() + " revised"
            })
            self.assertEqual(revised.status_code, 201, revised.content)
            self.assertEqual(revised.json()["revision"], "r002")
            self.assertEqual(revised.json()["properties"], props)
            self.assertEqual(self.client.get(url + "/" + item["id"] + "/revisions/1").json()["properties"], props)
            history = reader.get(url + "/" + item["id"] + "/revisions").json()["revisions"]
            self.assertEqual([r["revision"] for r in history], ["r001", "r002"])
            self.assertEqual([r["name"] for r in history], [kind.title(), kind.title() + " revised"])
            self.assertEqual(self.post(url + "/" + item["id"] + "/revisions", {
                "expected_revision": "r001", "name": "stale"
            }).status_code, 409)
            self.assertEqual(reader.post(url, data="{}", content_type="application/json").status_code, 403)
            self.assertEqual(CatalogAuditEvent.objects.filter(item__public_id=item["id"]).count(), 2)
        self.assertEqual(CatalogItem.objects.count(), 3)
        self.assertEqual(CatalogRevision.objects.count(), 6)
        self.assertEqual(CatalogAuditEvent.objects.count(), 6)
        self.assertEqual(CatalogItem.objects.filter(type_slug="model").count(), 0)
        self.assertEqual(set(ObjectTypeVersion.objects.filter(type_slug__in=CONFIG).values_list("type_slug", flat=True)), set(CONFIG))
        # Framework is a process definition only: no Solution or run/score record.
        framework = CatalogItem.objects.get(public_id=created["framework"]["id"])
        self.assertEqual(framework.type_slug, "framework")
        self.assertFalse(hasattr(framework, "score"))
        self.assertFalse(hasattr(framework, "run_id"))

    def test_wrong_type_and_invalid_payload_are_rejected(self):
        p = self.post(self.collection("provider"), {"name": "A", "properties": {}}).json()
        wrong = self.collection("harness") + "/" + p["id"]
        for path in (wrong, wrong + "/revisions", wrong + "/revisions/1"):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.post(wrong + "/revisions", {"expected_revision": "r001"}).status_code, 404)
        for kind in CONFIG:
            url = self.collection(kind)
            self.assertEqual(self.post(url, {"name": "", "properties": {}}).status_code, 400)
            self.assertEqual(self.post(url, {"name": "Invalid", "properties": []}).status_code, 400)
            self.assertEqual(self.post(url, {"name": "Bad", "properties": {"accessible": "yes"}}).status_code, 400)
            self.assertEqual(self.post(url, {"name": "Bad", "properties": {}, "type": "model"}).status_code, 400)
        self.assertEqual(self.post(self.collection("harness"), {
            "name": "bad interface", "properties": {"interface": "vortex"}
        }).status_code, 400)
        self.assertEqual(self.post(self.collection("framework"), {
            "name": "bad stages", "properties": {"stages": "one string"}
        }).status_code, 400)
        self.assertEqual(self.client.get(self.collection("model")).status_code, 404)
        self.assertEqual(self.client.get(self.collection("unknown")).status_code, 404)

    def test_post_revision_validation_and_immutable_preceding_properties(self):
        original = self.post(self.collection("harness"), {
            "name": "Harness", "properties": {"interface": "cli", "custom": {"keep": None}}
        }).json()
        revisions = self.collection("harness") + "/" + original["id"] + "/revisions"
        fail = self.post(revisions, {"expected_revision": "r001", "properties": {"interface": "wrong"}})
        self.assertEqual(fail.status_code, 400)
        self.assertEqual(self.post(revisions, {"name": "No token"}).status_code, 400)
        updated = self.post(revisions, {"expected_revision": "r001", "name": "Changed", "properties": {
            "interface": "ide", "custom": {"keep": None}, "extensions": {"new": [1, {"x": True}]}
        }}).json()
        self.assertEqual(updated["revision"], "r002")
        self.assertEqual(updated["properties"]["extensions"]["new"][1]["x"], True)
        self.assertEqual(self.client.get(revisions + "/1").json()["properties"], original["properties"])
        self.assertEqual(self.client.get(revisions + "/2").json()["properties"], updated["properties"])

    def test_permissions_and_csrf_cross_browser(self):
        creator = Client(enforce_csrf_checks=True)
        creator.get("/api/v1/auth/csrf")
        creator.force_login(self.writer)
        token = creator.cookies["csrftoken"].value
        url = self.collection("provider")
        self.assertEqual(creator.post(url, json.dumps({"name": "No CSRF"}), content_type="application/json").status_code, 403)
        good = creator.post(url, json.dumps({"name": "Allowed", "properties": {}}),
                            content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(good.status_code, 201, good.content)
        viewer = Client()
        viewer.force_login(self.reader)
        self.assertEqual(viewer.get(url).status_code, 200)
        self.assertEqual(viewer.get(url).json()["results"][0]["id"], good.json()["id"])
        self.assertEqual(viewer.post(url, "{}", content_type="application/json").status_code, 403)
        denied = Client()
        denied.force_login(self.no_read)
        self.assertEqual(denied.get(url).status_code, 403)
        self.assertEqual(Client().get(url).status_code, 401)
