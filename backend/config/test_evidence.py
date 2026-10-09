"""PLAT-17: original byte fidelity, provenance, dedup, CSRF and broken-file tests."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import Client, TestCase, override_settings

from .catalog_services import create_model, revise_model
from .evidence_store import blob_path
from .identity import ensure_roles
from .models import CatalogAuditEvent, EvidenceBlob, EvidenceLink
from .management.commands.reconcile_evidence import inspect

BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
BASE = "/api/v1/catalog/items/"


class EvidenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        cls.editor = User.objects.create_user(username="evidence-editor", password="test")
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.reader = User.objects.create_user(username="evidence-reader", password="test")
        cls.reader.groups.add(Group.objects.get(name="reviewer"))
        cls.no_read = User.objects.create_user(username="evidence-ops", password="test")
        cls.no_read.groups.add(Group.objects.get(name="data-maintainer"))

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ai-compass-evidence-test-")
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.override = override_settings(EVIDENCE_STORE_ROOT=self.temp)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.editor)
        self.client.get("/api/v1/auth/csrf")
        self.item = create_model(actor=self.editor, name="Model", properties={"context_window": 8000})
        self.second = create_model(actor=self.editor, name="Another", properties={"context_window": 9000})

    def url(self, item=None):
        return BASE + (item or self.item).public_id + "/evidence"

    def upload(self, *, item=None, body=BYTES, filename="reference.pdf", revision="r001",
               source="https://example.org/original", provenance=None, client=None):
        params = {
            "file": SimpleUploadedFile(filename, body, content_type="application/pdf"),
            "source": source,
            "provenance": json.dumps(provenance if provenance is not None else
                                     {"context": "review", "source_id": None}),
        }
        if revision is not None:
            params["revision"] = revision
        browser = client or self.client
        kwargs = {}
        if "csrftoken" in browser.cookies:
            kwargs["HTTP_X_CSRFTOKEN"] = browser.cookies["csrftoken"].value
        return browser.post(self.url(item) + "/upload", data=params, **kwargs)

    def test_two_sessions_original_bytes_and_distinct_context_links(self):
        first = self.upload()
        self.assertEqual(first.status_code, 201, first.content)
        record = first.json()
        self.assertEqual(record["sha256"], hashlib.sha256(BYTES).hexdigest())
        self.assertEqual(record["size"], len(BYTES))
        self.assertEqual(record["revision"], "r001")
        self.assertEqual(record["integrity"], "ok")
        self.assertEqual(uuid.UUID(record["id"]).version, 7)
        self.assertEqual(record["provenance"]["source_id"], None)
        self.assertEqual(record["source"], "https://example.org/original")
        other = self.upload(item=self.second, source="manual:second-context",
                            provenance={"evaluation": "different"}, filename="copy.pdf")
        self.assertEqual(other.status_code, 201, other.content)
        self.assertNotEqual(other.json()["id"], record["id"])
        self.assertEqual(other.json()["sha256"], record["sha256"])
        self.assertEqual(EvidenceBlob.objects.count(), 1)
        self.assertEqual(EvidenceLink.objects.count(), 2)
        viewer = Client()
        viewer.force_login(self.reader)
        result = viewer.get(self.url()).json()
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["id"], record["id"])
        path = "/api/v1/evidence/" + record["id"]
        self.assertEqual(viewer.get(path).json()["sha256"], record["sha256"])
        downloaded = viewer.get(path + "/download")
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(b"".join(downloaded.streaming_content), BYTES)
        self.assertIn('attachment;', downloaded["Content-Disposition"])
        self.assertIn("reference.pdf", downloaded["Content-Disposition"])
        self.assertEqual(downloaded["Cache-Control"], "private, no-store")
        self.assertEqual(viewer.get("/api/v1/evidence/" + other.json()["id"]).json()["source"],
                         "manual:second-context")
        self.assertEqual(CatalogAuditEvent.objects.filter(action="evidence_attached").count(), 2)

        # Renaming does not break FKs to a pinned historical catalog revision.
        revise_model(item=self.item, actor=self.editor, expected_revision="r001", name="Renamed")
        history = viewer.get(self.url()).json()["results"]
        self.assertEqual(history[0]["revision"], "r001")
        self.assertEqual(history[0]["revision_uuid"], str(self.item.revisions.get(number=1).id))
        self.assertEqual(b"".join(viewer.get(path + "/download").streaming_content), BYTES)

    def test_validation_type_content_size_and_mismatched_revision(self):
        self.assertEqual(self.upload(body=b"not actually PDF").status_code, 400)
        self.assertEqual(self.upload(filename="payload.exe").status_code, 400)
        self.assertEqual(self.upload(body=b"").status_code, 400)
        self.assertEqual(self.upload(filename="nested/evil.pdf").status_code, 201)
        self.assertEqual(self.upload(revision="r002").status_code, 404)
        self.assertEqual(self.upload(revision="not-a-revision").status_code, 400)
        with override_settings(EVIDENCE_MAX_BYTES=10):
            self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(self.upload(provenance="not an object").status_code, 400)
        self.assertEqual(self.upload(body=b"{", filename="data.json").status_code, 400)

    def test_permissions_csrf_and_no_public_payload(self):
        anonymous = Client()
        self.assertEqual(anonymous.get(self.url()).status_code, 401)
        no_write = Client(enforce_csrf_checks=True)
        no_write.force_login(self.reader)
        no_write.get("/api/v1/auth/csrf")
        self.assertEqual(self.upload(client=no_write).status_code, 403)
        no_permission = Client()
        no_permission.force_login(self.no_read)
        self.assertEqual(no_permission.get(self.url()).status_code, 403)
        self.assertEqual(no_permission.get("/api/v1/evidence/" + str(uuid.uuid4())).status_code, 403)
        missing_csrf = Client(enforce_csrf_checks=True)
        missing_csrf.force_login(self.editor)
        self.assertEqual(self.upload(client=missing_csrf).status_code, 403)
        saved = self.upload().json()
        link = "/api/v1/evidence/" + saved["id"]
        self.assertEqual(anonymous.get(link + "/download").status_code, 401)
        self.assertEqual(no_permission.get(link + "/download").status_code, 403)
        self.assertEqual(self.client.post(link, {}).status_code, 405)
        self.assertEqual(self.client.delete(link).status_code, 405)

    def test_corruption_or_missing_content_never_returns_original_as_valid(self):
        record = self.upload().json()
        link = "/api/v1/evidence/" + record["id"]
        storage_path = blob_path(record["sha256"])
        storage_path.write_bytes(b"modified")
        self.assertEqual(self.client.get(link).json()["integrity"], "broken")
        self.assertEqual(self.client.get(link + "/download").status_code, 409)
        self.assertIn(record["sha256"], inspect()["missing_or_corrupt_blobs"])
        storage_path.unlink()
        self.assertEqual(self.client.get(link + "/download").status_code, 409)
        self.assertIn(record["sha256"], inspect()["missing_or_corrupt_blobs"])

    def test_rollback_before_link_commit_leaves_no_valid_pointer(self):
        with patch("config.evidence_store.EvidenceLink.objects.create", side_effect=RuntimeError("interrupt")):
            with self.assertRaisesRegex(RuntimeError, "interrupt"):
                self.upload()
        self.assertEqual(EvidenceBlob.objects.count(), 0)
        self.assertEqual(EvidenceLink.objects.count(), 0)
        digest = hashlib.sha256(BYTES).hexdigest()
        self.assertTrue(blob_path(digest).exists())
        result = inspect()
        self.assertIn(digest, result["orphan_files"])
        self.assertEqual(result["dangling_links"], 0)
        self.assertEqual(result["status"], "attention")
        # Retry recovers same finalized bytes instead of rewriting or multiplying them.
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(inspect()["status"], "ok")

    def test_reconciliation_interrupted_upload_and_immutable_db_guards(self):
        record = self.upload().json()
        link = EvidenceLink.objects.get(pk=record["id"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EvidenceLink.objects.filter(pk=link.pk).update(source="changed")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EvidenceBlob.objects.filter(pk=record["sha256"]).delete()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EvidenceLink.objects.filter(pk=link.pk).delete()
        new_revision = revise_model(item=self.second, actor=self.editor,
                                    expected_revision="r001", name="Second changed")
        wrong_rev = self.second.current_revision
        # DB trigger independently blocks linking a revision from a different item.
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EvidenceLink.objects.create(
                    blob=link.blob, item=self.item, revision=wrong_rev,
                    original_filename="bad.pdf", uploaded_by=self.editor,
                )
        incoming = self.temp / ".incoming"
        incoming.mkdir(exist_ok=True)
        interrupted = incoming / "upload-interrupted.part"
        interrupted.write_bytes(b"some bytes")
        import os, time
        os.utime(interrupted, (time.time() - 7200, time.time() - 7200))
        self.assertIn(interrupted.name, inspect()["incoming_files"])
        self.assertTrue(interrupted.exists())
        cleaned = inspect(prune_stale_incoming=True)
        self.assertIn(interrupted.name, cleaned["pruned_stale_incoming"])
        self.assertFalse(interrupted.exists())
        self.assertEqual(inspect()["status"], "ok")
