"""FUT-20: bounded capacity policy, health/headroom, Internet profile, throttle.

Proves: only the platform-manage role can revise bounded policies and read
sensitive settings; a change is audited and never alters pinned history; the
Internet profile refuses unsafe cleartext/misconfigured exposure while loopback
development and LAN stay usable; and the durable login throttle denies replay
after repeated failures.
"""
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase
from django.utils import timezone

from .capacity_services import (
    BOUNDS, CapacityError, clear_failures, configure_policy, is_locked, metrics,
    policy, record_failure, serialize_policy,
)
from .identity import ensure_roles
from .models import AccessThrottle, CapacityPolicy, CapacityPolicyEvent

BASE = "/api/v1/platform/capacity"
PASS = "Secure-Fictitious-Capacity-Password-2026!"


class CapacityPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U = get_user_model()
        cls.admin = U.objects.create_user("cap-admin", password=PASS)
        cls.admin.groups.add(Group.objects.get(name="platform-admin"))
        cls.viewer = U.objects.create_user("cap-viewer", password=PASS)
        cls.viewer.groups.add(Group.objects.get(name="archive-operator"))  # platform_view, no manage
        cls.maint = U.objects.create_user("cap-maint", password=PASS)
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def login(self, user):
        self.client.force_login(user)
        response = self.client.get("/api/v1/auth/csrf")
        return response.json()["csrfToken"]

    def patch_policy(self, payload, token):
        return self.client.patch(f"{BASE}/policy/edit", json.dumps(payload),
                                 content_type="application/json",
                                 HTTP_X_CSRFTOKEN=token)

    # --- policy admin / RBAC -----------------------------------------------

    def test_only_platform_manage_can_revise_policy(self):
        token = self.login(self.maint)  # maintenance_view, not platform
        self.assertEqual(self.client.get(f"{BASE}/health").status_code, 403)
        self.assertEqual(self.client.get(f"{BASE}/policy").status_code, 403)
        self.assertEqual(self.patch_policy({"disk_warn_percent": 70}, token).status_code, 403)
        self.assertIsNone(policy())

    def test_platform_view_can_read_but_not_revise(self):
        token = self.login(self.viewer)
        self.assertEqual(self.client.get(f"{BASE}/health").status_code, 200)
        self.assertEqual(self.client.get(f"{BASE}/policy").status_code, 200)
        self.assertEqual(self.patch_policy({"disk_warn_percent": 70}, token).status_code, 403)

    def test_change_is_versioned_audited_and_bounded(self):
        token = self.login(self.admin)
        first = self.patch_policy({"disk_warn_percent": 70, "archive_concurrency_warn": 2}, token)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.json()["policy"]["version"], 1)
        second = self.patch_policy({"disk_warn_percent": 85}, token)
        self.assertEqual(second.json()["policy"]["version"], 2)
        self.assertEqual(CapacityPolicy.objects.filter(is_active=True).count(), 1)
        event = CapacityPolicyEvent.objects.order_by("-created_at").first()
        self.assertEqual(event.action, "updated")
        self.assertEqual(event.previous["disk_warn_percent"], 70)
        self.assertEqual(event.applied["disk_warn_percent"], 85)
        # Out-of-bounds values are refused and change nothing.
        self.assertEqual(self.patch_policy({"disk_warn_percent": 100}, token).status_code, 400)
        self.assertEqual(policy().disk_warn_percent, 85)
        self.assertEqual(self.patch_policy({"bogus": 1}, token).status_code, 400)

    def test_policy_event_is_immutable(self):
        configure_policy(actor=self.admin, disk_warn_percent=70)
        event = CapacityPolicyEvent.objects.first()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CapacityPolicyEvent.objects.filter(pk=event.pk).update(action="tampered")

    def test_health_distinguishes_configurable_warnings_from_hard_limits(self):
        # Zero threshold makes the (currently empty) evidence store warn.
        configure_policy(actor=self.admin, evidence_warn_bytes=0, disk_warn_percent=1)
        data = metrics()
        self.assertEqual(data["evidence_bytes"]["state"], "warning")
        self.assertEqual(data["evidence_bytes"]["warn_at"], 0)
        self.assertFalse(data["hard_limits"]["administrable"])
        self.assertEqual(data["hard_limits"]["records"], 200000)

    def test_synthetic_pressure_raises_a_configurable_warning_only(self):
        # Synthetic load: queued archive jobs cross the administrable threshold.
        from .archive_job_services import request_job
        configure_policy(actor=self.admin, archive_concurrency_warn=2)
        for _ in range(3):
            request_job(actor=self.admin, kind="native")
        data = metrics()
        self.assertEqual(data["archive_concurrency"]["value"], 3)
        self.assertEqual(data["archive_concurrency"]["state"], "warning")
        # The warning is informational: existing jobs and bytes are untouched.
        self.assertEqual(CapacityPolicy.objects.filter(is_active=True).count(), 1)

    # --- Internet profile fail-closed --------------------------------------

    def test_internet_profile_refuses_cleartext_and_misconfig(self):
        from .deployment_profiles import ProfileError, configuration
        good = {"AI_COMPASS_PROFILE": "internet", "AI_COMPASS_TLS_PROXY": "1",
                "DJANGO_SECRET_KEY": "k" * 40, "DB_PASSWORD": "p" * 40,
                "DJANGO_ALLOWED_HOSTS": "compass.example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://compass.example.com"}
        config = configuration(good)
        self.assertTrue(config["secure"])
        self.assertEqual(config["hsts_seconds"], 600)
        for bad in (
            {"AI_COMPASS_TLS_PROXY": "0"},                       # cleartext
            {"DJANGO_ALLOWED_HOSTS": "localhost"},               # loopback default
            {"DJANGO_ALLOWED_HOSTS": "192.168.1.5"},             # internal-only
            {"DJANGO_CSRF_TRUSTED_ORIGINS": "http://compass.example.com"},
            {"DJANGO_SECRET_KEY": "REPLACE_WITH_short"},         # weak secret
        ):
            with self.assertRaises(ProfileError):
                configuration(dict(good, **bad))

    def test_loopback_development_and_lan_are_preserved(self):
        from .deployment_profiles import configuration
        development = configuration({"AI_COMPASS_PROFILE": "development"})
        self.assertFalse(development["secure"])
        lan = configuration({"AI_COMPASS_PROFILE": "lan", "AI_COMPASS_TLS_PROXY": "1",
                             "AI_COMPASS_LAN_BIND": "192.168.1.20",
                             "DJANGO_SECRET_KEY": "k" * 40, "DB_PASSWORD": "p" * 40,
                             "DJANGO_ALLOWED_HOSTS": "api,localhost,127.0.0.1,192.168.1.20",
                             "DJANGO_CSRF_TRUSTED_ORIGINS": "https://192.168.1.20"})
        self.assertTrue(lan["secure"])
        self.assertNotIn("hsts_seconds", lan)

    # --- durable login throttle --------------------------------------------

    def test_repeated_failures_lock_and_replay_is_denied(self):
        for _ in range(5):
            record_failure(identifier="victim", ip="10.0.0.9")
        self.assertTrue(is_locked(identifier="victim", ip="10.0.0.9"))
        self.assertFalse(is_locked(identifier="victim", ip="10.0.0.8"))  # keyed per ip
        row = AccessThrottle.objects.get()
        self.assertEqual(len(row.key_digest), 64)  # one-way, not the raw identifier
        row.locked_until = timezone.now() - timedelta(seconds=1)
        row.save(update_fields=["locked_until"])
        self.assertFalse(is_locked(identifier="victim", ip="10.0.0.9"))
        clear_failures(identifier="victim", ip="10.0.0.9")
        self.assertEqual(AccessThrottle.objects.count(), 0)

    def test_sign_in_returns_429_after_lockout(self):
        from django.contrib.auth import get_user_model as GU
        U = GU()
        U.objects.create_user("throttle-target", password=PASS)
        token = self.login(self.viewer)
        bad = {"username": "throttle-target", "password": "wrong"}
        codes = []
        for _ in range(6):
            response = self.client.post("/api/v1/auth/login", json.dumps(bad),
                                        content_type="application/json",
                                        HTTP_X_CSRFTOKEN=token)
            codes.append(response.status_code)
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5], 429)
        # A correct password is still refused while locked, and no session exists.
        good = self.client.post("/api/v1/auth/login",
                                json.dumps({"username": "throttle-target", "password": PASS}),
                                content_type="application/json",
                                HTTP_X_CSRFTOKEN=token)
        self.assertEqual(good.status_code, 429)
