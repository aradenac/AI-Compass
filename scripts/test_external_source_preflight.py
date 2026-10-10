"""PLAT-33: source discovery is non-mutating and never becomes implicit import."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import external_source_preflight as intake


OPTIONS = {
    "origin": "https://internal.example.org/exports/authorized",
    "owner": "R&D data owner",
    "permission_basis": "Internal data-sharing approval from data owner",
    "classification": "confidential",
    "real_source_attested": True,
}


class SourceIntakeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def file(self, filename, text):
        path = self.root / filename
        path.write_text(text, encoding="utf-8")
        return path

    def discover(self, path, format="csv", **options):
        return intake.discover(path, format=format, **{**OPTIONS, **options})

    def test_csv_inventory_missing_duplicate_and_no_values_leaked(self):
        path = self.file("source.csv",
                         'source_ref,display_name,cost\nA001,SECRET_ABC,8\nA002,SECRET_DEF,\nA002,SECRET_DEF,\n')
        before = path.read_bytes()
        r = self.discover(path)
        self.assertEqual(r["status"], "source_discovered_mapping_pending")
        self.assertFalse(r["approved_for_apply"])
        self.assertFalse(r["production_ready"])
        self.assertEqual(r["inventory"]["rows"], 3)
        self.assertEqual(r["inventory"]["identical_duplicate_rows"], 1)
        cols = {v["name"]: v for v in r["inventory"]["fields"]}
        self.assertEqual(cols["cost"]["missing_count"], 2)
        self.assertEqual(r["mapping_gate"]["stable_source_key_field"], None)
        self.assertEqual(r["mapping_gate"]["target_business_type"], None)
        self.assertEqual(r["source"]["format"], "csv")
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn("SECRET_ABC", json.dumps(r))
        self.assertNotIn("SECRET_DEF", json.dumps(r))

    def test_jsonl_field_drift_and_unknown_are_described_not_imported(self):
        path = self.file("some-export.jsonl",
                         '{"id":"A","extended":{"future":null},"cost":0}\n'
                         '{"id":"B","optional":true}\n')
        r = self.discover(path, "jsonl")
        fields = {c["name"]:c for c in r["inventory"]["fields"]}
        self.assertEqual(fields["extended"]["observed_types"]["object"], 1)
        self.assertEqual(fields["extended"]["missing_count"], 1)
        self.assertEqual(fields["optional"]["observed_types"]["boolean"], 1)
        self.assertEqual(fields["optional"]["missing_count"], 1)
        self.assertEqual(fields["cost"]["observed_types"]["integer"], 1)
        self.assertFalse(r["mapping_gate"]["source_samples_reviewed"])

    def test_reject_fake_demo_zip_symlink_empty_and_bad_attestation(self):
        original = self.file("source.csv", "id,value\nA,real\n")
        with self.assertRaisesRegex(intake.PreflightError, "attest"):
            self.discover(original, real_source_attested=False)
        with self.assertRaisesRegex(intake.PreflightError, "Demo"):
            self.discover(original, origin="https://example.org/demo/data")
        with self.assertRaisesRegex(intake.PreflightError, "Demo"):
            self.discover(original, owner="Synthetic fixtures")
        linked = self.root / "linked.csv"
        linked.symlink_to(original)
        with self.assertRaisesRegex(intake.PreflightError, "non-symlink"):
            self.discover(linked)
        empty = self.file("empty.csv", "")
        with self.assertRaisesRegex(intake.PreflightError, "non-empty"):
            self.discover(empty)
        native = self.root / "external.csv"
        native.write_bytes(b"PK\x03\x04hidden archive")
        with self.assertRaisesRegex(intake.PreflightError, "ZIP"):
            self.discover(native)

    def test_reject_malformed_csv_and_duplicate_headers(self):
        for text, fragment in [
            ("id,id\n1,2\n", "Duplicate"),
            ("id,value\n1\n", "missing/extra"),
            ("id,value\n1,2,3\n", "missing/extra"),
            ("id,value\n", "at least one"),
            ("id,value\n\"unfinished\n", "CSV"),
        ]:
            with self.subTest(text=text):
                with self.assertRaisesRegex((intake.PreflightError, __import__("csv").Error),
                                            fragment):
                    self.discover(self.file("source.csv", text))

    def test_reject_jsonl_duplicate_keys_nan_arrays_and_localstorage(self):
        for text in [
            '{"id":"A","id":"B"}\n',
            '{"rating":NaN}\n',
            '["not", "a", "record"]\n',
            '{"mode":"demo","id":"fake"}\n',
            '{"localStorage":true}\n',
            '\n{"id":"A"}\n',
        ]:
            with self.subTest(text=text):
                with self.assertRaises(intake.PreflightError):
                    self.discover(self.file("source.jsonl", text), "jsonl")

    def test_enforces_file_bounds_and_source_shape(self):
        path = self.file("source.csv", "id\n1\n")
        with self.assertRaisesRegex(intake.PreflightError, "classification"):
            self.discover(path, classification="secret-unapproved")
        with self.assertRaisesRegex(intake.PreflightError, "origin"):
            self.discover(path, origin="")
        with self.assertRaisesRegex(intake.PreflightError, "Choose"):
            self.discover(path, "auto")
        large = self.root / "large.csv"
        large.write_bytes(b"x" * (intake.MAX_BYTES + 1))
        with self.assertRaisesRegex(intake.PreflightError, "10 MiB"):
            self.discover(large)
        many = self.file("many.csv", "id\n" + "A\n" * (intake.MAX_ROWS + 1))
        with self.assertRaisesRegex(intake.PreflightError, "2000 rows"):
            self.discover(many)


if __name__ == "__main__":
    unittest.main()
