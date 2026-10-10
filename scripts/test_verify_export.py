"""Standalone verifier tests: no Django, network, database or evidence volume."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from verify_export import VerificationError, verify


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


class NativeVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "native.zip"

    def fixture(self, *, corrupt=False, missing_fk=False, missing_blob=False):
        payload = b"original evidence bytes"
        digest = hashlib.sha256(payload).hexdigest()
        model = "config.evidenceblob"
        file = "records/" + model + ".ndjson"
        linkmodel = "config.evidencelink"
        linkfile = "records/" + linkmodel + ".ndjson"
        schema = {"format": "ai-compass-native", "version": 1, "models": [
            {"model": model, "path": file, "count": 1, "relations": []},
            {"model": linkmodel, "path": linkfile, "count": 1, "relations": [
                {"field": "blob", "target": model, "uses_pk": False}]}]}
        members = {
            "subjects.json": encode({"users": [], "note": "No credentials"}),
            "schema.json": encode(schema),
            file: encode({"model": model, "pk": digest, "fields": {"size": len(payload)}}),
            linkfile: encode({"model": linkmodel, "pk": "link-1",
                              "fields": {"blob": "not-a-blob" if missing_fk else digest}}),
            "evidence/blobs/" + digest: payload,
        }
        if missing_blob:
            del members["evidence/blobs/" + digest]
        declared = {name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                    for name, data in members.items()}
        manifest = {"format": "ai-compass-native", "version": 1, "complete": True,
                    "snapshot": {"isolation": "repeatable_read", "boundary": "2026-10-10T12:00:00Z"},
                    "record_count": 2, "evidence_blob_count": 1, "subjects": 0,
                    "files": declared}
        if corrupt:
            members["evidence/blobs/" + digest] = b"tampered original bytes"
        with zipfile.ZipFile(self.path, "w", zipfile.ZIP_DEFLATED) as target:
            for name, data in members.items():
                target.writestr(name, data)
            target.writestr("manifest.json", encode(manifest))
        return self.path

    def test_verified_original_and_fk(self):
        result = verify(self.fixture())
        self.assertEqual(result["records"], 2)
        self.assertEqual(result["original_evidence_blobs"], 1)
        self.assertEqual(result["status"], "verified")

    def test_tampered_original_fails(self):
        with self.assertRaisesRegex(VerificationError, "SHA-256"):
            verify(self.fixture(corrupt=True))

    def test_broken_reference_fails(self):
        with self.assertRaisesRegex(VerificationError, "Unresolved FK"):
            verify(self.fixture(missing_fk=True))

    def test_incomplete_original_fails(self):
        with self.assertRaisesRegex(VerificationError, "Missing or untracked"):
            verify(self.fixture(missing_blob=True))

    def test_rejects_zip_traversal_and_duplicate_entries(self):
        path = self.fixture()
        with zipfile.ZipFile(path, "a") as target:
            target.writestr("../escape", b"X")
        with self.assertRaisesRegex(VerificationError, "Unsafe ZIP"):
            verify(path)

    def test_rejects_partial_report(self):
        path = self.fixture()
        with zipfile.ZipFile(path, "a") as target:
            target.writestr("manifest.json", b"{}")
        with self.assertRaisesRegex(VerificationError, "duplicate"):
            verify(path)


if __name__ == "__main__":
    unittest.main()
