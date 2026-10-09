"""PLAT-25: version-aware read compatibility and immutable historical contracts."""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.db import DatabaseError, transaction

from .catalog_compat import classify
from .identity import ensure_roles
from .models import CatalogItem, CatalogRevision, ObjectTypeVersion


class SchemaCompatibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        cls.editor = User.objects.create_user(username="compat-editor", password="test-unique-pass")
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.maintainer = User.objects.create_user(username="compat-no-reader", password="test-unique-pass")
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))
        cls.reader = User.objects.create_user(username="compat-reader", password="test-unique-pass")
        cls.reader.groups.add(Group.objects.get(name="reviewer"))

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.client.force_login(self.editor)

    def post(self, path, payload, csrf=True):
        kwargs = {"HTTP_X_CSRFTOKEN": self.client.cookies["csrftoken"].value} if csrf else {}
        return self.client.post(path, json.dumps(payload), content_type="application/json", **kwargs)

    def legacy(self, *, public_id, properties, schema_version=1, type_slug="model", schema_type=None):
        schema = ObjectTypeVersion.objects.get(type_slug=schema_type or type_slug, version=schema_version)
        item = CatalogItem.objects.create(public_id=public_id, type_slug=type_slug)
        revision = CatalogRevision.objects.create(
            item=item, number=1, schema_version=schema, display_name="Historical",
            properties=properties, created_by=self.editor
        )
        item.current_revision = revision
        item.save(update_fields=["current_revision"])
        return item

    def test_registry_v1_and_v2_are_immutable_and_revisioned(self):
        one = self.client.get("/api/v1/models/schema?version=1")
        two = self.client.get("/api/v1/models/schema")
        self.assertEqual(one.status_code, 200)
        self.assertEqual((one.json()["version"], two.json()["version"]), (1, 2))
        self.assertNotIn("release_channel", one.json()["schema"]["properties"])
        self.assertEqual(two.json()["schema"]["properties"]["release_channel"]["enum"],
                         ["stable", "preview", "experimental"])
        self.assertEqual(self.client.get("/api/v1/catalog/schemas/model?version=1").json()["version"], 1)
        self.assertEqual(self.client.get("/api/v1/catalog/schemas/model").json()["version"], 2)
        self.assertEqual(self.client.get("/api/v1/catalog/schemas/model?version=garbage").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/catalog/schemas/model?version=89").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/catalog/schemas/not-registered").status_code, 404)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ObjectTypeVersion.objects.filter(type_slug="model", version=1).update(json_schema={})
        self.assertEqual(ObjectTypeVersion.objects.get(type_slug="model", version=1).json_schema,
                         one.json()["schema"])

    def test_new_model_v2_preserves_unknown_extensions_and_null(self):
        data = {"context_window": 32000, "release_channel": "preview",
                "vendor_specific": {"n": None, "flag": True}, "nullable_extension": None}
        response = self.post("/api/v1/models", {"name": "Versioned", "properties": data})
        self.assertEqual(response.status_code, 201, response.content)
        created = response.json()
        self.assertEqual(created["schema_version"], 2)
        self.assertEqual(created["compatibility"]["status"], "current")
        self.assertFalse(created["compatibility"]["read_only"])
        self.assertIn("nullable_extension", created["compatibility"]["null_fields"])
        self.assertIn("vendor_specific", created["compatibility"]["unknown_fields"])
        self.assertIn("supports_tools", created["compatibility"]["missing_fields"])
        self.assertNotIn("supports_tools", created["properties"])  # absence, not false/null
        self.assertEqual(created["properties"], data)
        revision = self.post("/api/v1/models/" + created["id"] + "/revisions",
                             {"expected_revision": "r001", "name": "Versioned updated"})
        self.assertEqual(revision.status_code, 201, revision.content)
        self.assertEqual(revision.json()["properties"], data)

    def test_legacy_v1_is_readable_and_edited_without_silent_promotion(self):
        item = self.legacy(
            public_id="mdl-quiet-river-leaf",
            properties={"context_window": 2048, "extension": {"deep": [None, 3]},
                        "missing_is_not_null": None}
        )
        current = self.client.get("/api/v1/models/" + item.public_id).json()
        self.assertEqual(current["schema_version"], 1)
        self.assertEqual(current["compatibility"]["status"], "migration_available")
        self.assertFalse(current["compatibility"]["read_only"])
        self.assertIn("missing_is_not_null", current["compatibility"]["null_fields"])
        self.assertIn("supports_tools", current["compatibility"]["missing_fields"])
        self.assertNotIn("supports_tools", current["properties"])
        revised = self.post("/api/v1/models/" + item.public_id + "/revisions",
                            {"expected_revision": "r001", "name": "Safe legacy name edit"})
        self.assertEqual(revised.status_code, 201, revised.content)
        self.assertEqual(revised.json()["schema_version"], 1)
        history = self.client.get("/api/v1/models/" + item.public_id + "/revisions").json()["revisions"]
        self.assertEqual([r["schema_version"] for r in history], [1, 1])
        self.assertEqual([r["revision"] for r in history], ["r001", "r002"])
        self.assertEqual(history[0]["name"], "Historical")
        self.assertEqual(history[0]["properties"], history[1]["properties"])
        self.assertEqual(CatalogRevision.objects.filter(item=item).count(), 2)

    def test_v1_newly_constrained_field_triggers_review_and_server_write_block(self):
        item = self.legacy(
            public_id="mdl-lazy-sky-glass",
            properties={"release_channel": "unclassified", "retain_me": {"k": "original"}}
        )
        response = self.client.get("/api/v1/models/" + item.public_id)
        status = response.json()["compatibility"]
        self.assertEqual(status["status"], "needs_review")
        self.assertTrue(status["read_only"])
        self.assertIn("release_channel", status["incompatible_fields"])
        self.assertEqual(response.json()["properties"]["release_channel"], "unclassified")
        blocked = self.post("/api/v1/models/" + item.public_id + "/revisions",
                            {"expected_revision": "r001", "name": "Do not modify"})
        self.assertEqual(blocked.status_code, 409, blocked.content)
        self.assertEqual(blocked.json()["error"], "schema_write_blocked")
        self.assertEqual(CatalogRevision.objects.filter(item=item).count(), 1)
        self.assertEqual(item.current_revision.display_name, "Historical")

    def test_invalid_original_and_unsupported_future_schema_never_crash_reads(self):
        corrupt = self.legacy(public_id="mdl-black-fox-tree",
                              properties={"context_window": -100, "nonstandard": [1, 2]})
        result = self.client.get("/api/v1/models/" + corrupt.public_id).json()
        self.assertEqual(result["compatibility"]["status"], "invalid")
        self.assertTrue(result["compatibility"]["read_only"])
        self.assertEqual(result["properties"]["context_window"], -100)
        self.assertEqual(self.post("/api/v1/models/" + corrupt.public_id + "/revisions",
                                   {"expected_revision": "r001", "name": "Unsafe"}).status_code, 409)
        ObjectTypeVersion.objects.create(type_slug="model", version=99, json_schema={"type": "object"})
        future = self.legacy(public_id="mdl-future-owl-water",
                             properties={"future_field": "keep"}, schema_version=99)
        future_result = self.client.get("/api/v1/models/" + future.public_id).json()
        self.assertEqual(future_result["compatibility"]["status"], "unsupported")
        self.assertEqual(future_result["compatibility"]["current_schema_version"], 2)
        self.assertTrue(future_result["compatibility"]["read_only"])
        # Unknown registered versions cannot hijack the schema used for new writes.
        created = self.post("/api/v1/models", {"name": "Still v2", "properties": {}})
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["schema_version"], 2)

    def test_unknown_type_and_partial_record_offer_authorized_raw_read_only_view(self):
        unknown = self.legacy(public_id="other-unknown-001",
                              type_slug="futuretype", schema_type="model",
                              properties={"original": {"arbitrary": 3}})
        raw = self.client.get("/api/v1/catalog/items/" + unknown.public_id)
        self.assertEqual(raw.status_code, 200)
        self.assertEqual(raw.json()["compatibility"]["status"], "unsupported")
        self.assertTrue(raw.json()["compatibility"]["read_only"])
        self.assertEqual(raw.json()["properties"], {"original": {"arbitrary": 3}})
        partial = CatalogItem.objects.create(public_id="other-partial-002", type_slug="newtype")
        result = self.client.get("/api/v1/catalog/items/" + partial.public_id).json()
        self.assertEqual(result["compatibility"]["status"], "unsupported")
        self.assertIsNone(result["properties"])
        self.assertIsNone(result["revision"])
        self.client.force_login(self.maintainer)
        self.assertEqual(self.client.get("/api/v1/catalog/items/" + unknown.public_id).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/catalog/schemas/model").status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get("/api/v1/catalog/items/" + unknown.public_id).status_code, 401)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/api/v1/catalog/items/" + unknown.public_id).status_code, 200)
        self.assertEqual(self.post("/api/v1/models", {"name": "Reader", "properties": {}}).status_code, 403)

    def test_generic_outdated_type_with_no_adapter(self):
        versions = {
            1: {"type": "object", "properties": {"flag": {"type": "boolean"}}, "additionalProperties": True},
            2: {"type": "object", "properties": {"flag": {"type": "boolean"}}, "additionalProperties": True},
        }
        old = classify("provider", "provider", 1, {"flag": True, "extra": 3}, versions)
        self.assertEqual(old["status"], "outdated")
        self.assertEqual(old["unknown_fields"], ["extra"])
        self.assertFalse(old["read_only"])
        self.assertEqual(classify("provider", "provider", 2, {"flag": True}, versions)["status"], "current")
