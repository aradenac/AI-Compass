"""DAP-01: planning confidentiality, effective inheritance and immutable snapshots."""
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase, override_settings

from .identity import ensure_roles
from .models import WorkloadProfile, WorkloadRevision, WorkloadAllocation
from .task_services import create_task

API = "/api/v1/planning/profiles"


class PlanningApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User = get_user_model()
        cls.planner = User.objects.create_user("planning-operator", password="StrongTestPassword2026!")
        cls.planner.groups.add(Group.objects.get(name="deployment-planner"))
        cls.contributor = User.objects.create_user("planning-contributor", password="StrongTestPassword2026!")
        cls.contributor.groups.add(Group.objects.get(name="contributor"))
        cls.maintainer = User.objects.create_user("planning-maintainer", password="StrongTestPassword2026!")
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))
        cls.user_admin = User.objects.create_user("planning-useradmin", password="StrongTestPassword2026!")
        cls.user_admin.groups.add(Group.objects.get(name="user-admin"))
        cls.root = create_task(actor=cls.contributor, name="Embedded development",
                               properties={"future": {"nullable": None}})
        cls.driver = create_task(actor=cls.contributor, name="Driver implementation",
                                 parent_id=cls.root.item.public_id)
        cls.other = create_task(actor=cls.contributor, name="Regression test")

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.csrf = self.client.cookies["csrftoken"].value
        self.client.force_login(self.planner)

    def send(self, path, body, method="POST", csrf=True):
        if method == "PATCH":
            func = self.client.patch
        else:
            func = self.client.post
        return func(path, json.dumps(body), content_type="application/json",
                    **({"HTTP_X_CSRFTOKEN": self.csrf} if csrf else {}))

    def create(self, kind, name, workloads=(), **extra):
        body = {"kind": kind, "name": name, "workloads": list(workloads), **extra}
        r = self.send(API, body)
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def line(self, task, freq, hours=None, excluded=False):
        return {"task_id": task.item.public_id, "annual_occurrences": freq,
                "baseline_human_hours": hours, "excluded": excluded}

    def test_empty_server_permissions_csrf_and_no_demo_fallback(self):
        self.assertEqual(self.client.get(API).json(), {"results": []})
        self.assertEqual(self.client.get("/api/v1/planning/tasks").status_code, 200)
        self.assertEqual(self.send(API, {"kind": "role", "name": "X"}, csrf=False).status_code, 403)
        for actor, expected in ((self.contributor, 403), (self.maintainer, 403),
                                (self.user_admin, 403)):
            browser = Client()
            browser.force_login(actor)
            self.assertEqual(browser.get(API).status_code, expected)
            self.assertEqual(browser.get("/api/v1/planning/tasks").status_code, expected)
        self.client.logout()
        self.assertEqual(self.client.get(API).status_code, 401)

    def test_role_specialty_inherit_conflict_override_null_vs_zero_and_cohort(self):
        role = self.create("role", "Embedded developer", [
            self.line(self.driver, "12.00", "3.50"),
            self.line(self.other, "0.00"),
        ], hourly_rate_eur="65.00")
        spec = self.create("specialty", "MCU", [
            self.line(self.driver, "15.00", "4.00"),
            self.line(self.root, "10.00"),
        ])
        person = self.create("person", "Collaborator planning profile", [
            self.line(self.other, None),
        ], role_id=role["id"], specialty_id=spec["id"])
        r = self.client.get(API+"/"+person["id"]+"/effective")
        self.assertEqual(r.status_code, 200, r.content)
        rows = {r["task_id"]: r for r in r.json()["workloads"]}
        self.assertEqual(rows[self.driver.item.public_id]["status"], "ambiguous")
        self.assertIsNone(rows[self.driver.item.public_id]["annual_occurrences"])
        self.assertEqual(rows[self.other.item.public_id]["status"], "unknown")
        self.assertEqual(rows[self.other.item.public_id]["source"], "explicit")
        self.assertEqual(r.json()["hourly_rate_source"]["rate_eur"], "65.00")
        self.assertEqual(r.json()["annual_gain_eur"], None)
        # Override does NOT add role and specialty frequencies.
        new = self.send(API+"/"+person["id"], {
            "expected_revision": "r001", "name": person["name"],
            "role_id": role["id"], "specialty_id": spec["id"],
            "workloads": [self.line(self.driver, "22.00", "2.00"),
                           self.line(self.other, "0.00")],
            "hourly_rate_eur": "70.00",
        }, method="PATCH")
        self.assertEqual(new.status_code, 200, new.content)
        r2 = self.client.get(API+"/"+person["id"]+"/effective").json()
        rows2 = {x["task_id"]: x for x in r2["workloads"]}
        self.assertEqual(rows2[self.driver.item.public_id]["annual_occurrences"], "22.00")
        self.assertEqual(rows2[self.other.item.public_id]["status"], "zero")
        self.assertEqual(rows2[self.driver.item.public_id]["source"], "explicit")
        self.assertEqual(rows2[self.driver.item.public_id]["overlaps_ancestor_task"], True)
        self.assertEqual(r2["hourly_rate_source"]["rate_eur"], "70.00")
        cohort = self.create("cohort", "Ten engineers", [],
                             headcount=10, role_id=role["id"])
        cohort_workload = self.client.get(API+"/"+cohort["id"]+"/effective").json()
        c = {x["task_id"]: x for x in cohort_workload["workloads"]}
        self.assertEqual(c[self.driver.item.public_id]["annual_person_occurrences"], "120.00")
        self.assertEqual(c[self.other.item.public_id]["annual_person_occurrences"], "0.00")
        self.assertEqual(cohort_workload["headcount"], 10)

    def test_immutable_versions_and_conflict_rejection(self):
        role = self.create("role", "System Engineer", [
            self.line(self.driver, "2.00", "6.00"),
        ], hourly_rate_eur="80.00", notes={"unknown": None})
        old = self.client.get(API + "/" + role["id"] + "/revisions/1").json()
        revised = self.send(API+"/"+role["id"], {
            "expected_revision": "r001", "name": "System Engineer Senior",
            "hourly_rate_eur": "95.00",
            "workloads": [self.line(self.driver, "3.00", "4.00")],
            "notes": {"unknown": None},
        }, "PATCH")
        self.assertEqual(revised.status_code, 200, revised.content)
        self.assertEqual(revised.json()["revision"], "r002")
        self.assertEqual(self.client.get(API+"/"+role["id"]+"/revisions/1").json(), old)
        self.assertEqual(self.client.get(API+"/"+role["id"]+"/revisions").json()
                         ["revisions"][0]["hourly_rate_eur"], "80.00")
        self.assertEqual(self.send(API+"/"+role["id"], {
            "expected_revision": "r001", "name": "stale", "workloads": [],
        }, "PATCH").status_code, 409)
        row = WorkloadRevision.objects.get(profile__public_id=role["id"], number=1)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                WorkloadRevision.objects.filter(pk=row.pk).update(name="overwritten")
        allocation = WorkloadAllocation.objects.get(revision=row)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                WorkloadAllocation.objects.filter(pk=allocation.pk).delete()

    def test_validation_fails_closed_without_partial_rows(self):
        good = self.line(self.driver, "7.00")
        bad = [
            {"kind": "role", "name": "X", "workloads": [good, good]},
            {"kind": "role", "name": "X", "workloads": [self.line(self.driver, "-1")]},
            {"kind": "role", "name": "X", "workloads": [self.line(self.driver, "NaN")]},
            {"kind": "role", "name": "X", "workloads": [self.line(self.driver, "1.00", excluded=True),
                                                      self.line(self.other, "5")]},
            {"kind": "person", "name": "X", "headcount": 3, "workloads": []},
            {"kind": "cohort", "name": "X", "linked_user_id": self.contributor.id,
             "workloads": []},
            {"kind": "role", "name": "X", "hourly_rate_eur": "-80",
             "workloads": []},
            {"kind": "specialty", "name": "X", "role_id": "role-unknown",
             "workloads": []},
            {"kind": "role", "name": "X", "workloads": [
                {"task_id": self.driver.item.public_id, "annual_occurrences": "3",
                 "excluded": True}]},
        ]
        for payload in bad:
            with self.subTest(payload=payload):
                self.assertEqual(self.send(API, payload).status_code, 400)
        self.assertEqual(WorkloadProfile.objects.count(), 0)

    def test_native_export_includes_planning_history_without_credentials(self):
        from .archive_services import build_native_export
        p = self.create("role", "Controlled rates", [
            self.line(self.driver, "8.00", "2.00")], hourly_rate_eur="93.00")
        with tempfile.TemporaryDirectory() as folder, \
             override_settings(EVIDENCE_STORE_ROOT=Path(folder)), \
             patch("config.archive_services._snapshot_boundary",
                   return_value="2026-10-10T12:00:00+00:00"):
            archive = build_native_export()
            try:
                raw = archive.read()
            finally:
                archive.close()
        with zipfile.ZipFile(io.BytesIO(raw)) as content:
            names = content.namelist()
            self.assertIn("records/config.workloadprofile.ndjson", names)
            self.assertIn("records/config.workloadrevision.ndjson", names)
            self.assertIn("records/config.workloadallocation.ndjson", names)
            revisions = [json.loads(x) for x in
                         content.read("records/config.workloadrevision.ndjson").splitlines()]
            self.assertEqual(len(revisions), 1)
            self.assertEqual(revisions[0]["fields"]["hourly_rate_eur"], "93.00")
            self.assertNotIn(b"StrongTestPassword2026!", raw)
