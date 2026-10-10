"""PLAT-16: composite-only measured evidence, exact participant revisions, independent solutions."""
import hashlib
import json
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction, connection
from django.test import Client, TestCase, override_settings

from .catalog_services import create_component, revise_component
from .identity import ensure_roles
from .models import (BenchmarkRun, BenchmarkSession, CatalogItem, CompositeBenchmarkRun,
                     CompositeRunParticipant, CompositeRunEvidence, MeasuredSolution)
from .setup_guide_services import create as create_guide, revise as revise_guide
from .task_services import create_task
from .test_case_services import create as create_case, revise as revise_case


class CompositeBenchmarkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U=get_user_model()
        cls.editor=U.objects.create_user("composite-editor",password="test")
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.other=U.objects.create_user("composite-other",password="test")
        cls.other.groups.add(Group.objects.get(name="contributor"))
        cls.reader=U.objects.create_user("composite-reader",password="test")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=U.objects.create_user("composite-maint",password="test")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.editor,name="Driver SPI composite")
        cls.case=create_case(actor=cls.editor,task_id=cls.task.item.public_id,
                             name="TC composite",properties={
                                 "objective":"Build driver","dod":"Twister regression passes"})
        cls.guide=create_guide(actor=cls.editor,name="Composite setup",
                               properties={"text":"Install toolchain and dependencies"})
        cls.framework=create_component(type_slug="framework",actor=cls.editor,
             name="Orchestrated framework",properties={"process":"plan, implement, review"})
        cls.catalog={kind:[create_component(type_slug=kind,actor=cls.editor,
             name=kind+" "+str(i),properties={"extra":None}) for i in range(2)]
             for kind in ("model","provider","harness")}

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="composite-run-bytes-")
        self.addCleanup(temp.cleanup)
        guard=override_settings(EVIDENCE_STORE_ROOT=Path(temp.name))
        guard.enable();self.addCleanup(guard.disable)
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.csrf=self.client.cookies["csrftoken"].value
        self.client.force_login(self.editor)

    def send(self,path,payload,method="POST",client=None,csrf=None):
        browser=client or self.client
        fn=browser.patch if method=="PATCH" else browser.post
        return fn(path,json.dumps(payload),content_type="application/json",
                  HTTP_X_CSRFTOKEN=self.csrf if csrf is None else csrf)

    def campaign(self):
        participants=[]
        for i,role in enumerate(("Planner","Implementer")):
            participants.append({
                "label":role+" member","role":role,
                "configuration_version":"cfg"+str(i+1),
                "settings":{"temperature":i/10,"future":{"nullable":None}},
                "properties":{"tools":["shell","git"],"enabled":True},
                "component_ids":{kind:self.catalog[kind][i].public_id
                                 for kind in ("model","provider","harness")},
            })
        result=self.send("/api/v1/campaigns",{
            "name":"Controlled composite campaign","objective":"Implement and review",
            "mode":"task_centred","task_id":self.task.item.public_id,
            "test_case_ids":[self.case.item.public_id],
            "guide_id":self.guide.public_id,
            "framework_id":self.framework.public_id,
            "participants":participants,
            "configuration":{"orchestration":{"escalate":True}},
        })
        self.assertEqual(result.status_code,201,result.content)
        original=result.json()
        result=self.send("/api/v1/campaigns/"+original["id"]+"/actions/start",
                         {"expected_revision":"r001"})
        self.assertEqual(result.status_code,200,result.content)
        return result.json()["campaign"]

    def session(self,campaign,participants=None):
        identifiers=[row["id"] for row in campaign["participants"]]
        result=self.send("/api/v1/campaigns/"+campaign["id"]+"/sessions",{
            "test_case_id":self.case.item.public_id,
            "selected_participant_ids":participants if participants is not None else identifiers,
        })
        self.assertEqual(result.status_code,201,result.content)
        return result.json()

    def interact(self,ses,revision="r001",participant_id=None,agent_minutes=None):
        result=self.send("/api/v1/sessions/"+ses["id"]+"/interactions",{
            "expected_revision":revision,"type":"human_prompt",
            "content":"Implement SPI driver and check errors",
            "human_minutes":2,"agent_minutes":agent_minutes,
            "participant_id":participant_id,
            "extensions":{"custom":{"unknown":None}},
            "occurred_at":"2026-10-10T10:00:00+02:00",
        })
        self.assertEqual(result.status_code,200,result.content)
        return result.json()

    def results(self,rev="r002",outcome="accepted",**extra):
        return {"expected_revision":rev,"outcome":outcome,
                "quality_score":77,"quality_evaluation":"Workflow passed required checks",
                "information_utility_score":70,
                "information_utility_evaluation":"Useful complete output",
                "tokens_count":None,"tokens_multiplier":1,
                "cost_mode":"flat_rate","cost_eur":None,
                "human_review_minutes":5,"human_correction_minutes":0,
                "produced_outputs":"commit abc123; native_sim Twister report",
                "extensions":{"custom":{"nullable":None}},
                **extra}

    def test_composite_close_preserves_roles_global_metrics_evidence_and_history(self):
        camp=self.campaign()
        ses=self.session(camp)
        self.assertEqual(len(ses["selected_participant_ids"]),2)
        self.assertIsNone(ses["individual_setup"])
        original_bytes=b"report: Twister native_sim pass; driver source unmodified\n"
        link=self.client.post("/api/v1/catalog/items/"+camp["id"]+"/evidence/upload",{
            "revision":"r002","file":SimpleUploadedFile(
                "twister.txt",original_bytes,content_type="text/plain"),
            "source":"test:controlled","provenance":json.dumps({"build":{"unknown":None}}),
        },HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(link.status_code,201,link.content)
        link_id=link.json()["id"]
        first=self.interact(ses,participant_id=camp["participants"][0]["id"],
                            agent_minutes=None)
        next_step=self.send("/api/v1/sessions/"+ses["id"]+"/interactions",{
            "expected_revision":"r002","type":"agent_response",
            "content":"Implementation completed and review delegated",
            "participant_id":camp["participants"][1]["id"],
            "human_minutes":0,"agent_minutes":12,
            "evidence_link_ids":[link_id],
            "extensions":{"tool_output":{"new_schema_field":None}},
        })
        self.assertEqual(next_step.status_code,200,next_step.content)
        closed=self.send("/api/v1/sessions/"+ses["id"]+"/close",
                         self.results(rev="r003",evidence_link_ids=[link_id]))
        self.assertEqual(closed.status_code,201,closed.content)
        run=closed.json()
        self.assertEqual(run["kind"],"composite")
        self.assertEqual(run["scope"],"framework_workflow")
        self.assertIsNone(run["solution_id"])
        self.assertIsNone(run["solution_revision_id"])
        self.assertEqual(run["outcome"],"accepted")
        self.assertEqual(run["framework_id"],camp["framework_id"])
        self.assertEqual(run["framework_revision_id"],camp["framework_revision_id"])
        self.assertEqual(run["provenance"]["method_version"],1)
        self.assertEqual(run["provenance"]["guide_revision_id"],camp["guide_revision_id"])
        self.assertEqual(run["provenance"]["test_case_revision_id"],
                         camp["test_case_revisions"][0]["revision_id"])
        self.assertEqual(run["provenance"]["campaign_configuration"],
                         {"orchestration":{"escalate":True}})
        self.assertEqual([row["role"] for row in run["participants"]],
                         ["Planner","Implementer"])
        self.assertEqual([row["participant_id"] for row in run["participants"]],
                         [row["id"] for row in camp["participants"]])
        self.assertEqual(run["participants"][0]["settings"]["future"],
                         {"nullable":None})
        self.assertEqual(run["participants"][1]["component_revision_ids"]["model"],
                         camp["participants"][1]["component_revisions"]["model"])
        self.assertEqual([r["actor_label"] for r in run["interaction_actor_labels"]],
                         ["Planner member · Planner","Implementer member · Implementer"])
        self.assertEqual(run["raw_session_state"]["interactions"][1]["extensions"],
                         {"tool_output":{"new_schema_field":None}})
        self.assertEqual(run["metrics"]["interaction_human_minutes"],2)
        self.assertIsNone(run["metrics"]["interaction_agent_minutes"])
        self.assertIsNone(run["metrics"]["human_total_minutes"])
        self.assertIsNone(run["metrics"]["cost_eur"])
        self.assertEqual(run["metrics"]["cost_mode"],"flat_rate")
        self.assertEqual(run["metrics"]["human_correction_minutes"],0)
        self.assertEqual(run["evidence"][0]["id"],link_id)
        self.assertEqual(run["evidence"][0]["sha256"],hashlib.sha256(original_bytes).hexdigest())
        self.assertEqual(BenchmarkRun.objects.count(),0)
        self.assertEqual(MeasuredSolution.objects.count(),0)
        self.assertEqual(CatalogItem.objects.filter(type_slug="ai_solution").count(),0)
        self.assertEqual(CompositeRunParticipant.objects.filter(run__public_id=run["id"]).count(),2)
        self.assertEqual(CompositeRunEvidence.objects.filter(run__public_id=run["id"]).count(),1)

        reader=Client();reader.force_login(self.reader)
        self.assertEqual(reader.get("/api/v1/runs/"+run["id"]).json(),run)
        all_runs=reader.get("/api/v1/runs?campaign_id="+camp["id"]).json()["results"]
        self.assertEqual([r["kind"] for r in all_runs],["composite"])
        self.assertEqual(len(reader.get("/api/v1/runs?kind=composite").json()["results"]),1)
        self.assertEqual(reader.get("/api/v1/runs?kind=individual").json()["results"],[])
        self.assertEqual(reader.get("/api/v1/solutions").json()["results"],[])
        self.assertEqual(b"".join(reader.get(run["evidence"][0]["download"]).streaming_content),
                         original_bytes)
        self.assertEqual(self.send("/api/v1/sessions/"+ses["id"]+"/close",
                                  self.results(rev="r003")).status_code,409)
        self.assertEqual(self.send("/api/v1/sessions/"+ses["id"]+"/interactions",
                                  {"expected_revision":"r004","content":"try to mutate"}).status_code,409)
        self.assertEqual(reader.get("/api/v1/sessions/"+ses["id"]+
                                   "/checkpoints/2").json()["state"]["interactions"][0]["content"],
                         "Implement SPI driver and check errors")

        revise_case(actor=self.editor,public_id=self.case.item.public_id,
                    expected_revision="r001",properties={"dod":"Stricter DoD"})
        revise_guide(actor=self.editor,public_id=self.guide.public_id,
                     expected_revision="r001",properties={"text":"Updated setup"})
        revise_component(item=self.catalog["model"][0],type_slug="model",actor=self.editor,
                         expected_revision="r001",name="New model release")
        self.assertEqual(reader.get("/api/v1/runs/"+run["id"]).json(),run)

    def test_failed_composite_is_not_measured_solution_and_individual_unchanged(self):
        camp=self.campaign()
        solo=self.session(camp,participants=[camp["participants"][0]["id"]])
        self.interact(solo,participant_id=camp["participants"][0]["id"],agent_minutes=4)
        individual=self.send("/api/v1/sessions/"+solo["id"]+"/close",
                             self.results(cost_mode="amount",cost_eur=2.5)).json()
        self.assertEqual(individual["kind"],"individual")
        self.assertEqual(MeasuredSolution.objects.count(),1)
        sid=individual["solution_id"]
        original=self.client.get("/api/v1/solutions/"+sid).json()
        before=self.client.get("/api/v1/runs/"+individual["id"]).json()
        ses=self.session(camp)
        self.interact(ses,participant_id=camp["participants"][1]["id"],agent_minutes=9)
        closed=self.send("/api/v1/sessions/"+ses["id"]+"/close",
            self.results(outcome="failed",quality_score=15,cost_mode="unknown"))
        self.assertEqual(closed.status_code,201,closed.content)
        composite=closed.json()
        self.assertEqual(composite["outcome"],"failed")
        self.assertEqual(composite["kind"],"composite")
        self.assertIsNone(composite["solution_id"])
        self.assertEqual(MeasuredSolution.objects.count(),1)
        self.assertEqual(BenchmarkRun.objects.count(),1)
        self.assertEqual(self.client.get("/api/v1/solutions/"+sid).json(),original)
        self.assertEqual(self.client.get("/api/v1/runs/"+individual["id"]).json(),before)
        all_rows=self.client.get("/api/v1/runs?campaign_id="+camp["id"]).json()["results"]
        self.assertEqual({r["kind"] for r in all_rows},{"individual","composite"})
        self.assertEqual(self.client.get("/api/v1/runs?solution_id="+sid).json()
                         ["results"][0]["id"],individual["id"])
        self.assertEqual(self.client.get("/api/v1/runs?kind=composite&solution_id="+sid)
                         .status_code,400)
        # Re-reading a composite is not a qualification/review event for individuals.
        for _ in range(2):
            self.assertEqual(self.client.get("/api/v1/runs/"+composite["id"]).json(),composite)
            self.assertEqual(self.client.get("/api/v1/solutions/"+sid).json(),original)

    def test_composite_rejects_invalid_close_and_enforces_access_integrity(self):
        camp=self.campaign()
        ses=self.session(camp)
        path="/api/v1/sessions/"+ses["id"]+"/close"
        self.assertEqual(self.send(path,self.results(rev="r001")).status_code,400)
        self.interact(ses)
        for data in (
            self.results(quality_score=101),self.results(cost_mode="flat_rate",cost_eur=0),
            self.results(produced_outputs=""),self.results(evidence_link_ids=["nope"]),
        ):
            with self.subTest(data=data):
                response=self.send(path,data)
                self.assertIn(response.status_code,(400,409),response.content)
        self.assertEqual(CompositeBenchmarkRun.objects.count(),0)
        self.assertEqual(MeasuredSolution.objects.count(),0)
        outsider=Client(enforce_csrf_checks=True)
        outsider.force_login(self.other);outsider.get("/api/v1/auth/csrf")
        response=self.send(path,self.results(),client=outsider,
                           csrf=outsider.cookies["csrftoken"].value)
        self.assertEqual(response.status_code,403,response.content)
        missing=Client(enforce_csrf_checks=True);missing.force_login(self.editor)
        self.assertEqual(missing.post(path,json.dumps(self.results()),
                          content_type="application/json").status_code,403)
        self.assertEqual(self.send("/api/v1/sessions/"+ses["id"]+"/actions/pause",
                                   {"expected_revision":"r002"}).status_code,200)
        self.assertEqual(self.send(path,self.results(rev="r003")).status_code,409)
        self.assertEqual(self.send("/api/v1/sessions/"+ses["id"]+"/actions/resume",
                                   {"expected_revision":"r003"}).status_code,200)
        self.assertEqual(self.send(path,self.results(rev="r003")).status_code,409)
        closed=self.send(path,self.results(rev="r004"))
        self.assertEqual(closed.status_code,201,closed.content)
        run=CompositeBenchmarkRun.objects.get(public_id=closed.json()["id"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompositeBenchmarkRun.objects.filter(pk=run.pk).update(metrics={})
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompositeRunParticipant.objects.filter(run=run).delete()
        self.assertEqual(self.client.get("/api/v1/runs/"+run.public_id).status_code,200)
        unauthorized=Client();unauthorized.force_login(self.maint)
        self.assertEqual(unauthorized.get("/api/v1/runs/"+run.public_id).status_code,403)
        self.assertEqual(Client().get("/api/v1/runs/"+run.public_id).status_code,401)

    def test_membership_trigger_rejects_foreign_campaign_pin(self):
        camp=self.campaign()
        ses=self.session(camp)
        self.interact(ses)
        closed=self.send("/api/v1/sessions/"+ses["id"]+"/close",self.results())
        self.assertEqual(closed.status_code,201,closed.content)
        run=CompositeBenchmarkRun.objects.get(public_id=closed.json()["id"])
        other=self.campaign()
        other_ses=self.session(other)
        foreign=other_ses.campaign_snapshot if not isinstance(other_ses,dict) else BenchmarkSession.objects.get(
            public_id=other_ses["id"]).campaign_snapshot
        pin=foreign.participant_pins.first()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompositeRunParticipant.objects.create(run=run,participant_pin=pin,position=99)
