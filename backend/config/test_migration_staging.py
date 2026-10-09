"""PLAT-35: registered migration stays transactional, staging-only, append-only."""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.test import TestCase

from config.models import CatalogItem, CatalogRevision, CatalogAuditEvent, ObjectTypeVersion
from config.management.commands.stage_model_v1_to_v2 import upgrade, assert_disposable_target

SAFE = {"AI_COMPASS_STAGING": "1", "AI_COMPASS_STAGING_CANDIDATE": "0123456789abcdef",
        "DB_NAME": "ai_compass_restore_verify", "DB_USER": "ai_compass_restore", "DB_HOST": "db"}


class StagingMigrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("stage-migration-tester", password="A_long_safe_password123")
        cls.v1 = ObjectTypeVersion.objects.get(type_slug="model", version=1)

    def create_legacy(self, public_id, properties):
        item = CatalogItem.objects.create(public_id=public_id, type_slug="model")
        revision = CatalogRevision.objects.create(item=item, number=1, schema_version=self.v1,
                                                   display_name="Legacy", properties=properties,
                                                   created_by=self.user)
        item.current_revision = revision
        item.save(update_fields=["current_revision"])
        return item

    def test_deny_wrong_target_and_missing_candidate(self):
        with patch.dict(os.environ, {"AI_COMPASS_STAGING": "0"}, clear=True):
            with self.assertRaises(CommandError):
                assert_disposable_target()
        with patch.dict(os.environ, SAFE | {"DB_NAME": "ai_compass"}, clear=True):
            with self.assertRaises(CommandError):
                assert_disposable_target()
        with patch.dict(os.environ, SAFE, clear=True):
            assert_disposable_target()

    def test_append_preserves_history_identity_unknown_fields_and_idempotency(self):
        item = self.create_legacy("mdl-tender-forest-light", {
            "context_window": 2048, "vendor_ext": {"missing": None},
            "release_channel": "preview"})
        original = item.current_revision
        self.assertEqual(upgrade(), [item.public_id])
        item.refresh_from_db()
        self.assertEqual(item.id, original.item_id)
        self.assertEqual(item.current_revision.number, 2)
        self.assertEqual(item.current_revision.schema_version.version, 2)
        self.assertEqual(item.current_revision.properties, original.properties)
        self.assertEqual(CatalogRevision.objects.get(pk=original.pk).schema_version.version, 1)
        self.assertEqual(CatalogAuditEvent.objects.filter(item=item, action="schema_migrated").count(), 1)
        self.assertEqual(upgrade(), [])
        self.assertEqual(CatalogRevision.objects.filter(item=item).count(), 2)

    def test_incompatible_legacy_aborts_whole_transaction(self):
        good = self.create_legacy("mdl-apple-brook-moon", {"release_channel": "stable"})
        bad = self.create_legacy("mdl-wheat-green-river", {"release_channel": "unknown"})
        with self.assertRaises(CommandError):
            upgrade()
        good.refresh_from_db()
        bad.refresh_from_db()
        self.assertEqual(good.current_revision.number, 1)
        self.assertEqual(bad.current_revision.number, 1)
        self.assertEqual(CatalogAuditEvent.objects.filter(action="schema_migrated").count(), 0)
