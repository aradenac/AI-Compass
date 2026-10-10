"""PLAT-15: immutable individual run completion, provenance, evidence and identity reuse."""
import hashlib
import json
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import Client, TestCase, override_settings

from .catalog_services import create_component, revise_component
from .identity import ensure_roles
from .models import BenchmarkRun, BenchmarkRunEvidence, CatalogItem, MeasuredSolution, SessionCheckpoint
from .setup_guide_services import create as create_guide, revise as revise_guide
from .task_services import create_task
from .test_case_services import create as create_case, revise as revise_case


class IndividualRunTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U=get_user_model()
        cls.editor=U.objects.create_user("run-editor",password="test")
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.other=U.objects.create_user("run-other",password="test")
        cls.other.groups.add(Group.objects.get(name="contributor"))
        cls.reader=U.objects.create_user("run-reader",password="test")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=U.objects.create_user("run-maint",password="test")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.editor,name="Driver SPI")
        cls.case=create_case(actor=cls.editor,task_id=cls.task.item.public_id,
                             name="TC1",properties={"objective":"SPI","dod":"Build and regression"})
        cls.guide=create_guide(actor=cls.editor,name="Linux setup",
                               properties={"text":"Run Zephyr native_sim"})
        cls.catalog={k:create_component(type_slug=k,actor=cls.editor,
                  name=k+" setup",properties={"unknown":None}) for k in ("model","provider","harness")}
        cls.framework=create_component(type_slug="framework",actor=cls.editor,
                                         name="Spec Kit",properties={})

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="ai-compass-run-")
        self.addCleanup(temp.cleanup)
        self.evidence_root=Path(temp.name)
        override=override_settings(EVIDENCE_STORE_ROOT=self.evidence_root)
        override.enable();self.addCleanup(override.disable)
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.token=self.client.cookies["csrftoken"].value
        self.client.force_login(self.editor)

    def send(self,path,payload,method="POST",client=None,token=None):
        browser=client or self.client
        fn=browser.patch if method=="PATCH" else browser.post
        return fn(path,json.dumps(payload),content_type="application/json",
                  HTTP_X_CSRFTOKEN=token if token is not None else self.token)

    def campaign(self,mode="task_centred",framework=False,settings=None):
        p={"name":"SPI benchmark","objective":"Check driver","mode":mode,
           "test_case_ids":[self.case.item.public_id],
           "guide_id":self.guide.public_id,"configuration":settings or {"reasoning":None}}
        if mode=="task_centred":p["task_id"]=self.task.item.public_id
        else:p["component_ids"]={k:v.public_id for k,v in self.catalog.items()}
        if framework:
            p["framework_id"]=self.framework.public_id
            p.pop("component_ids",None)
            p["participants"]=[{
                "label":"Builder","role":"Developer","configuration_version":"1",
                "component_ids":{k:v.public_id for k,v in self.catalog.items()},
                "settings":settings or {"reasoning":None},
                "properties":{"tool_access":{"shell":True,"other":None}}
            }]
        res=self.send("/api/v1/campaigns",p)
        self.assertEqual(res.status_code,201,res.content)
        created=res.json()
        started=self.send("/api/v1/campaigns/"+created["id"]+"/actions/start",
            {"expected_revision":"r001"})
        self.assertEqual(started.status_code,200,started.content)
        return started.json()["campaign"]

    def session(self,camp,settings=None):
        payload={"test_case_id":self.case.item.public_id}
        if camp["framework_id"]:
            payload["selected_participant_ids"]=[x["id"] for x in camp["participants"]]
        elif camp["mode"]=="task_centred":
            payload["component_ids"]={k:v.public_id for k,v in self.catalog.items()}
            payload["settings"]=settings or {"reasoning":None}
            payload["properties"]={"tools":["git"],"nullable":None}
            payload["configuration_version"]="v1"
        response=self.send("/api/v1/campaigns/"+camp["id"]+"/sessions",payload)
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def interaction(self,session,revision="r001",text="First prompt",more=None):
        response=self.send("/api/v1/sessions/"+session["id"]+"/interactions",{
            "expected_revision":revision,"type":"human_prompt","content":text,
            "human_minutes":0,"agent_minutes":None,
            "extensions":{"unknown":{"nullable":None}},
            **(more or {})})
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def upload(self,camp,body=b"original captured test report\n"):
        response=self.client.post("/api/v1/catalog/items/"+camp["id"]+"/evidence/upload",{
            "file":SimpleUploadedFile("test-report.txt",body,content_type="text/plain"),
            "revision":"r002","source":"experiment:test-case",
            "provenance":json.dumps({"capture":"test","unknown":None}),
        },HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def result(self,rev="r002",outcome="accepted",**override):
        return {"expected_revision":rev,"outcome":outcome,
                "quality_score":85,"quality_evaluation":"Build and regression passing",
                "information_utility_score":67,"information_utility_evaluation":"Useful patches",
                "tokens_count":None,"tokens_multiplier":1,
                "cost_mode":"flat_rate","cost_eur":None,
                "human_review_minutes":4,"human_correction_minutes":0,
                "produced_outputs":"drivers/ksz8851.c; twister-report.xml",
                "extensions":{"vendor_custom":{"unknown":None}},**override}

    def close(self,s,data):
        return self.send("/api/v1/sessions/"+s["id"]+"/close",data)

    def test_successful_individual_run_original_lineage_and_real_bytes_survive_edits(self):
        camp=self.campaign()
        session=self.session(camp)
        self.assertIsNotNone(session["individual_setup"])
        self.assertEqual(session["individual_setup"]["configuration_version"],"v1")
        stored=b"original captured test report\n"
        link=self.upload(camp,stored)
        a=self.interaction(session,more={"evidence_link_ids":[link["id"]]})
        second=self.interaction(session,"r002","Fix and retest",{
            "agent_minutes":15.5,"occurred_at":"2026-10-10T11:31:00+02:00",
            "extensions":{"extra":"preserved"}})
        self.assertEqual(second["revision"],"r003")
        payload=self.result(rev="r003",evidence_link_ids=[link["id"]])
        closed=self.close(session,payload)
        self.assertEqual(closed.status_code,201,closed.content)
        run=closed.json()
        self.assertTrue(run["id"].startswith("run-"))
        self.assertTrue(run["solution_id"].startswith("sol-"))
        self.assertEqual(run["closing_checkpoint"],"r004")
        self.assertEqual(run["outcome"],"accepted")
        self.assertEqual(run["solution_lifecycle"],"draft")
        self.assertIsNone(run["metrics"]["tokens_total"])
        self.assertIsNone(run["metrics"]["interaction_agent_minutes"])
        self.assertEqual(run["metrics"]["human_correction_minutes"],0)
        self.assertEqual(run["metrics"]["cost_mode"],"flat_rate")
        self.assertIsNone(run["metrics"]["cost_eur"])
        self.assertEqual(run["provenance"]["method_version"],1)
        self.assertEqual(run["provenance"]["campaign_mode"],"task_centred")
        self.assertEqual(run["provenance"]["test_case_revision_id"],
                         camp["test_case_revisions"][0]["revision_id"])
        self.assertEqual(run["provenance"]["guide_revision_id"],camp["guide_revision_id"])
        self.assertEqual(run["raw_session_state"]["status"],"closed")
        self.assertEqual([x["content"] for x in run["raw_session_state"]["interactions"]],
                         ["First prompt","Fix and retest"])
        self.assertEqual(run["raw_session_state"]["interactions"][0]["extensions"],
                         {"unknown":{"nullable":None}})
        self.assertEqual(run["raw_session_state"]["interactions"][1]["extensions"],
                         {"extra":"preserved"})
        self.assertEqual(run["metrics"]["extensions"],{"vendor_custom":{"unknown":None}})
        self.assertEqual(run["evidence"][0]["id"],link["id"])
        self.assertEqual(run["evidence"][0]["sha256"],hashlib.sha256(stored).hexdigest())
        browser_b=Client();browser_b.force_login(self.reader)
        self.assertEqual(browser_b.get("/api/v1/runs/"+run["id"]).json(),run)
        self.assertEqual(len(browser_b.get("/api/v1/runs?campaign_id="+camp["id"]).json()
                             ["results"]),1)
        self.assertEqual(len(browser_b.get("/api/v1/solutions").json()["results"]),1)
        self.assertEqual(browser_b.get("/api/v1/solutions/"+run["solution_id"]).json()
                         ["recommended"],False)
        self.assertEqual(b"".join(browser_b.get(run["evidence"][0]["download"])
                          .streaming_content),stored)
        self.assertEqual(self.send("/api/v1/sessions/"+session["id"]+"/interactions",{
            "expected_revision":"r004","content":"mutate closed"}).status_code,409)
        self.assertEqual(self.close(session,payload).status_code,409)

        revise_case(actor=self.editor,public_id=self.case.item.public_id,
            expected_revision="r001",properties={"dod":"Stricter acceptance"})
        revise_guide(actor=self.editor,public_id=self.guide.public_id,
            expected_revision="r001",properties={"text":"New setup"})
        revise_component(item=self.catalog["model"],type_slug="model",actor=self.editor,
                         expected_revision="r001",name="Model newer")
        after=browser_b.get("/api/v1/runs/"+run["id"]).json()
        self.assertEqual(after,run)
        self.assertEqual(CatalogItem.objects.filter(type_slug="ai_solution").count(),1)

    def test_reuse_identical_solution_and_distinct_changed_configuration(self):
        camp=self.campaign()
        first=self.session(camp,settings={"temperature":0.2})
        self.interaction(first)
        a=self.close(first,self.result()).json()
        second=self.session(camp,settings={"temperature":0.2})
        self.interaction(second)
        b=self.close(second,self.result(outcome="failed",quality_score=0,
                                        cost_mode="unknown")).json()
        self.assertNotEqual(a["id"],b["id"])
        self.assertEqual(a["solution_id"],b["solution_id"])
        self.assertEqual(b["outcome"],"failed")
        self.assertEqual(b["solution_lifecycle"],"draft")
        changed=self.session(camp,settings={"temperature":0.21})
        self.interaction(changed)
        c=self.close(changed,self.result(cost_mode="amount",cost_eur=0,
                                        tokens_count=0,tokens_multiplier=1000)).json()
        self.assertNotEqual(c["solution_id"],a["solution_id"])
        self.assertEqual(c["metrics"]["tokens_total"],0)
        self.assertEqual(c["metrics"]["cost_eur"],0)
        self.assertEqual(MeasuredSolution.objects.count(),2)
        self.assertEqual(BenchmarkRun.objects.count(),3)
        self.assertEqual(self.client.get("/api/v1/solutions/"+a["solution_id"])
                         .json()["run_ids"],[a["id"],b["id"]])

    def test_framework_single_participant_stays_individual_and_multi_completes_composite(self):
        camp=self.campaign(framework=True,settings={"model_hint":{"future":None}})
        s=self.session(camp)
        self.assertEqual(s["individual_setup"]["settings"],{"model_hint":{"future":None}})
        self.interaction(s)
        closed=self.close(s,self.result()).json()
        self.assertEqual(closed["provenance"]["selected_participant_ids"],
                         [camp["participants"][0]["id"]])
        self.assertEqual(closed["provenance"]["framework_revision_id"],
                         camp["framework_revision_id"])
        # A 2-participant draft is composite and belongs exclusively to #16.
        add=self.send("/api/v1/campaigns/"+camp["id"],{
            "expected_revision":camp["revision"],"participants":[
                {**{k:v for k,v in camp["participants"][0].items() if k in (
                    "id","label","role","component_ids","configuration_version","settings","properties")}},
                {"label":"Reviewer","role":"Reviewer",
                 "component_ids":{k:v.public_id for k,v in self.catalog.items()},
                 "configuration_version":"1","settings":{},"properties":{}},
            ]},"PATCH")
        self.assertEqual(add.status_code,200,add.content)
        revised=add.json()["campaign"]
        two=self.send("/api/v1/campaigns/"+camp["id"]+"/sessions",{
            "test_case_id":self.case.item.public_id,
            "selected_participant_ids":[p["id"] for p in revised["participants"]]})
        self.assertEqual(two.status_code,201,two.content)
        composite=two.json()
        self.assertIsNone(composite["individual_setup"])
        self.interaction(composite)
        completed=self.close(composite,self.result())
        self.assertEqual(completed.status_code,201,completed.content)
        self.assertEqual(completed.json()["kind"],"composite")
        self.assertIsNone(completed.json()["solution_id"])
        self.assertEqual(len(completed.json()["participants"]),2)
        self.assertEqual(BenchmarkRun.objects.count(),1)
        self.assertEqual(MeasuredSolution.objects.count(),1)

    def test_reject_invalid_metrics_missing_interactions_invalid_evidence_and_csrf(self):
        camp=self.campaign()
        ses=self.session(camp)
        self.assertEqual(self.close(ses,self.result("r001")).status_code,400)
        self.interaction(ses)
        bad=[
            self.result(outcome="unknown"),self.result(quality_score=-1),
            self.result(information_utility_score=101),
            self.result(tokens_count=-1),self.result(tokens_count=None,tokens_multiplier=100),
            self.result(cost_mode="amount",cost_eur=None),
            self.result(cost_mode="flat_rate",cost_eur=0),
            self.result(cost_mode="unknown",cost_eur=0),
            self.result(produced_outputs="  "),
            self.result(human_review_minutes=-1),
            self.result(evidence_link_ids=["not-a-real-uuid"]),
            self.result(extensions=[]),
        ]
        for payload in bad:
            with self.subTest(payload=payload):
                r=self.close(ses,payload)
                self.assertIn(r.status_code,(400,409),r.content)
        self.assertEqual(BenchmarkRun.objects.count(),0)
        self.assertEqual(MeasuredSolution.objects.count(),0)
        self.assertEqual(SessionCheckpoint.objects.filter(session__public_id=ses["id"]).count(),2)
        no_csrf=Client(enforce_csrf_checks=True);no_csrf.force_login(self.editor)
        self.assertEqual(no_csrf.post("/api/v1/sessions/"+ses["id"]+"/close",
            json.dumps(self.result()),content_type="application/json").status_code,403)
        browser=Client(enforce_csrf_checks=True);browser.force_login(self.other)
        browser.get("/api/v1/auth/csrf")
        response=self.send("/api/v1/sessions/"+ses["id"]+"/close",self.result(),
                           client=browser,token=browser.cookies["csrftoken"].value)
        self.assertEqual(response.status_code,403)
        maintenance=Client();maintenance.force_login(self.maint)
        self.assertEqual(maintenance.get("/api/v1/runs").status_code,403)
        anonymous=Client()
        self.assertEqual(anonymous.get("/api/v1/solutions").status_code,401)

    def test_database_guards_and_solution_centred_reuse(self):
        camp=self.campaign(mode="solution_centred")
        ses=self.session(camp)
        self.interaction(ses)
        run=self.close(ses,self.result()).json()
        record=BenchmarkRun.objects.get(public_id=run["id"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                BenchmarkRun.objects.filter(pk=record.pk).update(outcome="failed")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                MeasuredSolution.objects.filter(pk=record.solution_id).delete()
        self.assertEqual(self.client.get("/api/v1/runs/"+run["id"]).json(),run)
        self.assertEqual(self.client.get("/api/v1/sessions/"+ses["id"])
                         .json()["state"]["status"],"closed")
