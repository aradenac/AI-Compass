"""PLAT-32 cross-role Server acceptance journey, using real persisted domain APIs.

Extends the domain suites rather than mocking business data or duplicating
individual feature implementations. Demo fixtures are NEVER imported.
"""
import hashlib
import json
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import (BenchmarkRun, CatalogItem, CatalogRevision, EvidenceBlob,
                     EvidenceLink, EvaluationSnapshot, RecommendationSnapshot)
from .test_evaluations import ResultsAndEvaluationTests


class ReleaseJourneyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ResultsAndEvaluationTests.setUpTestData.__func__(cls)
        cls.reviewer = get_user_model().objects.create_user(
            "release-reviewer", password="Release-Safe-Password-2026")
        cls.reviewer.groups.add(Group.objects.get(name="reviewer"))

    setUp = ResultsAndEvaluationTests.setUp
    call = ResultsAndEvaluationTests.call
    as_user = ResultsAndEvaluationTests.as_user
    measured = ResultsAndEvaluationTests.measured
    evaluation = ResultsAndEvaluationTests.evaluation

    def test_task_case_campaign_session_run_evidence_evaluation_review(self):
        with tempfile.TemporaryDirectory(prefix="readiness-evidence-") as root:
            with override_settings(EVIDENCE_STORE_ROOT=Path(root)):
                reader, _ = self.as_user(self.reader)
                maintainer, _ = self.as_user(self.maint)
                # The new Server exposes zero measured data, not fake Demo items.
                self.assertEqual(reader.get("/api/v1/runs").json()["results"], [])
                self.assertEqual(reader.get("/api/v1/recommendations").json()["results"], [])

                # These helpers traverse authenticated HTTP endpoints:
                # Task + TC -> Campaign -> Session -> Interaction -> Run.
                baseline_task_revision = str(self.task.item.current_revision_id)
                baseline_case_revision = str(self.case.item.current_revision_id)
                run = self.measured()
                self.assertEqual(run["outcome"], "accepted")
                self.assertEqual(BenchmarkRun.objects.count(), 1)
                immutable_metrics = BenchmarkRun.objects.get(public_id=run["id"]).metrics.copy()

                original_bytes = b"Twister run passed; original SPI driver trace\n"
                attached = self.client.post(
                    "/api/v1/catalog/items/" + self.case.item.public_id + "/evidence/upload",
                    data={"file": SimpleUploadedFile("twister.txt", original_bytes),
                          "revision": "r001",
                          "source": "readiness:real-test-case",
                          "provenance": json.dumps({"unknown_extension": None})},
                    HTTP_X_CSRFTOKEN=self.token,
                )
                self.assertEqual(attached.status_code, 201, attached.content)
                evidence = attached.json()
                self.assertEqual(evidence["sha256"], hashlib.sha256(original_bytes).hexdigest())

                interpreted = self.evaluation([run["id"]])
                self.assertTrue(interpreted["id"].startswith("evl-"))
                created = self.call("/api/v1/recommendations", {
                    "name": "Release acceptance decision",
                    "task_id": self.task.item.public_id,
                    "solution_id": run["solution_id"],
                    "run_ids": [run["id"]],
                    "evaluation_id": interpreted["id"],
                    "evaluation_revision": "r001",
                    "properties": {
                        "decision": "recommended",
                        "rationale": "Controlled real Server test run with Twister evidence",
                        "extensions": {"future_property": None},
                    },
                })
                self.assertEqual(created.status_code, 201, created.content)
                recommendation = created.json()
                self.assertEqual(reader.get(
                    "/api/v1/recommendations/" + recommendation["id"]).status_code, 404)
                self.assertEqual(maintainer.get("/api/v1/runs").status_code, 403)

                submitted = self.call(
                    "/api/v1/recommendations/" + recommendation["id"] + "/actions/submit",
                    {"expected_revision": "r001"},
                )
                self.assertEqual(submitted.status_code, 200, submitted.content)
                review, review_csrf = self.as_user(self.reviewer)
                rejected = self.call(
                    "/api/v1/recommendations/" + recommendation["id"] + "/actions/publish",
                    {"expected_revision": "r002", "review_note": "unauthorized engineer"},
                )
                self.assertEqual(rejected.status_code, 403)
                published = self.call(
                    "/api/v1/recommendations/" + recommendation["id"] + "/actions/publish",
                    {"expected_revision": "r002",
                     "review_note": "Inspected original Twister test result and pinned revisions"},
                    browser=review, token=review_csrf,
                )
                self.assertEqual(published.status_code, 200, published.content)

                # Fresh reader browser gets genuine persisted data via Server.
                fresh_reader, _ = self.as_user(self.reader)
                public = fresh_reader.get(
                    "/api/v1/recommendations/" + recommendation["id"])
                self.assertEqual(public.status_code, 200, public.content)
                self.assertEqual(public.json()["state"], "published")
                self.assertEqual(public.json()["run_refs"][0]["status"], "unavailable")
                self.assertFalse(public.json()["eligible_for_current_suitability"])
                downloaded = fresh_reader.get(
                    "/api/v1/evidence/" + evidence["id"] + "/download")
                self.assertEqual(downloaded.status_code, 200, downloaded.content
                                 if not downloaded.streaming else "download")
                self.assertEqual(b"".join(downloaded.streaming_content), original_bytes)
                self.assertEqual(BenchmarkRun.objects.get(public_id=run["id"]).metrics,
                                 immutable_metrics)
                self.assertEqual(str(self.task.item.current_revision_id),
                                 baseline_task_revision)
                self.assertEqual(str(self.case.item.current_revision_id),
                                 baseline_case_revision)
                self.assertEqual(CatalogRevision.objects.filter(
                    item__public_id=recommendation["id"]).count(), 3)
                self.assertEqual(EvaluationSnapshot.objects.count(), 1)
                self.assertEqual(RecommendationSnapshot.objects.count(), 3)
                self.assertEqual(EvidenceBlob.objects.count(), 1)
                self.assertEqual(EvidenceLink.objects.count(), 1)
                self.assertEqual(CatalogItem.objects.get(
                    public_id=recommendation["id"]).current_revision.properties
                    ["extensions"]["future_property"], None)
