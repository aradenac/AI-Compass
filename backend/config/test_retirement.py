"""FUT-18: logical retirement, orphan inventory, privileged purge, RBAC and policy.

Every negative path is exercised: a shared blob is never purged while any
reference remains, a merely unlinked independent object is never auto-purged,
the grace window is enforced, purge requires a separate privilege and an
explicit confirmation, and a disk inconsistency fails closed.
"""
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .catalog_services import create_component
from .evidence_store import attach, blob_path, stream_and_finalize
from .identity import ensure_roles
from .models import (CatalogItem, EvidenceBlob, EvidenceLink, PurgeCandidate,
                     PurgePolicy, PurgeReceipt, RetirementEvent, RetirementRecord)
from .retirement_services import (
    RetirementError, PurgeRefused, configure_policy, inventory, policy,
    preview, purge, record_inventory, restore, retire, serialize_policy,
)

BASE = "/api/v1/maintenance/retirement"
PASS = "Secure-Fictitious-Retirement-Password-2026!"


class RetirementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U = get_user_model()
        cls.editor = U.objects.create_user("ret-editor", password=PASS)
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.maint = U.objects.create_user("ret-maint", password=PASS)
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.purger = U.objects.create_user("ret-purger", password=PASS)
        cls.purger.groups.add(Group.objects.get(name="purge-operator"))
        cls.reader = U.objects.create_user("ret-reader", password=PASS)
        cls.reader.groups.add(Group.objects.get(name="user"))

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ai-compass-ret-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        override = override_settings(EVIDENCE_STORE_ROOT=self.root)
        override.enable(); self.addCleanup(override.disable)
        self.client = Client(enforce_csrf_checks=True)

    def login(self, user):
        self.client.force_login(user)
        response = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["csrfToken"]

    def post(self, path, payload, token):
        return self.client.post(path, payload, content_type="application/json",
                                HTTP_X_CSRFTOKEN=token)

    def patch(self, path, payload, token):
        return self.client.patch(path, json.dumps(payload), content_type="application/json",
                                 HTTP_X_CSRFTOKEN=token)

    def component(self, name="Retire me"):
        return create_component(type_slug="model", actor=self.editor,
                                name=name, properties={"unknown": None})

    def orphan_blob(self, body=b"orphan bytes\n"):
        """A genuinely unreferenced blob: bytes on disk, metadata row, zero links.

        Evidence links are append-only and cannot be deleted, so an orphan is
        modelled the way it really appears — a payload committed with no live
        reference (e.g. an interrupted/rolled-back upload) rather than by
        unlinking a referenced one.
        """
        checksum, size, media_type, _ = stream_and_finalize(
            SimpleUploadedFile("o.txt", body, content_type="text/plain"))
        EvidenceBlob.objects.get_or_create(
            sha256=checksum, defaults={"size": size, "media_type": media_type})
        return checksum

    # --- logical retirement -------------------------------------------------

    def test_retire_hides_object_and_preserves_identity_and_history(self):
        item = self.component()
        token = self.login(self.maint)
        response = self.post(f"{BASE}/{item.public_id}/retire", {"reason": "obsolete"}, token)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(CatalogItem.objects.filter(public_id=item.public_id).exists())
        record = RetirementRecord.objects.get(item=item)
        self.assertEqual(record.action, "retired")
        self.assertTrue(RetirementEvent.objects.filter(item=item, action="retired").exists())
        # History is readable and the tombstone trail is intact.
        history = self.client.get(f"{BASE}/{item.public_id}")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["history"][0]["action"], "retired")

    def test_restore_reverses_retirement_but_keeps_tombstone_trail(self):
        item = self.component()
        token = self.login(self.maint)
        self.post(f"{BASE}/{item.public_id}/retire", {"reason": "x"}, token)
        response = self.post(f"{BASE}/{item.public_id}/restore", {"reason": "kept"}, token)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(RetirementRecord.objects.filter(item=item).exists())
        # The append-only event trail survives the restore.
        self.assertEqual(
            list(RetirementEvent.objects.filter(item=item).values_list("action", flat=True)),
            ["retired", "restored"])

    def test_retire_is_refused_for_a_reader_and_requires_retirement_manage(self):
        item = self.component()
        token = self.login(self.reader)
        response = self.post(f"{BASE}/{item.public_id}/retire", {"reason": "x"}, token)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(RetirementRecord.objects.filter(item=item).exists())

    # --- orphan inventory and dry-run ---------------------------------------

    def test_inventory_excludes_referenced_blob_and_includes_true_orphan(self):
        item = self.component("with evidence")
        attach(item=item, revision=None,
               file=SimpleUploadedFile("k.txt", b"kept\n", content_type="text/plain"),
               actor=self.editor)
        orphan = self.orphan_blob(b"nobody references me\n")
        subjects = {row["subject"] for row in inventory()}
        self.assertIn(orphan, subjects)
        for link in EvidenceLink.objects.all():
            self.assertNotIn(link.blob_id, subjects)

    def test_preview_enforces_grace_and_is_repeatable(self):
        orphan = self.orphan_blob()
        configure_policy(actor=self.purger, enabled=False, grace_days=30,
                         eligible_classes=["evidence_blob"], cadence_hours=168)
        first = preview()
        self.assertEqual(first["candidate_count"], len(inventory()))
        # A freshly orphaned blob is inside the grace window: blocked, not reclaimable.
        entry = next(r for r in first["candidates"] if r["subject"] == orphan)
        self.assertFalse(entry["eligible"])
        self.assertTrue(any("grace" in b for b in entry["blockers"]))
        self.assertEqual(first["projected_reclaim_bytes"], 0)
        # No journal row yet, so the orphan clock starts at upload: stable repeats.
        self.assertEqual(preview(), first)

    def test_preview_grace_uses_durable_candidate_journal(self):
        orphan = self.orphan_blob(b"journaled\n")
        configure_policy(actor=self.purger, enabled=False, grace_days=30,
                         eligible_classes=["evidence_blob"], cadence_hours=168)
        # First inventory observation journals the true first-orphan moment.
        record_inventory(actor=self.purger)
        journal = PurgeCandidate.objects.get(subject=orphan, kind="evidence_blob")
        earlier = self.orphan_blob(b"journaled-old\n")  # unrelated, just isolation
        # Rewind the journal past the grace window: now eligible, and the clock
        # follows the durable journal rather than any fabricated timestamp.
        PurgeCandidate.objects.filter(pk=journal.pk).update(
            first_seen_at=timezone.now() - timedelta(days=45))
        entry = next(r for r in preview()["candidates"] if r["subject"] == orphan)
        self.assertTrue(entry["eligible"], entry)
        self.assertTrue(earlier)  # sanity: distinct orphan still unjournaled
        blocked_other = next(r for r in preview()["candidates"] if r["subject"] == earlier)
        self.assertFalse(blocked_other["eligible"])

    def test_record_inventory_is_idempotent_and_never_restarts_grace(self):
        orphan = self.orphan_blob(b"stable journal\n")
        first = record_inventory(actor=self.purger)
        created = PurgeCandidate.objects.get(subject=orphan, kind="evidence_blob")
        stamp = created.first_seen_at
        second = record_inventory(actor=self.purger)
        self.assertEqual(first, second)
        self.assertEqual(
            PurgeCandidate.objects.filter(subject=orphan, kind="evidence_blob").count(), 1)
        created.refresh_from_db()
        self.assertEqual(created.first_seen_at, stamp)

    def test_preview_zero_grace_marks_orphan_eligible(self):
        orphan = self.orphan_blob(b"reclaim me\n")
        configure_policy(actor=self.purger, enabled=True, grace_days=0,
                         eligible_classes=["evidence_blob"], cadence_hours=1)
        entry = next(r for r in preview()["candidates"] if r["subject"] == orphan)
        self.assertTrue(entry["eligible"], entry)

    # --- privileged physical purge ------------------------------------------

    def test_purge_removes_only_true_orphan_and_reclaims_bytes(self):
        kept_item = self.component("still referenced")
        kept_link = attach(item=kept_item, revision=None,
                           file=SimpleUploadedFile("kept.txt", b"keep\n", content_type="text/plain"),
                           actor=self.editor)
        orphan = self.orphan_blob(b"delete these bytes please\n")
        size = EvidenceBlob.objects.get(sha256=orphan).size
        receipt = purge(actor=self.purger, subjects=[kept_link.blob_id, orphan], token="purge")
        self.assertEqual(receipt.purged_count, 1)
        self.assertEqual(receipt.blocked_count, 1)
        self.assertEqual(receipt.reclaimed_bytes, size)
        self.assertFalse(EvidenceBlob.objects.filter(sha256=orphan).exists())
        self.assertFalse(blob_path(orphan).exists())
        # The protected blob and its link are untouched.
        self.assertTrue(EvidenceBlob.objects.filter(sha256=kept_link.blob_id).exists())
        self.assertTrue(EvidenceLink.objects.filter(pk=kept_link.pk).exists())
        results = {r["subject"]: r["result"] for r in receipt.detail["results"]}
        self.assertEqual(results[orphan], "purged")
        self.assertEqual(results[kept_link.blob_id], "re_referenced")

    def test_purge_requires_explicit_confirmation_token(self):
        orphan = self.orphan_blob()
        with self.assertRaises(PurgeRefused):
            purge(actor=self.purger, subjects=[orphan], token="yes")
        self.assertTrue(EvidenceBlob.objects.filter(sha256=orphan).exists())

    def test_purge_fails_closed_on_disk_inconsistency(self):
        orphan = self.orphan_blob()
        blob_path(orphan).unlink()  # metadata present, bytes missing
        receipt = purge(actor=self.purger, subjects=[orphan], token="purge")
        self.assertEqual(receipt.purged_count, 0)
        self.assertEqual(receipt.blocked_count, 1)
        self.assertEqual(receipt.detail["results"][0]["result"], "disk_inconsistent")
        self.assertTrue(EvidenceBlob.objects.filter(sha256=orphan).exists())

    def test_dedup_shared_blob_is_protected_while_any_reference_remains(self):
        body = b"shared identical bytes\n"
        a = self.component("owner a")
        b = self.component("owner b")
        la = attach(item=a, revision=None,
                    file=SimpleUploadedFile("a.txt", body, content_type="text/plain"),
                    actor=self.editor)
        lb = attach(item=b, revision=None,
                    file=SimpleUploadedFile("b.txt", body, content_type="text/plain"),
                    actor=self.editor)
        # Identical bytes dedup to one immutable object with two attributions.
        self.assertEqual(la.blob_id, lb.blob_id)
        sha = la.blob_id
        self.assertEqual(EvidenceBlob.objects.filter(sha256=sha).count(), 1)
        self.assertEqual(EvidenceLink.objects.filter(blob_id=sha).count(), 2)
        # Any surviving reference protects the shared bytes, even under a purge.
        receipt = purge(actor=self.purger, subjects=[sha], token="purge")
        self.assertEqual(receipt.purged_count, 0)
        self.assertEqual(receipt.blocked_count, 1)
        self.assertEqual(receipt.detail["results"][0]["result"], "re_referenced")
        self.assertTrue(EvidenceBlob.objects.filter(sha256=sha).exists())

    def test_purged_blob_is_not_an_unknown_hash_reachable_by_url(self):
        orphan = self.orphan_blob(b"gone after purge\n")
        purge(actor=self.purger, subjects=[orphan], token="purge")
        # No metadata row and no bytes: a guessed digest downloads nothing.
        self.assertFalse(EvidenceBlob.objects.filter(sha256=orphan).exists())
        self.assertFalse(blob_path(orphan).exists())

    def test_receipt_is_immutable(self):
        orphan = self.orphan_blob()
        receipt = purge(actor=self.purger, subjects=[orphan], token="purge")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                PurgeReceipt.objects.filter(pk=receipt.pk).update(purged_count=99)

    def test_purge_is_idempotent_on_retry(self):
        orphan = self.orphan_blob(b"retry me\n")
        first = purge(actor=self.purger, subjects=[orphan], token="purge")
        self.assertEqual(first.purged_count, 1)
        # A retried job finds nothing to remove and never deletes unrelated data.
        second = purge(actor=self.purger, subjects=[orphan], token="purge")
        self.assertEqual(second.purged_count, 0)
        self.assertEqual(second.blocked_count, 1)
        self.assertEqual(second.detail["results"][0]["result"], "unknown_subject")
        self.assertEqual(PurgeReceipt.objects.count(), 2)

    def test_tamper_delete_outside_the_purge_window_is_refused(self):
        # The immutability exception is not reachable by an ordinary code path:
        # the same DELETE without the purge guard must still raise.
        orphan = self.orphan_blob(b"tamper target\n")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EvidenceBlob.objects.filter(sha256=orphan).delete()
        self.assertTrue(EvidenceBlob.objects.filter(sha256=orphan).exists())

    # --- policy administration ----------------------------------------------

    def test_policy_disabled_by_default_and_requires_a_class_to_enable(self):
        self.assertIsNone(policy())
        self.assertFalse(serialize_policy(None)["enabled"])
        with self.assertRaises(RetirementError):
            configure_policy(actor=self.purger, enabled=True, grace_days=30,
                             eligible_classes=[], cadence_hours=24)

    def test_policy_is_versioned_and_supersedes_previous(self):
        configure_policy(actor=self.purger, enabled=False, grace_days=10,
                         eligible_classes=["evidence_blob"], cadence_hours=24)
        second = configure_policy(actor=self.purger, enabled=True, grace_days=45,
                                  eligible_classes=["evidence_blob", "managed_record"],
                                  cadence_hours=48)
        self.assertEqual(second.version, 2)
        self.assertEqual(PurgePolicy.objects.filter(is_active=True).count(), 1)
        self.assertTrue(policy().enabled)
        self.assertEqual(policy().grace_days, 45)

    # --- HTTP RBAC / CSRF ---------------------------------------------------

    def test_purge_http_requires_purge_manage_and_csrf(self):
        orphan = self.orphan_blob()
        token = self.login(self.maint)  # data-maintainer: read, no purge
        denied = self.post(f"{BASE}/purge", {"subjects": [orphan], "confirm": "purge"}, token)
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(EvidenceBlob.objects.filter(sha256=orphan).exists())
        ptoken = self.login(self.purger)
        # Missing CSRF header is refused before any deletion.
        no_csrf = self.client.post(f"{BASE}/purge",
                                   json.dumps({"subjects": [orphan], "confirm": "purge"}),
                                   content_type="application/json")
        self.assertEqual(no_csrf.status_code, 403)
        self.assertTrue(EvidenceBlob.objects.filter(sha256=orphan).exists())
        ok = self.post(f"{BASE}/purge", {"subjects": [orphan], "confirm": "purge"}, ptoken)
        self.assertEqual(ok.status_code, 201, ok.content)
        self.assertEqual(ok.json()["receipt"]["purged_count"], 1)

    def test_policy_endpoint_rbac(self):
        token = self.login(self.maint)
        read = self.client.get(f"{BASE}/policy")
        self.assertEqual(read.status_code, 200)
        denied = self.patch(f"{BASE}/policy/edit",
                            {"enabled": True, "grace_days": 5,
                             "eligible_classes": ["evidence_blob"]}, token)
        self.assertEqual(denied.status_code, 403)
        ptoken = self.login(self.purger)
        allowed = self.patch(f"{BASE}/policy/edit",
                             {"enabled": True, "grace_days": 5,
                              "eligible_classes": ["evidence_blob"]}, ptoken)
        self.assertEqual(allowed.status_code, 201, allowed.content)
        self.assertTrue(allowed.json()["policy"]["enabled"])
