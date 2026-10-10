"""PLAT-33: end-to-end mocked source contract; never ingest Demo or real private data."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase, override_settings

from .catalog_services import revise_model
from .identity import ensure_roles
from .models import (
    CatalogAuditEvent, CatalogItem, CatalogRevision, EvidenceLink, EvidenceBlob,
    ExternalImportBinding, ExternalImportBatch, ExternalImportEvent,
)

PREFIX = "/api/v1/imports/mock-models"
SOURCE = "mock-model-catalog-v1"


class MockModelImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        cls.operator = User.objects.create_user("external-mock-operator", password="StrongTestPW12345678!")
        cls.operator.groups.add(Group.objects.get(name="import-operator"))
        cls.second_operator = User.objects.create_user("external-second-operator", password="StrongTestPW12345678!")
        cls.second_operator.groups.add(Group.objects.get(name="import-operator"))
        cls.contributor = User.objects.create_user("external-contributor", password="StrongTestPW12345678!")
        cls.contributor.groups.add(Group.objects.get(name="contributor"))
        cls.maintainer = User.objects.create_user("external-maintainer", password="StrongTestPW12345678!")
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="ai-compass-mock-source-")
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)
        config = override_settings(EXTERNAL_MOCK_IMPORT_ENABLED=True, EVIDENCE_STORE_ROOT=self.path)
        config.enable()
        self.addCleanup(config.disable)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.operator)
        self.client.get("/api/v1/auth/csrf")
        self.csrf = self.client.cookies["csrftoken"].value

    def rows(self):
        return {"source_id": SOURCE, "rows": [
            {"source_key": "external-alpha", "name": "Test Adapter A",
             "properties": {"context_window": 2048, "vendor_extra": {"unknown": None}}},
            {"source_key": "external-beta", "name": "Test Adapter B",
             "properties": {"supports_tools": False}},
        ]}

    def post(self, action, data, *, browser=None, csrf=True):
        client = browser or self.client
        return client.post(
            PREFIX + "/" + action, json.dumps(data), content_type="application/json",
            **({"HTTP_X_CSRFTOKEN": self.csrf} if csrf else {}),
        )

    def preview(self, data=None):
        r = self.post("preview", data or self.rows())
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def import_rows(self, data=None):
        source = data if data is not None else self.rows()
        preview = self.preview(source)
        self.assertTrue(preview["valid"], preview)
        response = self.post("apply", dict(source, preview_token=preview["preview_token"]))
        self.assertIn(response.status_code, (200, 201), response.content)
        return response

    def test_empty_preview_create_read_original_bytes_replay_and_revisions(self):
        source = self.rows()
        self.assertEqual(CatalogItem.objects.count(), 0)
        review = self.preview(source)
        self.assertEqual(review["counts"]["created"], 2)
        self.assertEqual(review["counts"]["invalid"], 0)
        self.assertFalse(review["already_imported"])
        self.assertEqual(CatalogItem.objects.count(), 0)
        self.assertEqual(ExternalImportBatch.objects.count(), 0)
        self.assertEqual(EvidenceBlob.objects.count(), 0)
        self.assertIn("vendor_extra", review["records"][0]["unknown_fields"])

        result = self.post("apply", dict(source, preview_token=review["preview_token"]))
        self.assertEqual(result.status_code, 201, result.content)
        first = result.json()
        self.assertEqual(first["row_count"], 2)
        self.assertEqual([r["action"] for r in first["results"]], ["created", "created"])
        self.assertEqual(len(set(r["item_id"] for r in first["results"])), 2)
        self.assertEqual(CatalogItem.objects.filter(type_slug="model").count(), 2)
        self.assertEqual(CatalogRevision.objects.count(), 2)
        self.assertEqual(ExternalImportBatch.objects.count(), 1)
        self.assertEqual(ExternalImportBinding.objects.count(), 2)
        self.assertEqual(ExternalImportEvent.objects.count(), 2)
        self.assertEqual(EvidenceLink.objects.count(), 2)
        self.assertEqual(CatalogAuditEvent.objects.filter(action="evidence_attached").count(), 2)

        # The attached content is the exact canonical original mock row,
        # never described or mislabeled as an original real-source export.
        reader = Client()
        reader.force_login(self.contributor)
        for row in first["results"]:
            evidence = EvidenceLink.objects.get(
                item__public_id=row["item_id"], provenance__source_key=row["source_key"]
            )
            downloaded = reader.get("/api/v1/evidence/" + str(evidence.pk) + "/download")
            self.assertEqual(downloaded.status_code, 200)
            original = next(r for r in source["rows"] if r["source_key"] == row["source_key"])
            expected = json.dumps(original, sort_keys=True, ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8")
            self.assertEqual(b"".join(downloaded.streaming_content), expected)
            self.assertEqual(evidence.blob.sha256, hashlib.sha256(expected).hexdigest())

        repeated = self.import_rows(source)
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(repeated.json()["already_imported"])
        self.assertEqual(repeated.json()["batch_id"], first["batch_id"])
        self.assertEqual(ExternalImportBatch.objects.count(), 1)
        self.assertEqual(CatalogRevision.objects.count(), 2)
        self.assertEqual(EvidenceLink.objects.count(), 2)
        self.assertEqual(self.client.get(PREFIX + "/batches/" + first["batch_id"]).json()
                         ["results"], first["results"])

        changed = self.rows()
        changed["rows"][0]["properties"]["context_window"] = 4096
        next_preview = self.preview(changed)
        self.assertEqual(next_preview["counts"]["revised"], 1)
        self.assertEqual(next_preview["counts"]["unchanged"], 1)
        self.assertEqual(next_preview["records"][0]["changed_fields"], ["context_window"])
        again = self.import_rows(changed)
        self.assertEqual(again.status_code, 201)
        self.assertEqual(again.json()["results"][0]["revision"], "r002")
        self.assertEqual(again.json()["results"][1]["revision"], "r001")
        self.assertEqual(CatalogRevision.objects.count(), 3)
        self.assertEqual(ExternalImportBatch.objects.count(), 2)
        self.assertEqual(EvidenceLink.objects.count(), 3)
        item = CatalogItem.objects.get(public_id=first["results"][0]["item_id"])
        original_revision = item.revisions.get(number=1)
        self.assertEqual(original_revision.properties["context_window"], 2048)
        self.assertEqual(original_revision.properties["vendor_extra"], {"unknown": None})
        self.assertEqual(item.current_revision.properties["context_window"], 4096)
        self.assertEqual(ExternalImportBinding.objects.get(source_key="external-alpha")
                         .last_import_revision, item.current_revision)

    def test_reject_invalid_preview_and_atomic_apply(self):
        payload = self.rows()
        payload["rows"][0]["properties"]["context_window"] = -9
        review = self.preview(payload)
        self.assertEqual(review["counts"]["invalid"], 1)
        self.assertIsNone(review["preview_token"])
        attempt = self.post("apply", dict(payload, preview_token="fake-token"))
        self.assertEqual(attempt.status_code, 409, attempt.content)
        self.assertEqual(CatalogItem.objects.count(), 0)

        valid = self.rows()
        token = self.preview(valid)["preview_token"]
        with patch("config.external_mock_import.attach", side_effect=RuntimeError("disk broken")):
            with self.assertRaisesRegex(RuntimeError, "disk broken"):
                self.post("apply", dict(valid, preview_token=token))
        self.assertEqual(CatalogItem.objects.count(), 0)
        self.assertEqual(ExternalImportBatch.objects.count(), 0)
        self.assertEqual(ExternalImportBinding.objects.count(), 0)
        self.assertEqual(ExternalImportEvent.objects.count(), 0)
        self.assertEqual(self.post("apply", dict(valid, preview_token=token)).status_code, 201)

    def test_conflict_on_manual_divergence_and_stale_signed_preview(self):
        source = self.rows()
        token = self.preview(source)["preview_token"]
        edited = self.rows()
        edited["rows"][0]["name"] = "Changed maliciously without another preview"
        self.assertEqual(self.post("apply", dict(edited, preview_token=token)).status_code, 409)
        self.assertEqual(CatalogItem.objects.count(), 0)
        first = self.import_rows(source).json()
        updated = self.rows()
        updated["rows"][0]["properties"]["context_window"] = 7000
        approved_token = self.preview(updated)["preview_token"]
        item = CatalogItem.objects.get(public_id=first["results"][0]["item_id"])
        revise_model(item=item, actor=self.contributor, expected_revision="r001",
                     properties={"context_window": 9000})
        new = self.preview(updated)
        self.assertFalse(new["valid"])
        self.assertEqual(new["counts"]["conflict"], 1)
        self.assertIsNone(new["preview_token"])
        self.assertEqual(self.post("apply", dict(updated, preview_token=approved_token)).status_code, 409)
        self.assertEqual(ExternalImportBatch.objects.count(), 1)
        self.assertEqual(CatalogRevision.objects.count(), 3)
        # Old exact batch replay MUST NOT silently ignore a later manual edit.
        self.assertFalse(self.preview(source)["valid"])

    def test_authentication_csrf_role_and_mock_only_safety(self):
        source = self.rows()
        self.assertEqual(self.post("preview", source, csrf=False).status_code, 403)
        self.assertEqual(self.post("apply", source, csrf=False).status_code, 403)
        self.client.logout()
        self.client.get("/api/v1/auth/csrf")
        self.csrf = self.client.cookies["csrftoken"].value
        self.assertEqual(self.post("preview", source).status_code, 401)
        self.client.force_login(self.contributor)
        self.assertEqual(self.post("preview", source).status_code, 403)
        self.client.force_login(self.maintainer)
        self.assertEqual(self.post("apply", source).status_code, 403)
        self.client.force_login(self.operator)
        with override_settings(EXTERNAL_MOCK_IMPORT_ENABLED=False):
            self.assertEqual(self.post("preview", source).status_code, 404)
            self.assertEqual(self.post("apply", source).status_code, 404)
        token = self.preview(source)["preview_token"]
        # Preview tokens are bound to the exact operator, not transferable.
        other = Client(enforce_csrf_checks=True)
        other.force_login(self.second_operator)
        other.get("/api/v1/auth/csrf")
        response = other.post(
            PREFIX + "/apply", json.dumps(dict(source, preview_token=token)),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=other.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(CatalogItem.objects.count(), 0)

    def test_duplicate_keys_nonmock_sources_and_batch_immutability(self):
        bad = self.rows()
        bad["rows"][1]["source_key"] = bad["rows"][0]["source_key"]
        self.assertEqual(self.post("preview", bad).status_code, 400)
        self.assertEqual(self.post("preview", {"source_id": "demo", "rows": []}).status_code, 400)
        self.assertEqual(self.post("preview", {"source_id": SOURCE, "rows": []}).status_code, 400)
        self.assertEqual(self.post("preview", {"source_id": SOURCE, "rows": [
            {"source_key": "x", "name": "a", "properties": {}, "extra": "not mapped"}
        ]}).status_code, 400)
        record = self.import_rows().json()
        batch = ExternalImportBatch.objects.get(pk=record["batch_id"])
        event = batch.events.first()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ExternalImportBatch.objects.filter(pk=batch.pk).update(row_count=55)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ExternalImportEvent.objects.filter(pk=event.pk).delete()
        self.assertEqual(ExternalImportBatch.objects.count(), 1)


