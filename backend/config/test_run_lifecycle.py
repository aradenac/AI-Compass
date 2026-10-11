"""FUT-11: real published original, amendment, withdrawn, privacy and score tests."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client

from .test_runs import IndividualRunTests
from .test_publication import PublicationTests
from .models import BenchmarkRun, RunAmendment, CatalogAuditEvent
from .publication_services import effective_ids


class RunLifecycleTests(IndividualRunTests.__bases__[0]):
    setUpTestData = classmethod(IndividualRunTests.setUpTestData.__func__)
    setUp = IndividualRunTests.setUp
    send = IndividualRunTests.send
    campaign = IndividualRunTests.campaign
    session = IndividualRunTests.session
    interaction = IndividualRunTests.interaction
    result = IndividualRunTests.result
    close = IndividualRunTests.close
    ready_guide = PublicationTests.ready_guide
    completed = PublicationTests.completed
    review = PublicationTests.review
    publisher = PublicationTests.publisher
    publish = PublicationTests.publish

    def fixture(self, two=False):
        self.ready_guide()
        camp=self.campaign()
        first=self.completed(camp, outcome="failed")
        other=self.completed(camp) if two else None
        closed=self.review(camp)
        self.publisher()
        included=[first["id"]]+([other["id"]] if other else [])
        response=self.publish(closed,included)
        self.assertEqual(response.status_code,200,response.content)
        return camp,first,other,response.json()

    def changed(self, run, action, revision, **fields):
        return self.send("/api/v1/runs/"+run["id"]+"/actions/"+action,
                         {"expected_revision":revision,
                          "reason":"Incorrect declared experimental value",
                          **fields})

    def test_correct_declared_metrics_outcome_and_stale_revision(self):
        camp, run, _, _=self.fixture()
        before=BenchmarkRun.objects.get(public_id=run["id"])
        raw=dict(before.metrics)
        reader=Client();reader.force_login(self.reader)
        original=reader.get("/api/v1/runs/"+run["id"]).json()
        self.assertEqual(original["revision"],"r001")
        self.assertEqual(original["outcome"],"failed")
        denied=self.send("/api/v1/runs/"+run["id"]+"/actions/corrected",{
            "expected_revision":"r001","reason":"Incorrect declared original score",
            "metrics_patch":{"quality_score":92}})
        # Reviewer in fixture is allowed; correction must succeed.
        self.assertEqual(denied.status_code,201,denied.content)
        self.assertEqual(denied.json()["current"]["revision"],"r002")
        self.assertEqual(self.changed(run,"corrected","r001",
                         metrics_patch={"quality_score":88}).status_code,409)
        self.assertEqual(self.changed(run,"corrected","r002",
                         metrics_patch={"cost_eur":-1}).status_code,400)
        self.assertEqual(self.changed(run,"corrected","r002",
                         metrics_patch={"quality_score":92}).status_code,400)
        next_change=self.changed(run,"corrected","r002",
                                 outcome="accepted",
                                 metrics_patch={"tokens_count":123,"tokens_multiplier":10})
        self.assertEqual(next_change.status_code,201,next_change.content)
        after=reader.get("/api/v1/runs/"+run["id"]).json()
        self.assertEqual(after["metrics"]["quality_score"],92)
        self.assertEqual(after["metrics"]["tokens_total"],1230)
        self.assertEqual(after["metrics"]["outcome"],"accepted")
        self.assertEqual(after["outcome"],"accepted")
        self.assertEqual(after["revision"],"r003")
        current=reader.get("/api/v1/results/explorer").json()["results"]
        self.assertEqual(current[0]["metrics"]["quality_score"],92)
        self.assertEqual(current[0]["outcome"],"accepted")
        self.assertEqual(current[0]["effective_revision"],"r003")
        self.assertEqual(BenchmarkRun.objects.get(pk=before.pk).metrics,raw)
        hist=self.client.get("/api/v1/runs/"+run["id"]+"/revisions").json()
        self.assertEqual([x["revision"] for x in hist["revisions"]],
                         ["r001","r002","r003"])
        self.assertEqual(hist["revisions"][0]["metrics"],raw)
        self.assertEqual(RunAmendment.objects.filter(individual_run=before).count(),2)
        self.assertEqual(CatalogAuditEvent.objects.filter(action="run_corrected").count(),2)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                RunAmendment.objects.filter(individual_run=before).update(reason="tampered")

    def test_withdrawal_immediate_and_unrelated_run_remains(self):
        camp, one, two, _=self.fixture(two=True)
        reader=Client();reader.force_login(self.reader)
        self.assertEqual(len(reader.get("/api/v1/runs").json()["results"]),2)
        revoked=self.changed(one,"withdrawn","r001")
        self.assertEqual(revoked.status_code,201,revoked.content)
        self.assertEqual(effective_ids(camp["id"]),{two["id"]})
        self.assertEqual(reader.get("/api/v1/runs/"+one["id"]).status_code,404)
        self.assertEqual(reader.get("/api/v1/runs/"+two["id"]).status_code,200)
        self.assertEqual([x["id"] for x in reader.get("/api/v1/runs").json()["results"]],
                         [two["id"]])
        self.assertEqual([x["id"] for x in reader.get(
            "/api/v1/results/explorer").json()["results"]],[two["id"]])
        manifest=reader.get("/api/v1/campaigns/"+camp["id"]+"/publication").json()
        self.assertEqual(manifest["effective_run_ids"],[two["id"]])
        self.assertEqual(manifest["publication"]["as_published_run_count"],2)
        self.assertEqual(manifest["publication"]["active_run_count"],1)
        self.assertEqual(reader.get("/api/v1/runs/"+one["id"]+"/revisions").status_code,404)
        self.assertEqual(self.changed(one,"corrected","r002",
                         metrics_patch={"quality_score":5}).status_code,400)
        self.assertEqual(self.changed(one,"withdrawn","r002").status_code,400)

    def test_permission_input_and_concurrency_boundaries(self):
        camp, run, _, _=self.fixture()
        self.client.force_login(self.reader)
        self.assertEqual(self.changed(run,"withdrawn","r001").status_code,403)
        self.client.force_login(self.editor)
        self.assertEqual(self.changed(run,"corrected","r001",
                         metrics_patch={"quality_score":11}).status_code,403)
        self.publisher()
        self.assertEqual(self.changed(run,"corrected","r001",
                         metrics_patch={"unknown_metric":19}).status_code,400)
        self.assertEqual(self.changed(run,"corrected","r001",
                         metrics_patch={"quality_score":float("nan")}).status_code,400)
        self.assertEqual(RunAmendment.objects.count(),0)
        self.assertEqual(self.changed(run,"withdrawn","r999").status_code,409)
        self.assertEqual(RunAmendment.objects.count(),0)
        self.assertEqual(self.changed(run,"withdrawn","r001").status_code,201)

    def test_unpublished_run_must_not_be_amended(self):
        self.ready_guide()
        camp=self.campaign()
        run=self.completed(camp)
        self.publisher()
        self.assertEqual(self.changed(run,"withdrawn","r001").status_code,400)
        self.assertEqual(RunAmendment.objects.count(),0)
