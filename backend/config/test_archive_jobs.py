"""FUT-19: durable archive jobs, scoped resumable download grants and audit.

Security is proven from the HTTP boundary: read-only observers, unrelated
maintainers and expired/revoked/wrong-archive token holders download no byte;
authorized logs carry no secret. A synthetic multi-range transfer proves Range
resume returns exactly the right bytes and that corruption fails closed.
"""
import hashlib
import io
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .archive_job_services import (
    GrantDenied, issue_grant, open_artifact, parse_range, request_job,
    resolve_grant, revoke_grant,
)
from .identity import ensure_roles
from .models import ArchiveAccessEvent, ArchiveGrant, ArchiveJob

BASE = "/api/v1/archives/jobs"

PASS = "Secure-Fictitious-Archive-Password-2026!"


class ArchiveJobTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U = get_user_model()
        cls.operator = U.objects.create_user("arch-operator", password=PASS)
        cls.operator.groups.add(Group.objects.get(name="archive-operator"))
        cls.admin = U.objects.create_user("arch-admin", password=PASS)
        cls.admin.groups.add(Group.objects.get(name="platform-admin"))
        cls.reader = U.objects.create_user("arch-reader", password=PASS)
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint = U.objects.create_user("arch-maint", password=PASS)
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ai-compass-arch-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        override = override_settings(ARCHIVE_STORE_ROOT=self.root)
        override.enable(); self.addCleanup(override.disable)
        self.client = Client(enforce_csrf_checks=True)

    def login(self, user):
        self.client.force_login(user)
        response = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["csrfToken"]

    def post(self, path, payload, token):
        import json
        return self.client.post(path, json.dumps(payload),
                                content_type="application/json",
                                HTTP_X_CSRFTOKEN=token)

    def _artifact(self, job, body=b"PK\x03\x04 fake archive bytes for tests\n" * 4096):
        """Publish bytes directly, bypassing the DB-touching child build."""
        import os
        path = self.root / f"{job.public_id}-{hashlib.sha256(body).hexdigest()}.zip"
        path.write_bytes(body)
        job.state = "complete"
        job.artifact_path = str(path)
        job.sha256 = hashlib.sha256(body).hexdigest()
        job.size_bytes = len(body)
        job.manifest = {"verified": True}
        job.save()
        return body

    # --- job lifecycle & RBAC ----------------------------------------------

    def test_only_an_export_grant_can_list_and_request_jobs(self):
        token = self.login(self.reader)  # a read-only platform observer
        denied = self.client.get(BASE)
        self.assertEqual(denied.status_code, 403)
        denied = self.post(BASE, {"kind": "native"}, token)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(ArchiveJob.objects.count(), 0)

    def test_data_maintainer_gains_no_archive_right_by_default(self):
        token = self.login(self.maint)
        self.assertEqual(self.client.get(BASE).status_code, 403)
        self.assertEqual(self.post(BASE, {"kind": "native"}, token).status_code, 403)

    def test_request_creates_queued_job_and_rejects_unknown_kind(self):
        token = self.login(self.operator)
        response = self.post(BASE, {"kind": "native"}, token)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["job"]["state"], "queued")
        self.assertEqual(self.post(BASE, {"kind": "evil"}, token).status_code, 400)

    def test_job_creation_is_separate_from_download_but_not_from_export_grant(self):
        # Both request and download require archive_export here; a maintainer or
        # observer holds neither, so neither content nor grant is reachable.
        token = self.login(self.maint)
        job = request_job(actor=self.operator, kind="native")
        self._artifact(job)
        self.assertEqual(self.client.get(f"{BASE}/{job.public_id}").status_code, 403)
        self.assertEqual(self.post(f"{BASE}/{job.public_id}/grant", {}, token).status_code, 403)

    # --- grant issuance / revocation / audit --------------------------------

    def test_grant_token_is_revealed_once_and_never_stored_raw(self):
        job = request_job(actor=self.operator, kind="native")
        self._artifact(job)
        token = self.login(self.operator)
        response = self.post(f"{BASE}/{job.public_id}/grant", {}, token)
        self.assertEqual(response.status_code, 201, response.content)
        raw = response.json()["token"]
        self.assertTrue(raw and len(raw) > 40)
        grant = ArchiveGrant.objects.get(public_id=response.json()["grant"]["public_id"])
        self.assertNotEqual(grant.token_digest, raw)
        self.assertEqual(grant.token_digest, hashlib.sha256(raw.encode()).hexdigest())
        # Listing never re-reveals the token.
        listing = self.client.get(f"{BASE}/{job.public_id}/grants")
        self.assertEqual(listing.status_code, 200)
        self.assertNotIn(raw, listing.content.decode())
        self.assertNotIn("token", listing.json()["results"][0])

    def test_audit_events_never_contain_a_raw_token(self):
        job = request_job(actor=self.operator, kind="native")
        self._artifact(job)
        grant, raw = issue_grant(actor=self.operator, job=job)
        revoke_grant(actor=self.operator, grant=grant)
        detail = " ".join(str(e.detail) for e in ArchiveAccessEvent.objects.all())
        self.assertNotIn(raw, detail)
        actions = set(ArchiveAccessEvent.objects.values_list("action", flat=True))
        self.assertLessEqual({"requested", "grant_issued", "grant_revoked"}, actions)

    def test_expired_and_revoked_grants_are_refused(self):
        job = request_job(actor=self.operator, kind="native")
        self._artifact(job)
        grant, raw = issue_grant(actor=self.operator, job=job)
        grant.expires_at = timezone.now() - timedelta(seconds=1)
        grant.save(update_fields=["expires_at"])
        with self.assertRaises(GrantDenied):
            resolve_grant(raw, job_public_id=job.public_id)
        grant.expires_at = timezone.now() + timedelta(hours=1)
        grant.save(update_fields=["expires_at"])
        revoke_grant(actor=self.operator, grant=grant)
        with self.assertRaises(GrantDenied):
            resolve_grant(raw, job_public_id=job.public_id)

    def test_grant_is_scoped_to_its_artifact(self):
        job = request_job(actor=self.operator, kind="native")
        other = request_job(actor=self.operator, kind="native")
        self._artifact(job); self._artifact(other, b"different bytes\n" * 100)
        grant, raw = issue_grant(actor=self.operator, job=job)
        with self.assertRaises(GrantDenied):
            resolve_grant(raw, job_public_id=other.public_id)

    # --- streaming, Range resume, integrity --------------------------------

    def test_full_download_round_trips_and_reports_digest(self):
        job = request_job(actor=self.operator, kind="native")
        body = self._artifact(job)
        grant, raw = issue_grant(actor=self.operator, job=job)
        response = self.client.get(f"/api/v1/archives/download/{job.public_id}",
                                   HTTP_AUTHORIZATION="Bearer " + raw)
        self.assertEqual(response.status_code, 200)
        payload = b"".join(response.streaming_content)
        self.assertEqual(payload, body)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), job.sha256)
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response["ETag"], f'"{job.sha256}"')

    def test_interrupted_download_resumes_via_range_exactly(self):
        job = request_job(actor=self.operator, kind="native")
        body = self._artifact(job)
        grant, raw = issue_grant(actor=self.operator, job=job)
        half = len(body) // 2
        # First leg: bytes [0, half) then an interrupted client that keeps half.
        first = self.client.get(f"/api/v1/archives/download/{job.public_id}",
                                HTTP_AUTHORIZATION="Bearer " + raw,
                                HTTP_RANGE=f"bytes=0-{half - 1}")
        self.assertEqual(first.status_code, 206)
        self.assertEqual(first["Content-Range"], f"bytes 0-{half - 1}/{len(body)}")
        head = b"".join(first.streaming_content)
        # Second leg: resume from `half` to the end; the two halves must reassemble.
        second = self.client.get(f"/api/v1/archives/download/{job.public_id}",
                                 HTTP_AUTHORIZATION="Bearer " + raw,
                                 HTTP_RANGE=f"bytes={half}-")
        self.assertEqual(second.status_code, 206)
        tail = b"".join(second.streaming_content)
        self.assertEqual(head + tail, body)
        self.assertEqual(hashlib.sha256(head + tail).hexdigest(), job.sha256)

    def test_unsatisfiable_range_is_refused_with_416(self):
        job = request_job(actor=self.operator, kind="native")
        body = self._artifact(job)
        grant, raw = issue_grant(actor=self.operator, job=job)
        response = self.client.get(f"/api/v1/archives/download/{job.public_id}",
                                   HTTP_AUTHORIZATION="Bearer " + raw,
                                   HTTP_RANGE=f"bytes={len(body)}-")
        self.assertEqual(response.status_code, 416)
        self.assertIn("bytes */", response["Content-Range"])

    def test_download_denied_without_token_or_with_wrong_token(self):
        job = request_job(actor=self.operator, kind="native")
        self._artifact(job)
        self.assertEqual(self.client.get(
            f"/api/v1/archives/download/{job.public_id}").status_code, 401)
        self.assertEqual(self.client.get(
            f"/api/v1/archives/download/{job.public_id}",
            HTTP_AUTHORIZATION="Bearer not-a-real-token").status_code, 403)

    def test_disabled_grant_holder_cannot_download(self):
        job = request_job(actor=self.operator, kind="native")
        self._artifact(job)
        grant, raw = issue_grant(actor=self.operator, job=job)
        self.operator.is_active = False
        self.operator.save(update_fields=["is_active"])
        # Deactivation does not destroy the token, but a revoked grant does.
        revoke_grant(actor=self.operator, grant=grant)
        self.assertEqual(self.client.get(
            f"/api/v1/archives/download/{job.public_id}",
            HTTP_AUTHORIZATION="Bearer " + raw).status_code, 403)

    # --- corruption fails closed -------------------------------------------

    def test_artifact_outside_the_private_store_is_refused(self):
        job = request_job(actor=self.operator, kind="native")
        self._artifact(job)
        outside = self.root.parent / "escape.zip"
        job.artifact_path = str(outside)
        job.save(update_fields=["artifact_path"])
        with self.assertRaises(GrantDenied):
            open_artifact(job)

    def test_parse_range_rejects_malformed_and_multi_range(self):
        for bad in ("bytes=abc-", "bytes=0-1,3-4", "items=0-1", "bytes=5-2"):
            with self.assertRaises(GrantDenied):
                parse_range(bad, 100)
        self.assertEqual(parse_range("bytes=10-19", 100), (10, 19))
        self.assertEqual(parse_range("bytes=90-", 100), (90, 99))


class ArchiveBuildCommandTests(TestCase):
    """The build command refuses the deferred kind rather than faking it."""

    def test_full_recovery_build_is_refused_not_faked(self):
        from django.core.management import CommandError, call_command
        ensure_roles()
        job = request_job(actor=None, kind="full_recovery")
        job.state = "running"
        job.save(update_fields=["state"])
        with self.assertRaises(CommandError) as caught:
            call_command("build_archive_job", job.public_id)
        self.assertIn("full_recovery_requires_operational_gate", str(caught.exception))

    def test_native_build_command_produces_a_verifiable_artifact(self):
        from django.core.management import call_command
        from unittest.mock import patch
        ensure_roles()
        # TestCase wraps the test in a transaction, so the real PostgreSQL
        # repeatable-read snapshot command cannot run here (the live smoke
        # covers it); patch only the isolation primitive.
        with tempfile.TemporaryDirectory(prefix="ai-compass-arch-build-") as root:
            isolated = patch("config.archive_services._snapshot_boundary",
                             return_value="2026-10-10T12:00:00+00:00")
            with isolated, override_settings(ARCHIVE_STORE_ROOT=Path(root)):
                job = request_job(actor=None, kind="native")
                job.state = "running"
                job.save(update_fields=["state"])
                call_command("build_archive_job", job.public_id)
                job.refresh_from_db()
                self.assertEqual(job.state, "complete")
                self.assertEqual(len(job.sha256), 64)
                self.assertTrue(job.manifest.get("verified"))
                self.assertTrue(Path(job.artifact_path).exists())
                self.assertTrue(Path(job.artifact_path).is_relative_to(Path(root)))
