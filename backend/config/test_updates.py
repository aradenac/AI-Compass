"""UX-R06: the published-only Workgroup Updates read model.

Real authentication and real APIs only: no mocked authorization, no Demo data.
"""
from django.test import Client

from . import test_engineer, test_publication, test_runs
from .models import CatalogItem
from .watch_services import create as create_watch

BASE = "/api/v1/updates"
RECOMMENDATIONS = "/api/v1/recommendations"
_IndividualRunTests = test_runs.IndividualRunTests
_PublicationTests = test_publication.PublicationTests


class UpdatesJourneyTests(_IndividualRunTests.__bases__[0]):
    """Reuse the real Server fixture helpers, not the inherited test journeys."""

    setUpTestData = classmethod(_IndividualRunTests.setUpTestData.__func__)
    setUp = _IndividualRunTests.setUp
    send = _IndividualRunTests.send
    campaign = _IndividualRunTests.campaign
    session = _IndividualRunTests.session
    interaction = _IndividualRunTests.interaction
    result = _IndividualRunTests.result
    close = _IndividualRunTests.close
    ready_guide = _PublicationTests.ready_guide
    completed = _PublicationTests.completed
    review = _PublicationTests.review
    publisher = _PublicationTests.publisher
    public_guide = test_engineer.EngineerJourneyTests.public_guide

    def published(self, outcome="accepted"):
        self.public_guide()
        camp = self.campaign()
        run = self.completed(camp, outcome=outcome)
        reviewed = self.review(camp)
        self.publisher()
        response = _PublicationTests.publish(self, reviewed, [run["id"]])
        self.assertEqual(response.status_code, 200, response.content)
        return camp, run, response

    def reader_client(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/api/v1/auth/csrf")
        client.force_login(self.reader)
        return client

    def test_requires_a_real_business_read_grant(self):
        self.assertEqual(Client().get(BASE).status_code, 401)
        denied = Client()
        denied.force_login(self.maint)
        self.assertEqual(denied.get(BASE).status_code, 403)
        allowed = self.reader_client().get(BASE)
        self.assertEqual(allowed.status_code, 200, allowed.content)
        self.assertIn("no-store", allowed.headers["Cache-Control"])
        self.assertEqual(self.reader_client().get(BASE + "?scope=private").status_code, 400)
        self.assertEqual(self.reader_client().get(BASE + "?kind=draft").status_code, 400)

    def test_drafts_internal_and_theoretical_records_never_appear(self):
        self.campaign()  # planned draft campaign, never published
        create_watch("watch_entry", self.editor, "Internal hypothesis", {
            "hypothesis": "Unreviewed internal hypothesis", "review_state": "draft",
            "visibility": "internal"})
        payload = self.reader_client().get(BASE).json()
        kinds = {entry["kind"] for entry in payload["items"]}
        self.assertNotIn("campaign_published", kinds)
        self.assertNotIn("watch_published", kinds)
        self.assertNotIn("guide_published", kinds)
        self.assertNotIn("recommendation_published", kinds)
        self.assertEqual(payload["scope"], "published_only")
        # Review #134 / UX-R06 #125: the reader is told what is excluded, never
        # how many restricted records exist (no existence/volume disclosure).
        for value in payload["excluded"].values():
            self.assertNotIsInstance(value, int)
        self.assertEqual(payload["excluded"]["unpublished_or_draft_records"],
                         "never included")
        self.assertEqual(payload["excluded"]["activity_feed_and_audit_events"],
                         "never included")
        self.assertEqual(payload["excluded"]["discussions_internal_or_private"],
                         "never included")
        self.assertEqual(payload["excluded"]["theoretical_forecasts"], "never included")

    def test_restricted_existence_counts_are_not_disclosed_to_any_reader(self):
        # Two real authenticated privilege levels: a Workspace reader
        # (business_read only) and a full Workgroup editor. Neither response may
        # carry a count of unpublished/draft/internal records, which would leak
        # their existence and volume across the published-only boundary.
        self.campaign()
        create_watch("watch_entry", self.editor, "Internal hypothesis", {
            "hypothesis": "Unreviewed internal hypothesis", "review_state": "draft",
            "visibility": "internal"})
        workgroup = Client(enforce_csrf_checks=True)
        workgroup.get("/api/v1/auth/csrf")
        workgroup.force_login(self.editor)
        for label, client in (("reader", self.reader_client()), ("workgroup", workgroup)):
            allowed = client.get(BASE)
            self.assertEqual(allowed.status_code, 200, allowed.content)
            payload = allowed.json()
            self.assertEqual(payload["scope"], "published_only", label)
            self.assertEqual(set(payload["excluded"]),
                             {"unpublished_or_draft_records",
                              "discussions_internal_or_private",
                              "activity_feed_and_audit_events",
                              "theoretical_forecasts"}, label)
            for value in payload["excluded"].values():
                self.assertNotIsInstance(value, int, label)

    def test_published_sources_carry_exact_origin_ids_and_revisions(self):
        camp, run, _ = self.published()
        payload = self.reader_client().get(BASE).json()
        by_kind = {}
        for entry in payload["items"]:
            by_kind.setdefault(entry["kind"], []).append(entry)
        self.assertEqual(len(by_kind["campaign_published"]), 1)
        campaign_item = by_kind["campaign_published"][0]
        self.assertEqual(campaign_item["source"]["object_id"], camp["id"])
        self.assertTrue(campaign_item["source"]["revision"].startswith("r"))
        self.assertIn("active published measured Run(s)", campaign_item["summary"])
        measured = by_kind["measured_result"][0]
        self.assertEqual(measured["source"]["object_id"], run["id"])
        self.assertEqual(measured["source"]["section"], "results")
        self.assertEqual(measured["parent"]["campaign_id"], camp["id"])
        self.assertTrue(measured["measured"])
        guide_item = by_kind["guide_published"][0]
        self.assertEqual(guide_item["source"]["object_id"], self.guide.public_id)
        self.assertTrue(guide_item["source"]["revision"].startswith("r"))

    def test_failed_published_run_is_negative_evidence_not_a_recommendation(self):
        self.published(outcome="failed")
        payload = self.reader_client().get(BASE).json()
        measured = [entry for entry in payload["items"]
                    if entry["kind"] == "measured_result"]
        self.assertEqual(len(measured), 1)
        self.assertIn("failed Definition of Done", measured[0]["summary"])
        self.assertIn("never an endorsement", measured[0]["notice"])
        self.assertFalse([entry for entry in payload["items"]
                          if entry["kind"] == "recommendation_published"])

    def test_editorial_recommendation_keeps_its_pinned_task_solution_and_runs(self):
        camp, run, _ = self.published()
        self.client.force_login(self.editor)
        created = self.send(RECOMMENDATIONS, {
            "name": "Driver coding recommendation",
            "task_id": self.task.item.public_id,
            "solution_id": run["solution_id"],
            "run_ids": [run["id"]],
            "properties": {"decision": "conditional",
                           "rationale": "Situational fit under one method",
                           "limitations": "Single evaluation scenario"}})
        self.assertEqual(created.status_code, 201, created.content)
        record = created.json()
        submitted = self.send(RECOMMENDATIONS + "/" + record["id"] + "/actions/submit",
                              {"expected_revision": record["revision"]})
        self.assertEqual(submitted.status_code, 200, submitted.content)
        self.publisher()
        published = self.send(RECOMMENDATIONS + "/" + record["id"] + "/actions/publish", {
            "expected_revision": submitted.json()["record"]["revision"],
            "review_note": "Reviewed original measured evidence"})
        self.assertEqual(published.status_code, 200, published.content)
        payload = self.reader_client().get(BASE).json()
        editorial = [entry for entry in payload["items"]
                     if entry["kind"] == "recommendation_published"]
        self.assertEqual(len(editorial), 1)
        self.assertEqual(editorial[0]["source"]["object_id"], record["id"])
        self.assertEqual(editorial[0]["pins"]["task_id"], self.task.item.public_id)
        self.assertEqual(editorial[0]["pins"]["solution_id"], run["solution_id"])
        self.assertEqual(editorial[0]["pins"]["original_run_pins"], 1)
        self.assertIn("never overrides", editorial[0]["notice"])
        self.assertFalse(editorial[0]["measured"])
        self.assertNotEqual(editorial[0]["source"]["object_id"], camp["id"])

    def test_withdrawn_campaign_evidence_leaves_the_public_view(self):
        camp, run, _ = self.published()
        self.publisher()
        current = self.client.get("/api/v1/campaigns/" + camp["id"]).json()
        revoked = self.send("/api/v1/campaigns/" + camp["id"] + "/publication/withdraw",
                            {"expected_revision": current["revision"]})
        self.assertEqual(revoked.status_code, 200, revoked.content)
        payload = self.reader_client().get(BASE).json()
        kinds = {entry["kind"] for entry in payload["items"]}
        self.assertNotIn("campaign_published", kinds)
        self.assertNotIn("measured_result", kinds)
        self.assertEqual(payload["excluded"]["unpublished_or_draft_records"],
                         "never included")
        self.assertEqual(CatalogItem.objects.filter(
            type_slug="campaign", public_id=camp["id"]).count(), 1)
