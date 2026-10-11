"""FUT-12: published evidence → personalized Task → precise Solution → feedback."""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client

from .catalog_services import revise_component
from .identity import ensure_roles
from .models import (BenchmarkRun, CatalogAuditEvent, CatalogItem,
                     DiscussionThread, UserEnvironmentRevision)
from .setup_guide_services import revise as revise_guide
from .test_publication import PublicationTests
from .test_runs import IndividualRunTests
from .workload_services import create_profile

BASE="/api/v1/engineer"


class EngineerJourneyTests(IndividualRunTests.__bases__[0]):
    setUpTestData=classmethod(IndividualRunTests.setUpTestData.__func__)
    setUp=IndividualRunTests.setUp
    send=IndividualRunTests.send
    campaign=IndividualRunTests.campaign
    session=IndividualRunTests.session
    interaction=IndividualRunTests.interaction
    result=IndividualRunTests.result
    close=IndividualRunTests.close
    ready_guide=PublicationTests.ready_guide
    completed=PublicationTests.completed
    review=PublicationTests.review
    publisher=PublicationTests.publisher
    publish=PublicationTests.publish

    def viewer(self):
        client=Client(enforce_csrf_checks=True)
        client.get("/api/v1/auth/csrf")
        client.force_login(self.reader)
        return client,client.cookies["csrftoken"].value

    def setup_access(self,available=("linux",)):
        for kind,item in self.catalog.items():
            props=dict(item.current_revision.properties)
            props["enterprise_accessibility"]="accessible"
            if kind=="harness":
                props["supported_os"]=list(available)
            revise_component(item=item,type_slug=kind,actor=self.editor,
                             expected_revision="r001",properties=props)

    def public_guide(self):
        self.ready_guide()
        guide,_=revise_guide(actor=self.editor,public_id=self.guide.public_id,
            expected_revision="r002",properties={"publication":"published"})
        self.assertEqual(guide.current_revision.number,3)

    def published(self,outcome="accepted", ready=True):
        if ready:self.public_guide()
        camp=self.campaign()
        run=self.completed(camp,outcome=outcome)
        reviewed=self.review(camp)
        self.publisher()
        p=self.publish(reviewed,[run["id"]])
        if ready:self.assertEqual(p.status_code,200,p.content)
        return camp,run,p

    def test_no_profile_no_private_runs_no_fake_ranking_or_access(self):
        camp=self.campaign()
        run=self.completed(camp)
        reader,_=self.viewer()
        listing=reader.get(BASE+"/workspace").json()
        self.assertEqual(listing["profile"]["status"],"not_configured")
        self.assertEqual(listing["tasks"],[])
        self.assertEqual(reader.get(BASE+"/solutions/"+run["solution_id"]).status_code,404)
        all_rows=reader.get(BASE+"/workspace?all_tasks=true").json()
        self.assertTrue(any(x["id"]==self.task.item.public_id for x in all_rows["tasks"]))
        self.assertTrue(all(not t["configurations"] for t in all_rows["tasks"]))
        self.assertEqual(reader.get(BASE+"/workspace?all_tasks=yes").status_code,400)
        self.assertEqual(reader.get(BASE+"/workspace?scope=private").status_code,400)
        self.assertEqual(reader.get(BASE+"/workspace?view=wrong").status_code,422)
        self.assertEqual(reader.get("/api/v1/runs/"+run["id"]).status_code,404)
        self.client.force_login(self.maint)
        self.assertEqual(self.client.get(BASE+"/workspace").status_code,403)
        self.assertEqual(Client().get(BASE+"/workspace").status_code,401)

    def test_person_scoped_relevance_os_alternative_precise_setup_and_feedback(self):
        self.setup_access(available=("linux",))
        self.public_guide()
        profile=create_profile(actor=self.editor,kind="person",data={
            "name":"Engineer private planning profile",
            "linked_user_id":self.reader.pk, "hourly_rate_eur":"250.00",
            "workloads":[{"task_id":self.task.item.public_id,
                          "annual_occurrences":"30","baseline_human_hours":"3"}]})
        UserEnvironmentRevision.objects.create(user=self.reader,number=1,
                                                available_os=["windows"])
        camp=self.campaign()
        run=self.completed(camp)
        reviewed=self.review(camp)
        self.publisher()
        published=self.publish(reviewed,[run["id"]])
        self.assertEqual(published.status_code,200,published.content)
        reader,token=self.viewer()
        payload=reader.get(BASE+"/workspace").json()
        self.assertEqual(payload["profile"]["status"],"configured")
        self.assertEqual(payload["profile"]["relevant_task_ids"],[self.task.item.public_id])
        self.assertNotIn("250",json.dumps(payload))
        self.assertNotIn("hourly_rate",json.dumps(payload))
        self.assertNotIn("linked_user_id",json.dumps(payload))
        task=next(t for t in payload["tasks"] if t["id"]==self.task.item.public_id)
        self.assertTrue(task["relevant"])
        self.assertEqual(len(task["configurations"]),1)
        config=task["configurations"][0]
        self.assertEqual(config["outcome_status"],"accepted_observed")
        self.assertEqual(config["suitability"],"other_os_observation")
        self.assertEqual(config["os"]["requires_os"],["linux"])
        self.assertEqual(config["enterprise_access"]["status"],"accessible")
        self.assertEqual(config["enterprise_access"]["personal_entitlement"],
                         "unknown_unverified")
        self.assertIsNone(config["scoring"]["score"])
        self.assertIsNone(config["scoring"]["rank"])
        tool=reader.get(BASE+"/workspace?view=tool").json()["tools"]
        self.assertEqual(tool[0]["solution_id"],run["solution_id"])
        self.assertEqual(tool[0]["tasks"][0]["task_id"],self.task.item.public_id)
        detail=reader.get(BASE+"/solutions/"+run["solution_id"]+"?task_id="+
                          self.task.item.public_id).json()
        self.assertEqual(detail["guide"]["status"],"applicable")
        self.assertEqual(detail["guide"]["current"]["source"]["revision"],"r003")
        self.assertEqual(detail["guide"]["historical"]["source"]["revision"],"r003")
        self.assertTrue(detail["guide"]["current"]["sections"])
        self.assertEqual(detail["historical_evidence"]["runs"][0]["id"],run["id"])
        self.assertEqual(detail["entitlement"],"unknown_unverified")
        post=reader.post(BASE+"/feedback",json.dumps({
            "kind":"request","context_id":run["solution_id"],
            "body":"Please contact me if an eligible account becomes available"}),
            content_type="application/json",HTTP_X_CSRFTOKEN=token)
        self.assertEqual(post.status_code,201,post.content)
        self.assertFalse(post.json()["entitlement_granted"])
        self.assertEqual(post.json()["status"],"discussion_recorded_not_a_ticket")
        self.assertEqual(DiscussionThread.objects.count(),1)
        messages=reader.get("/api/v1/discussions/"+post.json()["id"])
        self.assertEqual(messages.status_code,200,messages.content)
        self.assertIn("no entitlement",json.dumps(messages.json()).lower())
        update=reader.get(BASE+"/solutions/"+run["solution_id"]).json()
        self.assertEqual([x["id"] for x in update["published_updates"]],[post.json()["id"]])
        from .discussion_services import create_thread
        reviewer=get_user_model().objects.get(username="publisher-"+str(self.editor.pk)[:8])
        private,_=create_thread(reviewer,{
            "title":"Private workgroup discussion",
            "context_id":run["solution_id"], "body":"Workgroup-only investigation",
            "properties":{"scope":"internal","kind":"discussion"}})
        self.assertNotIn(private.item.public_id,json.dumps(
            reader.get(BASE+"/solutions/"+run["solution_id"]).json()))

    def test_failed_only_and_withdrawn_never_positive_or_discoverable(self):
        self.setup_access(available=("windows",))
        camp,failed,_=self.published("failed")
        reader,_=self.viewer()
        candidates=reader.get(BASE+"/workspace?all_tasks=true").json()
        task=next(x for x in candidates["tasks"] if x["id"]==self.task.item.public_id)
        self.assertEqual(task["configurations"][0]["outcome_status"],"failed_only")
        self.assertEqual(task["configurations"][0]["suitability"],"unverified_or_not_suitable")
        self.client.force_login(self.editor)
        # Another completed Run remains private, even when the Campaign was reopened.
        self.assertEqual(reader.get(BASE+"/solutions/"+failed["solution_id"]).status_code,200)
        self.publisher()
        revoked=self.send("/api/v1/runs/"+failed["id"]+"/actions/withdrawn",{
            "expected_revision":"r001",
            "reason":"Measurement source invalidated after independent investigation"})
        self.assertEqual(revoked.status_code,201,revoked.content)
        self.assertEqual(reader.get(BASE+"/solutions/"+failed["solution_id"]).status_code,404)
        self.assertEqual(reader.get(BASE+"/workspace?all_tasks=true").json()["tasks"][-1]["configurations"],[])
        self.assertEqual(reader.get("/api/v1/runs/"+failed["id"]).status_code,404)
        self.assertEqual(BenchmarkRun.objects.get(public_id=failed["id"]).outcome,"failed")

    def test_csrf_feedback_context_and_permanent_demo_server_separation(self):
        self.setup_access(available=("windows",))
        _,run,_=self.published()
        reader,token=self.viewer()
        body={"kind":"feedback","context_id":run["solution_id"],
              "body":"I used this configuration and encountered reproducible behavior"}
        self.assertEqual(reader.post(BASE+"/feedback",json.dumps(body),
             content_type="application/json").status_code,403)
        invalid=reader.post(BASE+"/feedback",json.dumps({**body,"context_id":"sol-not-found"}),
             content_type="application/json",HTTP_X_CSRFTOKEN=token)
        self.assertEqual(invalid.status_code,400)
        self.assertEqual(DiscussionThread.objects.count(),0)
        created=reader.post(BASE+"/feedback",json.dumps(body),
             content_type="application/json",HTTP_X_CSRFTOKEN=token)
        self.assertEqual(created.status_code,201,created.content)
        self.assertEqual(created.json()["context_id"],run["solution_id"])
        self.assertEqual(CatalogItem.objects.filter(type_slug="discussion_thread").count(),1)
        self.assertTrue(CatalogAuditEvent.objects.filter(
            item__type_slug="discussion_thread",action="created").exists())
        self.assertEqual(reader.get(BASE+"/workspace?all_tasks=true").status_code,200)
