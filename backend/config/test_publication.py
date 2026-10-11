"""FUT-10: end-to-end published subset, private draft and immutable re-review."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client

from .test_runs import IndividualRunTests
from .setup_guide_services import revise as revise_guide
from .identity import ensure_roles
from .models import CatalogRevision
from .publication_services import effective_ids


class PublicationTests(IndividualRunTests.__bases__[0]):
    # Reuse real Server API fixture helpers, not the inherited test cases.
    setUpTestData = classmethod(IndividualRunTests.setUpTestData.__func__)
    setUp = IndividualRunTests.setUp
    send = IndividualRunTests.send
    campaign = IndividualRunTests.campaign
    session = IndividualRunTests.session
    interaction = IndividualRunTests.interaction
    result = IndividualRunTests.result
    close = IndividualRunTests.close

    def ready_guide(self):
        # The historical text at r001 remains the pinned module; the new
        # recipe can be evaluated without contacting a remote setup service.
        revised, _ = revise_guide(
            actor=self.editor, public_id=self.guide.public_id,
            expected_revision="r001", properties={"recipe": {
                "modules": [{"id": self.guide.public_id, "revision": "r001"}],
                "required": ["model", "provider", "harness"]}})
        self.assertEqual(revised.current_revision.number, 2)

    def completed(self, campaign, outcome="accepted"):
        session = self.session(campaign)
        interaction = self.interaction(session)
        closed = self.close(session, self.result(outcome=outcome))
        self.assertEqual(closed.status_code, 201, closed.content)
        return closed.json()

    def review(self, campaign):
        closed = self.send("/api/v1/campaigns/" + campaign["id"] + "/actions/close",
                           {"expected_revision": campaign["revision"]})
        self.assertEqual(closed.status_code, 200, closed.content)
        return closed.json()["campaign"]

    def publisher(self):
        reviewer, _ = get_user_model().objects.get_or_create(
            username="publisher-" + str(self.editor.pk)[:8],
            defaults={"is_active": True})
        reviewer.groups.add(Group.objects.get(name="reviewer"))
        self.client.force_login(reviewer)
        return reviewer

    def publish(self, campaign, ids, reason=""):
        return self.send("/api/v1/campaigns/" + campaign["id"] +
                         "/publication/publish", {
            "expected_revision": campaign["revision"], "run_ids": ids,
            "removal_reason": reason})

    def test_private_measured_run_requires_selected_ready_guide_and_review_role(self):
        camp = self.campaign()
        run = self.completed(camp)
        reviewed = self.review(camp)
        self.publisher()
        rejected = self.publish(reviewed, [run["id"]])
        self.assertEqual(rejected.status_code, 409, rejected.content)
        self.assertIn("setup_recipe_not_adequate", rejected.json()["detail"])
        self.assertEqual(effective_ids(camp["id"]), set())
        self.assertEqual(CatalogRevision.objects.filter(
            item__public_id=camp["id"]).count(), 3)
        reader = Client()
        reader.force_login(self.reader)
        self.assertIsNone(reader.get("/api/v1/campaigns/" + camp["id"] +
                                     "/publication").json()["publication"])
        self.assertEqual(reader.get("/api/v1/runs/" + run["id"]).status_code, 404)
        self.assertEqual(reader.get("/api/v1/runs").json()["results"], [])
        self.assertEqual(reader.get("/api/v1/results/explorer").json()["results"], [])
        self.assertEqual(reader.get("/api/v1/campaigns/" + camp["id"] +
                                    "/publication/review").status_code, 403)
        self.assertEqual(reader.get("/api/v1/results/explorer?scope=private").status_code, 400)

    def test_publish_failure_dod_then_reopen_and_republish_preserves_old_selection(self):
        self.ready_guide()
        camp = self.campaign()
        original = self.completed(camp, outcome="failed")
        reviewed = self.review(camp)
        self.client.force_login(self.reader)
        self.assertEqual(self.send("/api/v1/campaigns/" + camp["id"] +
                                   "/publication/publish", {
            "expected_revision": reviewed["revision"],
            "run_ids": [original["id"]]}).status_code, 403)
        self.publisher()
        selected = self.publish(reviewed, [original["id"]])
        self.assertEqual(selected.status_code, 200, selected.content)
        pub = selected.json()["publication"]
        self.assertEqual(pub["runs"][0]["outcome"], "failed")
        self.assertEqual(pub["runs"][0]["guide"]["revision"], "r002")
        self.assertEqual(effective_ids(camp["id"]), {original["id"]})
        first_rev = pub["campaign_revision_id"]
        reader = Client()
        reader.force_login(self.reader)
        self.assertEqual(reader.get("/api/v1/results/explorer").json()
                         ["results"][0]["id"], original["id"])
        self.assertNotIn("raw_session_state",
                         reader.get("/api/v1/runs/" + original["id"]).json())

        self.client.force_login(self.editor)
        reopened_response = self.send("/api/v1/campaigns/" + camp["id"] +
                                      "/actions/reopen", {
            "expected_revision": selected.json()["campaign"]["revision"]})
        self.assertEqual(reopened_response.status_code, 200, reopened_response.content)
        reopened = reopened_response.json()["campaign"]
        newrun = self.completed(reopened)
        self.assertEqual(effective_ids(camp["id"]), {original["id"]})
        self.assertEqual(reader.get("/api/v1/runs/" + newrun["id"]).status_code, 404)
        again = self.review(reopened)
        self.publisher()
        error = self.publish(again, [newrun["id"]])
        self.assertEqual(error.status_code, 400)
        self.assertIn("removal", error.json()["detail"])
        second = self.publish(again, [newrun["id"]], reason="Replacement evidence selected")
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(effective_ids(camp["id"]), {newrun["id"]})
        old = self.client.get("/api/v1/campaigns/" + camp["id"] +
                              "/revisions/4").json()
        self.assertEqual(old["effective_publication"]["revision_id"], first_rev)

    def test_reopen_keeps_pins_after_setup_guide_correction(self):
        self.ready_guide()
        camp = self.campaign()
        run = self.completed(camp)
        reviewed = self.review(camp)
        self.publisher()
        published = self.publish(reviewed, [run["id"]])
        self.assertEqual(published.status_code, 200, published.content)
        pinned = published.json()["publication"]["runs"][0]["guide"]
        self.client.force_login(self.editor)
        revise_guide(actor=self.editor, public_id=self.guide.public_id,
                     expected_revision="r002", properties={"text": "Improved guide for next use"})
        current = self.client.get("/api/v1/campaigns/" + camp["id"] +
                                  "/publication").json()["publication"]
        self.assertEqual(current["runs"][0]["guide"], pinned)
        self.assertEqual(current["reviewed_by"], published.json()["publication"]["reviewed_by"])

    def test_explicit_withdrawal_after_reopening_keeps_working_plan_and_history(self):
        self.ready_guide()
        camp = self.campaign()
        run = self.completed(camp)
        reviewed = self.review(camp)
        self.publisher()
        published = self.publish(reviewed, [run["id"]])
        self.assertEqual(published.status_code, 200, published.content)
        original = published.json()["publication"]
        self.client.force_login(self.editor)
        reopened = self.send("/api/v1/campaigns/" + camp["id"] +
                             "/actions/reopen", {
            "expected_revision": published.json()["campaign"]["revision"]})
        self.assertEqual(reopened.status_code, 200, reopened.content)
        work = reopened.json()["campaign"]
        self.assertEqual(work["status"], "in_progress")
        self.assertEqual(effective_ids(camp["id"]), {run["id"]})
        self.publisher()
        stale = self.send("/api/v1/campaigns/" + camp["id"] +
                          "/publication/withdraw", {"expected_revision": "r003"})
        self.assertEqual(stale.status_code, 409, stale.content)
        withdrawn = self.send("/api/v1/campaigns/" + camp["id"] +
                              "/publication/withdraw", {
            "expected_revision": work["revision"]})
        self.assertEqual(withdrawn.status_code, 200, withdrawn.content)
        self.assertEqual(withdrawn.json()["campaign"]["status"], "in_progress")
        self.assertEqual(effective_ids(camp["id"]), set())
        old = self.client.get("/api/v1/campaigns/" + camp["id"] +
                              "/revisions/4").json()
        self.assertEqual(old["effective_publication"]["revision_id"],
                         original["campaign_revision_id"])
        reader = Client()
        reader.force_login(self.reader)
        self.assertEqual(reader.get("/api/v1/runs/" + run["id"]).status_code, 404)

    def test_matrix_partial_review_publishes_one_run_without_pending_second_cell(self):
        self.ready_guide()
        camp = self.campaign()
        path = "/api/v1/campaigns/" + camp["id"]
        for name in ("Measured setup", "Future alternative"):
            added = self.send(path + "/matrix/edit", {
                "expected_revision": camp["revision"],
                "operation": {
                    "action": "add_configuration",
                    "task_id": self.task.item.public_id,
                    "label": name,
                    "component_ids": {kind: item.public_id
                                      for kind, item in self.catalog.items()},
                    "test_case_ids": [self.case.item.public_id],
                }}, "PATCH")
            self.assertEqual(added.status_code, 200, added.content)
            camp = added.json()["campaign"]
        matrix = self.client.get(path + "/matrix").json()
        self.assertEqual(matrix["summary"]["pending"], 2)
        evaluation = matrix["cells"][0]
        created = self.send(path + "/sessions", {
            "test_case_id": self.case.item.public_id,
            "evaluation_id": evaluation["id"]})
        self.assertEqual(created.status_code, 201, created.content)
        session = created.json()
        self.interaction(session)
        closed = self.close(session, self.result(outcome="failed"))
        self.assertEqual(closed.status_code, 201, closed.content)
        run = closed.json()
        partial = self.send(path + "/actions/close", {
            "expected_revision": camp["revision"], "partial_review": True})
        self.assertEqual(partial.status_code, 200, partial.content)
        self.assertEqual(partial.json()["campaign"]["status"], "under_review")
        self.publisher()
        published = self.publish(partial.json()["campaign"], [run["id"]])
        self.assertEqual(published.status_code, 200, published.content)
        coverage = published.json()["publication"]["coverage"]
        self.assertEqual(coverage["pending"], 1)
        self.assertFalse(coverage["full_plan_complete"])
        self.assertEqual(len(published.json()["publication"]["runs"]), 1)
        reader = Client()
        reader.force_login(self.reader)
        self.assertEqual([x["id"] for x in reader.get(
            "/api/v1/runs?campaign_id=" + camp["id"]).json()["results"]],
                         [run["id"]])
