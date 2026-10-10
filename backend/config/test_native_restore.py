"""PLAT-31 permission, fail-closed preview, missing schema and nonempty target tests."""
import io
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from config.archive_services import build_native_export
from config.identity import ensure_roles
from config.models import CatalogItem, ObjectTypeVersion
from config.native_restore import RestoreError, inspect, require_disposable
from restore_tracking.models import NativeRestore, NativeRestoreEvent

ENV = {
    "AI_COMPASS_STAGING": "1", "AI_COMPASS_NATIVE_RESTORE_TEST": "1",
    "AI_COMPASS_STAGING_CANDIDATE": "abcdef0123456789",
    "DB_NAME": "ai_compass_restore_verify",
    "DB_USER": "ai_compass_restore", "DB_HOST": "db",
}


class NativeRestoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U = get_user_model()
        cls.maintainer = U.objects.create_user(username="restore-maintainer", password="test")
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))
        cls.unprivileged = U.objects.create_user(username="restore-reader", password="test")
        cls.unprivileged.groups.add(Group.objects.get(name="user"))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / "source.zip"
        with patch("config.archive_services._snapshot_boundary",
                   return_value="2026-10-10T12:00:00+00:00"):
            snapshot = build_native_export()
            try:
                self.archive.write_bytes(snapshot.read())
            finally:
                snapshot.close()
        env = patch.dict(os.environ, ENV)
        env.start()
        self.addCleanup(env.stop)

    def test_all_disposable_guards(self):
        require_disposable()
        for key, wrong in (
            ("AI_COMPASS_STAGING", "0"), ("AI_COMPASS_NATIVE_RESTORE_TEST", "0"),
            ("DB_NAME", "ai_compass"), ("DB_USER", "production"),
            ("DB_HOST", "production-db"),
            ("AI_COMPASS_STAGING_CANDIDATE", "invalid")):
            with self.subTest(key=key), patch.dict(os.environ, {key: wrong}):
                with self.assertRaises(RestoreError):
                    require_disposable()

    def test_preview_is_read_only_and_enforces_permission(self):
        before = (CatalogItem.objects.count(), NativeRestore.objects.count(),
                  NativeRestoreEvent.objects.count())
        outcome = inspect(self.archive, self.maintainer.username)
        self.assertEqual(outcome["status"], "preview")
        self.assertEqual(outcome["target"], "disposable-staging-only")
        self.assertEqual((CatalogItem.objects.count(), NativeRestore.objects.count(),
                          NativeRestoreEvent.objects.count()), before)
        with self.assertRaisesRegex(RestoreError, "lacks"):
            inspect(self.archive, self.unprivileged.username)
        with self.assertRaisesRegex(RestoreError, "Active named"):
            inspect(self.archive, "missing")

    def test_nonempty_target_rejected_without_mutation(self):
        from config.catalog_services import create_model
        created = create_model(actor=self.maintainer, name="Existing",
                               properties={"context_window": 9000})
        with self.assertRaisesRegex(RestoreError, "Nonempty target"):
            inspect(self.archive, self.maintainer.username, apply=True)
        self.assertEqual(CatalogItem.objects.get(pk=created.pk).public_id, created.public_id)
        self.assertEqual(NativeRestore.objects.count(), 0)

    def test_corrupt_manifest_rejected_without_receipt(self):
        with zipfile.ZipFile(self.archive) as source:
            entries = {name: source.read(name) for name in source.namelist()}
        entries["manifest.json"] = b'{"complete":false}'
        with zipfile.ZipFile(self.archive, "w") as result:
            for name, data in entries.items():
                result.writestr(name, data)
        with self.assertRaisesRegex(RestoreError, "Invalid native archive"):
            inspect(self.archive, self.maintainer.username, apply=True)
        self.assertEqual(NativeRestore.objects.count(), 0)

    def test_unsupported_schema_blocks_preview_without_mutation(self):
        existing = ObjectTypeVersion.objects.get(type_slug="model", version=2)
        with patch("config.native_restore._schema_mapping",
                   side_effect=RestoreError("Unknown/changed schema")):
            with self.assertRaisesRegex(RestoreError, "Unknown/changed"):
                inspect(self.archive, self.maintainer.username, apply=True)
        self.assertTrue(ObjectTypeVersion.objects.filter(pk=existing.pk).exists())
        self.assertEqual(NativeRestore.objects.count(), 0)
