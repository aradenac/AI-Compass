"""PLAT-26: signed, authorized, append-only and retry-safe production promotion."""
import hashlib
import hmac
import json
import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, transaction
from django.test import TestCase

from .identity import ensure_roles
from .models import (
    CatalogItem, CatalogRevision, CatalogAuditEvent, ObjectTypeVersion,
    ProductionMigrationReceipt,
)
from . import schema_promotion as promo


class PromotionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        cls.creator = User.objects.create_user("legacy-model-creator", password="TestSecret-long-2026!")
        cls.actor = User.objects.create_user("migration-operator", password="TestSecret-long-2026!")
        cls.actor.groups.add(Group.objects.get(name="data-maintainer"))
        cls.unprivileged = User.objects.create_user("migration-nonprivileged", password="TestSecret-long-2026!")
        cls.unprivileged.groups.add(Group.objects.get(name="contributor"))
        cls.v1 = ObjectTypeVersion.objects.get(type_slug="model", version=1)

    def make_legacy(self, index, properties=None):
        row = CatalogItem.objects.create(type_slug="model", public_id=f"mdl-legacy-fixture-{index:04d}")
        revision = CatalogRevision.objects.create(
            item=row, number=1, schema_version=self.v1,
            display_name="Legacy model", properties=properties or
            {"context_window":2048,"extension":{"preserve":None}},
            created_by=self.creator)
        row.current_revision = revision
        row.save(update_fields=["current_revision"])
        return row

    def approval(self, actor=None):
        operator = actor or self.actor
        import json
        schemas = list(ObjectTypeVersion.objects.order_by("type_slug", "version"))
        items, count, revision_hash, hrids, audits = promo._source_inventory()
        proof = {
            "candidate_id":"0123456789abcdef",
            "migration":promo.MIGRATION_KEY,
            "migration_sha256":"a" * 64,
            "app_commit":"b" * 40,
            "recovery_id":"20261010T010101Z-012345abcdef",
            "recovery_manifest_sha256":"c" * 64,
            "approved_report_sha256":"d" * 64,
            "source_item_count":items,
            "source_revision_count":count,
            "source_revision_digest":revision_hash,
            "source_hrid_digest":hrids,
            "source_audit_count":audits,
            "source_schema_versions":[f"{row.type_slug}:{row.version}" for row in schemas],
            "source_schema_hashes":[
                {"type":row.type_slug,"version":row.version,
                 "sha256":hashlib.sha256(json.dumps(row.json_schema,sort_keys=True,
                          ensure_ascii=False,separators=(",",":")).encode()).hexdigest()}
                for row in schemas],
            "source_evidence_db_references":{"blob_count":0,"link_count":0,"sha256":[]},
            "operator":operator.username,
        }
        return {"proof":proof,"signature":promo.sign(proof,settings.SECRET_KEY)}

    def test_read_only_preview_and_initial_append(self):
        row = self.make_legacy(1)
        original = row.current_revision
        before = promo.dry_run()
        self.assertEqual(before["pending_count"], 1)
        self.assertEqual(ProductionMigrationReceipt.objects.count(), 0)
        approval = self.approval()
        changed = promo.apply_batch(approval, expected_migration_sha="a"*64)
        self.assertEqual(changed["changed"], 1)
        self.assertEqual(changed["remaining"], 0)
        row.refresh_from_db()
        self.assertEqual(row.current_revision.number, 2)
        self.assertEqual(row.current_revision.schema_version.version, 2)
        self.assertEqual(row.current_revision.properties, original.properties)
        receipt = ProductionMigrationReceipt.objects.get(item=row)
        self.assertEqual(receipt.source_revision_id, original.pk)
        self.assertEqual(receipt.target_revision_id, row.current_revision.pk)
        self.assertEqual(receipt.actor_id, self.actor.pk)
        self.assertEqual(receipt.candidate_id, "0123456789abcdef")
        self.assertEqual(CatalogAuditEvent.objects.filter(item=row, action="schema_migrated").count(), 1)
        self.assertEqual(promo.apply_batch(approval, expected_migration_sha="a"*64)["changed"], 0)
        self.assertEqual(CatalogRevision.objects.filter(item=row).count(), 2)
        self.assertEqual(ProductionMigrationReceipt.objects.count(), 1)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ProductionMigrationReceipt.objects.filter(pk=receipt.pk).update(candidate_id="fedcba9876543210")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ProductionMigrationReceipt.objects.filter(pk=receipt.pk).delete()
        # PostgreSQL also refuses a fabricated cross-item receipt even when
        # both foreign keys independently point to existing valid revisions.
        other = self.make_legacy(8)
        other_v2 = CatalogRevision.objects.create(
            item=other, number=2, schema_version=ObjectTypeVersion.objects.get(
                type_slug="model", version=2),
            display_name="Other", properties={}, created_by=self.actor)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ProductionMigrationReceipt.objects.create(
                    item=row, source_revision=original, target_revision=other_v2,
                    actor=self.actor, candidate_id="0123456789abcdef",
                    migration_key=promo.MIGRATION_KEY, migration_sha256="a"*64,
                    app_commit="b"*40, recovery_id="backup-ref-1234",
                    recovery_manifest_sha256="c"*64,
                    approved_report_sha256="d"*64)
        self.assertEqual(ProductionMigrationReceipt.objects.count(), 1)

    def test_recovery_after_bounded_batch_keeps_exact_source_fingerprint(self):
        for i in range(103):
            self.make_legacy(i)
        approval = self.approval()
        one = promo.apply_batch(approval, expected_migration_sha="a"*64)
        self.assertEqual(one["changed"], 100)
        self.assertEqual(one["remaining"], 3)
        two = promo.apply_batch(approval, expected_migration_sha="a"*64)
        self.assertEqual(two["changed"], 3)
        self.assertEqual(two["remaining"], 0)
        self.assertEqual(promo.apply_batch(approval, expected_migration_sha="a"*64)["changed"], 0)
        self.assertEqual(CatalogRevision.objects.count(), 206)
        self.assertEqual(ProductionMigrationReceipt.objects.count(), 103)
        self.assertEqual(CatalogAuditEvent.objects.count(), 103)

    def test_stale_state_and_bad_authentication_do_not_modify(self):
        row = self.make_legacy(2)
        proof = self.approval()
        with self.assertRaisesRegex(CommandError, "checksum"):
            promo.apply_batch(proof, expected_migration_sha="b"*64)
        bad = json.loads(json.dumps(proof))
        bad["proof"]["candidate_id"] = "fedcba9876543210"
        with self.assertRaisesRegex(CommandError, "signature"):
            promo.apply_batch(bad, expected_migration_sha="a"*64)
        bad_user = self.approval(self.unprivileged)
        with self.assertRaisesRegex(CommandError, "maintenance_triage"):
            promo.apply_batch(bad_user, expected_migration_sha="a"*64)
        # Make the backup stale AFTER the approval was signed.
        self.make_legacy(3)
        with self.assertRaisesRegex(CommandError, "recovery point"):
            promo.apply_batch(proof, expected_migration_sha="a"*64)
        self.assertEqual(ProductionMigrationReceipt.objects.count(), 0)
        row.refresh_from_db()
        self.assertEqual(row.current_revision.number, 1)

    def test_ambiguous_extensions_abort_full_batch(self):
        good = self.make_legacy(4, {"release_channel":"preview","vendor_extension":{"opaque":"preserve"}})
        bad = self.make_legacy(5, {"release_channel":"unrecognized"})
        check = promo.dry_run()
        self.assertEqual(check["pending_count"], 1)
        self.assertEqual(check["blocked_count"], 1)
        proof = self.approval()
        with self.assertRaisesRegex(CommandError, "Ambiguous"):
            promo.apply_batch(proof, expected_migration_sha="a"*64)
        good.refresh_from_db()
        bad.refresh_from_db()
        self.assertEqual(good.current_revision.number, 1)
        self.assertEqual(bad.current_revision.number, 1)
        self.assertEqual(ProductionMigrationReceipt.objects.count(), 0)

    def test_prevent_writes_outside_frozen_host_and_refuse_staging(self):
        self.make_legacy(6)
        from io import StringIO
        with patch.dict(os.environ, {"AI_COMPASS_PROMOTION_API_FROZEN":"0"}, clear=False):
            with self.assertRaisesRegex(CommandError, "frozen"):
                call_command("promote_model_schema", "--apply",
                             "--operator", self.actor.username)
        with patch.dict(os.environ, {"AI_COMPASS_STAGING":"1"}, clear=False):
            with self.assertRaisesRegex(CommandError, "not a staging"):
                call_command("promote_model_schema", "--preview",
                             "--operator", self.actor.username)
        with patch.dict(os.environ, {"AI_COMPASS_STAGING":"0"}, clear=False):
            with self.assertRaisesRegex(CommandError, "maintenance_triage"):
                call_command("promote_model_schema", "--preview",
                             "--operator", self.unprivileged.username)
            out = StringIO()
            call_command("promote_model_schema", "--preview",
                         "--operator", self.actor.username, "--json", stdout=out)
            self.assertEqual(json.loads(out.getvalue())["pending_count"], 1)
        self.assertEqual(ProductionMigrationReceipt.objects.count(), 0)
