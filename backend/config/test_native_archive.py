"""PLAT-30: exact historical archive, permissions, bytes and fail-closed behavior."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TransactionTestCase, override_settings

from .catalog_services import create_model, revise_model
from .evidence_store import attach, blob_path
from .identity import ensure_roles
from .models import CatalogRevision, CatalogItem, ObjectTypeVersion

ROOT = "/api/v1/archives/native"
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


class NativeArchiveTests(TransactionTestCase):
    # Preserve data-migration-provisioned technical schemas across flush().
    serialized_rollback = True
    def _create_identities(self):
        ensure_roles()
        User = get_user_model()
        self.operator = User.objects.create_user(username="native-operator",
                                                 password="Dont-export-This-Test-Password!")
        self.operator.groups.add(Group.objects.get(name="platform-admin"))
        self.writer = User.objects.create_user(username="native-writer",
                                               password="Another-Sensitive-Test-Password!")
        self.writer.groups.add(Group.objects.get(name="contributor"))
        self.maintainer = User.objects.create_user(username="native-maintainer",
                                                   password="Dont-export-This-Either!")
        self.maintainer.groups.add(Group.objects.get(name="data-maintainer"))

    def setUp(self):
        self._create_identities()
        workdir = tempfile.TemporaryDirectory(prefix="ai-native-test-")
        self.addCleanup(workdir.cleanup)
        self.root = Path(workdir.name)
        settings = override_settings(EVIDENCE_STORE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client = Client()
        self.client.force_login(self.operator)

    def download(self):
        response = self.client.get(ROOT)
        if response.status_code != 200:
            return response, None
        return response, b"".join(response.streaming_content)

    def test_empty_catalog_has_valid_versioned_archive_and_no_passwords(self):
        response, raw = self.download()
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            schema = json.loads(archive.read("schema.json"))
            users = json.loads(archive.read("subjects.json"))["users"]
            self.assertTrue(manifest["complete"])
            self.assertEqual(manifest["record_count"], ObjectTypeVersion.objects.count())
            self.assertEqual(CatalogItem.objects.count(), 0)
            self.assertEqual(manifest["evidence_blob_count"], 0)
            self.assertEqual(manifest["snapshot"]["isolation"], "repeatable_read")
            self.assertGreater(len(schema["models"]), 1)
            self.assertIn("native-operator", [u["username"] for u in users])
            self.assertTrue(all(set(u) == {"id", "username", "roles", "is_active"}
                                for u in users))
        self.assertNotIn(b"Dont-export-This-Test-Password!", raw)
        self.assertNotIn(b"pbkdf2_sha256", raw)
        self.assertNotIn(b"Another-Sensitive-Test-Password!", raw)

    def test_history_unknown_json_fks_and_original_bytes(self):
        model = create_model(actor=self.writer, name="GLM",
                             properties={"context_window": 8000,
                                         "extensions": {"unfamiliar_future_value": None}})
        old_id = str(model.current_revision_id)
        revised = revise_model(item=model, actor=self.writer,
                               expected_revision="r001", name="GLM updated")
        self.assertEqual(revised.number, 2)
        link = attach(item=model, revision=CatalogRevision.objects.get(pk=old_id),
                      file=SimpleUploadedFile("trace.pdf", PDF, content_type="application/pdf"),
                      actor=self.writer, source="test:manual")
        response, raw = self.download()
        self.assertEqual(response.status_code, 200, response.content if not raw else "")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            model_records = [json.loads(line) for line in
                             archive.read("records/config.catalogitem.ndjson").splitlines()]
            revisions = [json.loads(line) for line in
                         archive.read("records/config.catalogrevision.ndjson").splitlines()]
            links = [json.loads(line) for line in
                     archive.read("records/config.evidencelink.ndjson").splitlines()]
            self.assertEqual(len(model_records), 1)
            self.assertEqual(len(revisions), 2)
            self.assertEqual(len(links), 1)
            self.assertEqual(str(links[0]["fields"]["revision"]), old_id)
            self.assertEqual(links[0]["fields"]["blob"], link.blob_id)
            self.assertEqual(revisions[0]["fields"]["properties"]["extensions"]
                             ["unfamiliar_future_value"], None)
            self.assertEqual(archive.read("evidence/blobs/" + link.blob_id), PDF)
            self.assertEqual(manifest["files"]["evidence/blobs/" + link.blob_id]
                             ["sha256"], hashlib.sha256(PDF).hexdigest())
            self.assertEqual(manifest["evidence_blob_count"], 1)
            self.assertIn("records/config.catalogauditevent.ndjson", archive.namelist())

    def test_permissions_never_expose_archive_or_login_secrets(self):
        self.client.logout()
        self.assertEqual(self.client.get(ROOT).status_code, 401)
        self.client.force_login(self.writer)
        self.assertEqual(self.client.get(ROOT).status_code, 403)
        self.client.force_login(self.maintainer)
        self.assertEqual(self.client.get(ROOT).status_code, 403)
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(ROOT + "?all=true").status_code, 400)

    def test_missing_corrupt_evidence_never_returns_partial_archive(self):
        model = create_model(actor=self.writer, name="Model",
                             properties={"context_window": 4096})
        evidence = attach(item=model, revision=model.current_revision,
                          file=SimpleUploadedFile("original.pdf", PDF),
                          actor=self.writer)
        path = blob_path(evidence.blob_id)
        path.write_bytes(b"malicious replacement")
        result, raw = self.download()
        self.assertIsNone(raw)
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json()["error"], "archive_integrity_failed")
        self.assertEqual(result["Cache-Control"], "no-store")
