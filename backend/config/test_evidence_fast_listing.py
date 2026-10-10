"""FUT-02: metadata-only evidence listing and true byte integrity on download."""
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .catalog_services import create_model
from .evidence_store import attach, blob_path
from .identity import ensure_roles

DATA = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


class FastListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        cls.actor = get_user_model().objects.create_user("fast-evidence-tester", password="not-production")
        cls.actor.groups.add(Group.objects.get(name="contributor"))

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        override = override_settings(EVIDENCE_STORE_ROOT=Path(temp.name))
        override.enable()
        self.addCleanup(override.disable)
        self.c = Client()
        self.c.force_login(self.actor)
        self.item = create_model(actor=self.actor, name="Immutable Source",
                                 properties={"context_window": 4096})
        self.link = attach(item=self.item, revision=self.item.current_revision,
                           file=SimpleUploadedFile("original.pdf", DATA), actor=self.actor)
        self.url = "/api/v1/catalog/items/%s/evidence" % self.item.public_id
        self.original = "/api/v1/evidence/%s" % self.link.pk

    def test_metadata_list_does_not_touch_large_evidence_bytes(self):
        with patch("config.evidence_views.verify_bytes", side_effect=AssertionError("no blob I/O in listings")):
            response = self.c.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        row = response.json()["results"][0]
        self.assertEqual(row["integrity"], "not_checked")
        self.assertEqual(row["verification"], {"status": "not_checked", "last_verified_at": None})
        self.assertEqual(row["sha256"], hashlib.sha256(DATA).hexdigest())

    def test_full_detail_and_download_continue_failing_on_tamper(self):
        self.assertEqual(self.c.get(self.original).json()["integrity"], "ok")
        blob_path(self.link.blob_id).write_bytes(b"corrupt")
        # A listing does not falsely say "OK": verification was not attempted.
        self.assertEqual(self.c.get(self.url).json()["results"][0]["integrity"], "not_checked")
        self.assertEqual(self.c.get(self.original).json()["integrity"], "broken")
        self.assertEqual(self.c.get(self.original + "/download").status_code, 409)
