"""PLAT-22: real individual run evidence, public/draft isolation and historical decision safety."""
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction,DatabaseError
from django.test import TestCase,Client,override_settings

from .identity import ensure_roles
from .test_evaluations import ResultsAndEvaluationTests
from .models import (BenchmarkRun,CompositeBenchmarkRun,CatalogItem,CatalogRevision,
                     RecommendationSnapshot,RecommendationRunPin,CatalogAuditEvent)

ROOT="/api/v1/recommendations"


class RecommendationTests(TestCase):
    """Reuse tested real controlled Run constructors; don't fabricate measured evidence."""
    @classmethod
    def setUpTestData(cls):
        ResultsAndEvaluationTests.setUpTestData.__func__(cls)
        cls.reviewer=get_user_model().objects.create_user(
            "recommendation-reviewer",password="test")
        cls.reviewer.groups.add(Group.objects.get(name="reviewer"))

    call=ResultsAndEvaluationTests.call
    as_user=ResultsAndEvaluationTests.as_user
    measured=ResultsAndEvaluationTests.measured
    evaluation=ResultsAndEvaluationTests.evaluation

    def setUp(self):
        ResultsAndEvaluationTests.setUp(self)
        folder=tempfile.TemporaryDirectory(prefix="recommendation-evidence-")
        self.addCleanup(folder.cleanup)
        settings=override_settings(EVIDENCE_STORE_ROOT=Path(folder.name))
        settings.enable();self.addCleanup(settings.disable)

    def recommend(self,run,with_evaluation=False):
        payload={"name":"Driver coding recommendation","task_id":self.task.item.public_id,
            "solution_id":run["solution_id"],"run_ids":[run["id"]],
            "properties":{"decision":"recommended",
                "rationale":"Controlled Twister tests passed for this precise setup",
                "limitations":"Single evaluation scenario; flat-rate costs are unknown",
                "extensions":{"unknown_in_future":None}}}
        if with_evaluation:
            evaluated=self.evaluation([run["id"]])
            payload.update(evaluation_id=evaluated["id"],evaluation_revision="r001")
        res=self.call(ROOT,payload)
        self.assertEqual(res.status_code,201,res.content)
        return res.json()

    def submit(self,item):
        response=self.call(ROOT+"/"+item["id"]+"/actions/submit",
                    {"expected_revision":item["revision"]})
        self.assertEqual(response.status_code,200,response.content)
        return response.json()["record"]

    def publish(self,item,note="Reviewed original Twister evidence, one reviewer decision"):
        user,csrf=self.as_user(self.reviewer)
        return self.call(ROOT+"/"+item["id"]+"/actions/publish",{
            "expected_revision":item["revision"],"review_note":note
        },browser=user,token=csrf)

    def withdraw(self,item):
        user,csrf=self.as_user(self.reviewer)
        return self.call(ROOT+"/"+item["id"]+"/actions/unpublish",{
            "expected_revision":item["revision"],
            "review_note":"New failed Test Case invalidates prior qualification"
        },browser=user,token=csrf)

    def failed_run(self):
        original=self.call
        def injected(path,data,method="POST",browser=None,token=None):
            if path.endswith("/close"):
                data={**data,"outcome":"failed","quality_score":25,
                      "quality_evaluation":"Regression test failed"}
            return original(path,data,method=method,browser=browser,token=token)
        self.call=injected
        try:return self.measured()
        finally:self.call=original

    def test_empty_server_and_registered_new_evidence_type(self):
        self.assertEqual(self.client.get(ROOT).json(),{"results":[]})
        self.assertEqual(CatalogItem.objects.filter(type_slug="recommendation").count(),0)
        self.assertEqual(RecommendationSnapshot.objects.count(),0)

    def test_review_publish_edit_new_failure_and_explicit_withdraw(self):
        first=self.measured()
        before=dict(BenchmarkRun.objects.get(public_id=first["id"]).metrics)
        recommendation=self.recommend(first,with_evaluation=True)
        self.assertTrue(recommendation["id"].startswith("rec-"))
        self.assertEqual(recommendation["state"],"draft")
        self.assertEqual(recommendation["evaluation_revision"],"r001")
        self.assertEqual(recommendation["run_refs"][0]["metrics"],before)
        reader,_=self.as_user(self.reader)
        self.assertEqual(reader.get(ROOT).json()["results"],[])
        self.assertEqual(reader.get(ROOT+"/"+recommendation["id"]).status_code,404)
        self.assertEqual(reader.get("/api/v1/catalog/items/"+recommendation["id"]).status_code,404)
        self.assertEqual(reader.get("/api/v1/catalog/items/"+recommendation["id"]+
                                    "/evidence").status_code,404)
        self.assertEqual(self.publish(recommendation).status_code,400)
        submitted=self.submit(recommendation)
        self.assertEqual(submitted["state"],"in_review")
        reviewer_output=self.publish(submitted)
        self.assertEqual(reviewer_output.status_code,200,reviewer_output.content)
        published=reviewer_output.json()["record"]
        self.assertEqual(published["state"],"published")
        self.assertEqual(published["revision"],"r003")
        self.assertEqual(published["reviewed_by"],self.reviewer.username)
        self.assertIsNotNone(published["reviewed_at"])
        self.assertEqual(len(reader.get(ROOT).json()["results"]),1)
        public_published=reader.get(ROOT+"/"+recommendation["id"]).json()
        self.assertFalse(public_published["eligible_for_current_suitability"])
        self.assertEqual(public_published["run_refs"],[{"kind":"individual","status":"unavailable"}])
        self.assertEqual(reader.get(ROOT+"/"+recommendation["id"]+"/revisions/1").status_code,404)
        self.assertEqual(reader.get(ROOT+"/"+recommendation["id"]+"/revisions").json()
                         ["revisions"],[public_published])
        updated=self.call(ROOT+"/"+recommendation["id"],{
            "expected_revision":"r003",
            "properties":{"rationale":"Will reassess after a broader set of Test Cases"}},
            method="PATCH")
        self.assertEqual(updated.status_code,200,updated.content)
        draft=updated.json()["record"]
        self.assertEqual(draft["revision"],"r004")
        self.assertEqual(draft["state"],"draft")
        self.assertIsNone(draft["reviewed_by"])
        self.assertEqual(draft["evaluation_revision_id"],published["evaluation_revision_id"])
        self.assertEqual(draft["run_refs"],published["run_refs"])
        # A draft under review must not shadow the last public decision.
        self.assertEqual(reader.get(ROOT+"/"+recommendation["id"]).json(),public_published)
        failed=self.failed_run()
        self.assertEqual(failed["outcome"],"failed")
        self.assertEqual(failed["solution_id"],first["solution_id"])
        public_alert=reader.get(ROOT+"/"+recommendation["id"]).json()
        self.assertEqual(public_alert["revision"],"r003")
        self.assertTrue(public_alert["review_needed"])
        self.assertEqual(public_alert["contradictory_run_ids"],[])
        self.assertEqual(public_alert["new_run_ids"],[])
        self.assertFalse(public_alert["eligible_for_current_suitability"])
        self.assertEqual(reader.get(ROOT).json()["results"][0]["review_needed"],True)
        self.assertEqual(self.client.get(ROOT+"/"+recommendation["id"]+
                                         "/revisions/3").json()["properties"],
                         published["properties"])
        self.assertEqual(BenchmarkRun.objects.get(public_id=first["id"]).metrics,before)
        self.assertEqual(BenchmarkRun.objects.count(),2)
        self.assertEqual(CompositeBenchmarkRun.objects.count(),0)
        unpublished=self.withdraw(draft)
        self.assertEqual(unpublished.status_code,200,unpublished.content)
        self.assertEqual(unpublished.json()["record"]["state"],"unpublished")
        self.assertEqual(reader.get(ROOT).json(),{"results":[]})
        self.assertEqual(reader.get(ROOT+"/"+recommendation["id"]).status_code,404)
        self.assertEqual(reader.get(ROOT+"/"+recommendation["id"]+"/revisions/3").status_code,404)
        self.assertEqual(self.client.get(ROOT+"/"+recommendation["id"]+
                                         "/revisions/3").json()["properties"],
                         published["properties"])
        self.assertEqual(RecommendationRunPin.objects.count(),5)
        self.assertTrue(CatalogAuditEvent.objects.filter(
            item__public_id=recommendation["id"],action="published").exists())
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                RecommendationRunPin.objects.filter(
                    snapshot__revision_id=published["revision_id"]).delete()

    def test_refuse_missing_composite_cross_solution_and_unapproved_revision(self):
        run=self.measured()
        rec=self.recommend(run)
        other=self.measured(composite=True)
        self.assertEqual(self.call(ROOT,{
            "name":"Composite is not an individual recommendation",
            "task_id":self.task.item.public_id,
            "solution_id":run["solution_id"],"run_ids":[other["id"]],
            "properties":{"rationale":"Invalid composite"}}).status_code,400)
        # A mixed individual+composite Evaluation is never an acceptable
        # basis for assigning global Framework quality to one AI Solution.
        mixed=self.evaluation([run["id"],other["id"]])
        denied=self.call(ROOT,{
            "name":"Cannot attribute composite score to an individual",
            "task_id":self.task.item.public_id,
            "solution_id":run["solution_id"],"run_ids":[run["id"]],
            "evaluation_id":mixed["id"],"evaluation_revision":"r001",
            "properties":{"rationale":"Mixed workflow evidence"}})
        self.assertEqual(denied.status_code,400,denied.content)
        self.assertIn("composite",denied.json()["detail"])
        self.assertEqual(self.call(ROOT,{
            "name":"Broken Run",
            "task_id":self.task.item.public_id,
            "solution_id":run["solution_id"],"run_ids":["run-no-such-id"],
            "properties":{"rationale":"Unknown original"}}).status_code,400)
        self.assertEqual(self.call(ROOT+"/"+rec["id"],{
            "expected_revision":"r001","solution_id":"sol-does-not-exist"},
            method="PATCH").status_code,400)
        self.assertEqual(self.call(ROOT+"/"+rec["id"],{
            "expected_revision":"r900","properties":{"rationale":"stale"}},
            method="PATCH").status_code,409)
        self.assertEqual(self.call(ROOT+"/"+rec["id"],{
            "expected_revision":"r001","properties":{"state":"published"}},
            method="PATCH").status_code,400)
        self.assertEqual(self.call(ROOT+"/"+rec["id"],{
            "expected_revision":"r001","evaluation_id":"evl-missing"},
            method="PATCH").status_code,400)
        # Cannot publish without submission and attributable justification.
        self.assertEqual(self.publish(rec).status_code,400)
        reviewed=self.submit(rec)
        self.assertEqual(self.publish(reviewed,note=" ").status_code,400)
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=rec["id"]).count(),2)
        self.assertEqual(RecommendationSnapshot.objects.filter(
            revision__item__public_id=rec["id"]).count(),2)

    def test_permission_guards_and_original_recommendation_attachments(self):
        original=self.measured()
        rec=self.recommend(original)
        reader,token=self.as_user(self.reader)
        maint,_=self.as_user(self.maint)
        self.assertEqual(maint.get(ROOT).status_code,403)
        self.assertEqual(reader.get(ROOT+"/"+rec["id"]+"/revisions").status_code,404)
        self.assertEqual(self.call(ROOT,{
            "name":"Forbidden","task_id":self.task.item.public_id,
            "solution_id":original["solution_id"],"run_ids":[original["id"]],
            "properties":{"rationale":"denied"}},
            browser=reader,token=token).status_code,403)
        no_csrf=Client(enforce_csrf_checks=True);no_csrf.force_login(self.editor)
        self.assertEqual(no_csrf.post(ROOT,json.dumps({
            "name":"Bad","task_id":self.task.item.public_id,
            "solution_id":original["solution_id"],"run_ids":[original["id"]],
            "properties":{"rationale":"bad"}}),content_type="application/json").status_code,403)
        draftbytes=b"unreleased recommendation decision details"
        upload=self.client.post("/api/v1/catalog/items/"+rec["id"]+"/evidence/upload",{
            "revision":"r001","file":SimpleUploadedFile("draft.txt",draftbytes,
                content_type="text/plain"),"source":"workgroup:decision",
            "provenance":json.dumps({"unknown":None}),
        },HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(upload.status_code,201,upload.content)
        eid=upload.json()["id"]
        self.assertEqual(reader.get("/api/v1/evidence/"+eid).status_code,404)
        self.assertEqual(reader.get("/api/v1/evidence/"+eid+"/download").status_code,404)
        submitted=self.submit(rec)
        published=self.publish(submitted).json()["record"]
        # Original draft attachment remains confidential even after publication.
        self.assertEqual(reader.get("/api/v1/evidence/"+eid).status_code,404)
        pubbytes=b"approved recommendation rationale"
        attachment=self.client.post("/api/v1/catalog/items/"+rec["id"]+"/evidence/upload",{
            "revision":published["revision"],
            "file":SimpleUploadedFile("published.txt",pubbytes,content_type="text/plain"),
            "source":"workgroup:published",
        },HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(attachment.status_code,201,attachment.content)
        published_id=attachment.json()["id"]
        visible=reader.get("/api/v1/catalog/items/"+rec["id"]+"/evidence")
        self.assertEqual(visible.status_code,200,visible.content)
        self.assertEqual([x["id"] for x in visible.json()["results"]],[published_id])
        self.assertEqual(b"".join(reader.get("/api/v1/evidence/"+published_id+
                    "/download").streaming_content),pubbytes)
        withdrawn=self.withdraw(published)
        self.assertEqual(withdrawn.status_code,200,withdrawn.content)
        self.assertEqual(reader.get("/api/v1/evidence/"+published_id).status_code,404)


    def test_new_failed_run_blocks_stale_republication_until_explicit_reassessment(self):
        first=self.measured()
        original=self.recommend(first)
        published=self.publish(self.submit(original)).json()["record"]
        failed=self.failed_run()
        changed=self.call(ROOT+"/"+original["id"],{
            "expected_revision":"r003",
            "properties":{"rationale":"Preparing a new review of recently observed failures"}},
            method="PATCH")
        self.assertEqual(changed.status_code,200,changed.content)
        draft=changed.json()["record"]
        self.assertTrue(draft["review_needed"])
        self.assertEqual(draft["contradictory_run_ids"],[failed["id"]])
        pending=self.submit(draft)
        refusal=self.publish(pending)
        self.assertEqual(refusal.status_code,400,refusal.content)
        self.assertIn("New measured Runs",refusal.json()["detail"])
        reader,_=self.as_user(self.reader)
        self.assertEqual(reader.get(ROOT+"/"+original["id"]).json()["revision"],"r003")
        self.assertEqual(CatalogRevision.objects.filter(
            item__public_id=original["id"]).count(),5)
        # A human explicitly links both original and contrary evidence and
        # revises the conclusion. Earlier publication is never overwritten.
        repaired=self.call(ROOT+"/"+original["id"],{
            "expected_revision":"r005",
            "run_ids":[first["id"],failed["id"]],
            "properties":{"decision":"conditional",
                "rationale":"Original success is contradicted by a later controlled failure",
                "limitations":"Requires targeted regression and reproduction"}},
            method="PATCH")
        self.assertEqual(repaired.status_code,200,repaired.content)
        updated=repaired.json()["record"]
        self.assertEqual(updated["state"],"draft")
        self.assertEqual(len(updated["run_refs"]),2)
        republished=self.publish(self.submit(updated))
        self.assertEqual(republished.status_code,200,republished.content)
        final=republished.json()["record"]
        self.assertEqual(final["revision"],"r008")
        self.assertEqual(final["properties"]["decision"],"conditional")
        self.assertTrue(final["review_needed"])
        self.assertFalse(final["eligible_for_current_suitability"])
        self.assertEqual(reader.get(ROOT+"/"+original["id"]).json()["revision"],"r008")
        self.assertEqual(self.client.get(ROOT+"/"+original["id"]+
                                         "/revisions/3").json()["properties"],
                         published["properties"])
        self.assertEqual(BenchmarkRun.objects.get(public_id=first["id"]).metrics,
                         first["metrics"])
