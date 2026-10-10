"""PLAT-14: durable server-confirmed session checkpoints and original evidence bytes."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import Client, TestCase, override_settings

from .catalog_services import create_component
from .identity import ensure_roles
from .models import (BenchmarkSession, CampaignSnapshot, ObjectTypeVersion,
                     SessionCheckpoint, SessionCheckpointEvidence)
from .setup_guide_services import create as create_guide, revise as revise_guide
from .task_services import create_task
from .test_case_services import create as create_case, revise as revise_case


class BenchmarkSessionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User=get_user_model()
        cls.editor=User.objects.create_user("session-editor",password="test")
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.other=User.objects.create_user("session-other",password="test")
        cls.other.groups.add(Group.objects.get(name="contributor"))
        cls.third=User.objects.create_user("session-third",password="test")
        cls.third.groups.add(Group.objects.get(name="contributor"))
        cls.reader=User.objects.create_user("session-reader",password="test")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=User.objects.create_user("session-maintainer",password="test")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.editor,name="Embedded SPI driver")
        cls.case=create_case(actor=cls.editor,task_id=cls.task.item.public_id,
            name="TC1",properties={"objective":"Implement API","dod":"Integration tests pass"})
        cls.guide=create_guide(actor=cls.editor,name="Testbench installation",
            properties={"text":"Flash and configure UART"})
        cls.other_guide=create_guide(actor=cls.editor,name="Another guide",
            properties={"url":"https://example.org/install"})
        cls.framework=create_component(type_slug="framework",actor=cls.editor,
            name="n8n",properties={"orchestration":"review"})
        cls.catalog={kind:create_component(type_slug=kind,actor=cls.editor,
            name=kind+" alpha",properties={})
                     for kind in ("model","provider","harness")}

    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="ai-compass-session-evidence-")
        self.addCleanup(t.cleanup)
        self.evidence_root=Path(t.name)
        settings=override_settings(EVIDENCE_STORE_ROOT=self.evidence_root)
        settings.enable();self.addCleanup(settings.disable)
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.csrf=self.client.cookies["csrftoken"].value
        self.client.force_login(self.editor)

    def call(self,path,data,method="POST",client=None,csrf=True):
        browser=client or self.client
        fn=browser.post if method=="POST" else browser.patch
        return fn(path,json.dumps(data),content_type="application/json",
                  **({"HTTP_X_CSRFTOKEN":self.csrf} if csrf else {}))

    def campaign(self,mode="task_centred",framework=False):
        data={"name":"Benchmark session campaign","objective":"Develop driver",
              "mode":mode,"test_case_ids":[self.case.item.public_id],
              "guide_id":self.guide.public_id}
        if mode=="task_centred":
            data["task_id"]=self.task.item.public_id
        else:
            data["component_ids"]={k:v.public_id for k,v in self.catalog.items()}
        if framework:
            data["framework_id"]=self.framework.public_id
            data["participants"]=[{"label":"Implementer","role":"Developer",
                 "component_ids":{k:v.public_id for k,v in self.catalog.items()},
                 "configuration_version":"1","settings":{"context":None}}]
            data.pop("component_ids",None)
        result=self.call("/api/v1/campaigns",data)
        self.assertEqual(result.status_code,201,result.content)
        campaign=result.json()
        result=self.call("/api/v1/campaigns/"+campaign["id"]+"/actions/start",
                         {"expected_revision":"r001"})
        self.assertEqual(result.status_code,200,result.content)
        return result.json()["campaign"]

    def create_session(self,campaign,extra=None):
        payload={"test_case_id":self.case.item.public_id}
        if campaign["framework_id"]:
            payload["selected_participant_ids"]=[p["id"] for p in campaign["participants"]]
        payload.update(extra or {})
        result=self.call("/api/v1/campaigns/"+campaign["id"]+"/sessions",payload)
        self.assertEqual(result.status_code,201,result.content)
        return result.json()

    def evidence(self,item_id,filename="original.txt",content=b"SPI captured log\n"):
        payload={"file":SimpleUploadedFile(filename,content,content_type="text/plain"),
                 "revision":"r001","provenance":json.dumps({"source":"DUT","unknown":None})}
        result=self.client.post("/api/v1/catalog/items/"+item_id+"/evidence/upload",
            data=payload,HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(result.status_code,201,result.content)
        return result.json()

    def test_save_two_interactions_and_evidence_relogin_resume_exact_bytes(self):
        camp=self.campaign()
        self.assertEqual(camp["status"],"in_progress")
        original=self.create_session(camp)
        self.assertTrue(original["id"].startswith("ses-"))
        self.assertEqual(original["revision"],"r001")
        self.assertEqual(original["method_version"],1)
        self.assertEqual(original["method_descriptor"]["steps"][0]["key"],"planning")
        self.assertEqual(original["guide_revision_id"],camp["guide_revision_id"])
        self.assertEqual(original["test_case_revision_id"],camp["test_case_revisions"][0]["revision_id"])
        self.assertIsNone(original["state"]["measurements"]["agent_total_minutes"])
        link=self.evidence(camp["id"],content=b"Experimental driver artifact\n")
        b="/api/v1/sessions/"+original["id"]
        started=self.call(b+"/setup",{
            "expected_revision":"r001",
            "started_at":"2026-10-10T09:00:00+02:00",
            "installation_duration_minutes":None,
            "environment":{"os":"Ubuntu","extension":{"nullable":None}},
            "notes":"Configured JTAG; first prompt not yet given",
            "extensions":{"custom":{"extra":True}},
            "evidence_link_ids":[link["id"]]},"PATCH")
        self.assertEqual(started.status_code,200,started.content)
        self.assertEqual(started.json()["state"]["setup"]["started_at"],"2026-10-10T07:00:00+00:00")
        self.assertIsNone(started.json()["state"]["setup"]["installation_duration_minutes"])
        step=self.call(b+"/steps/planning",{"expected_revision":"r002",
             "values":{"objective":"KSZ driver", "unknown_future":{"nullable":None}},
             "extensions":{"external_schema":{"v":2}},
             "status":"in_progress","duration_minutes":0,
             "evidence_link_ids":[link["id"]]},"PATCH")
        self.assertEqual(step.status_code,200,step.content)
        self.assertEqual(step.json()["state"]["steps"]["planning"]["duration_minutes"],0)
        self.assertIsNone(step.json()["state"]["steps"]["review"]["duration_minutes"])
        first=self.call(b+"/interactions",{"expected_revision":"r003",
              "type":"human_prompt","content":"Implement and test SPI driver",
              "occurred_at":"2026-10-10T09:15:00+02:00",
              "human_minutes":4.5,"agent_minutes":None,
              "evidence_link_ids":[link["id"]],
              "extensions":{"tool_options":{"unknown":None}}})
        self.assertEqual(first.status_code,200,first.content)
        second=self.call(b+"/interactions",{"expected_revision":"r004",
              "type":"agent_response","content":"Applied source patch and built tests",
              "human_minutes":0,"agent_minutes":9.25,
              "notes":"Intermediate successful build"})
        self.assertEqual(second.status_code,200,second.content)
        updated=second.json()
        self.assertEqual(updated["revision"],"r005")
        self.assertEqual([r["type"] for r in updated["state"]["interactions"]],
                         ["human_prompt","agent_response"])
        self.assertEqual([r["order"] for r in updated["state"]["interactions"]],[0,1])
        self.assertEqual(updated["state"]["interactions"][0]["extensions"]["tool_options"],
                         {"unknown":None})
        self.assertIsNone(updated["state"]["measurements"]["agent_total_minutes"])
        self.assertEqual(updated["state"]["measurements"]["human_total_minutes"],4.5)
        self.assertEqual(len(updated["evidence"]),1)
        self.assertEqual(updated["evidence"][0]["sha256"],link["sha256"])
        self.assertEqual(hashlib.sha256(b"Experimental driver artifact\n").hexdigest(),link["sha256"])
        self.assertEqual(SessionCheckpointEvidence.objects.filter(
            checkpoint__session__public_id=original["id"]).count(),4)

        # A fresh browser and client instance sees exactly the durable DB checkpoint.
        browser_b=Client()
        browser_b.force_login(self.reader)
        resumed=browser_b.get(b)
        self.assertEqual(resumed.status_code,200)
        self.assertEqual(resumed.json(),updated)
        self.assertEqual(browser_b.get(b+"/checkpoints/4").json()["state"]
                         ["interactions"][0]["content"],"Implement and test SPI driver")
        self.assertEqual(browser_b.get(b+"/checkpoints/3").json()["state"]["interactions"],[])
        self.assertEqual([x["revision"] for x in browser_b.get(b+"/checkpoints").json()
                          ["checkpoints"]],["r001","r002","r003","r004","r005"])
        data=browser_b.get("/api/v1/evidence/"+link["id"]+"/download")
        self.assertEqual(b"".join(data.streaming_content),b"Experimental driver artifact\n")
        self.assertEqual(browser_b.get("/api/v1/campaigns/"+camp["id"]+"/sessions")
                         .json()["results"][0]["revision"],"r005")

    def test_schema_evolution_frozen_steps_and_guide_even_after_campaign_edit(self):
        camp=self.campaign()
        old=self.create_session(camp)
        old_schema=deepcopy(old["method_descriptor"])
        changed=deepcopy(old_schema)
        changed["steps"]=[changed["steps"][1],changed["steps"][0],
                          {"key":"security","label":"Safety verification","fields":[{"key":"risk"}]}]
        changed["fields"].append({"key":"risk","type":"text","step":"security"})
        ObjectTypeVersion.objects.create(
            type_slug="campaign_method_task_centred",version=2,json_schema=changed)
        revise_guide(actor=self.editor,public_id=self.guide.public_id,
                     expected_revision="r001",properties={"text":"Changed test rig"})
        revise_case(actor=self.editor,public_id=self.case.item.public_id,
                    expected_revision="r001",properties={"dod":"More stringent DoD"})
        rewrite=self.call("/api/v1/campaigns/"+camp["id"],{
            "expected_revision":camp["revision"],"method_version":2,
            "guide_id":self.guide.public_id,"repin":True},"PATCH")
        self.assertEqual(rewrite.status_code,200,rewrite.content)
        self.assertEqual(rewrite.json()["campaign"]["method_version"],2)
        recent=self.create_session(rewrite.json()["campaign"])
        self.assertEqual(recent["method_version"],2)
        self.assertEqual([x["key"] for x in recent["method_descriptor"]["steps"]],
                         ["execution","planning","security"])
        # PostgreSQL JSONB dictionaries are not ordered. Step order is carried
        # by the frozen method descriptor's steps array, not the state map.
        self.assertEqual(set(recent["state"]["steps"]),{"execution","planning","security"})
        self.assertEqual(self.client.get("/api/v1/sessions/"+old["id"]).json()
                         ["method_descriptor"],old_schema)
        self.assertEqual(self.client.get("/api/v1/sessions/"+old["id"]).json()
                         ["guide_revision_id"],old["guide_revision_id"])
        fail=self.call("/api/v1/sessions/"+old["id"]+"/steps/security",{
            "expected_revision":"r001","values":{"risk":12}},"PATCH")
        self.assertEqual(fail.status_code,400)
        good=self.call("/api/v1/sessions/"+recent["id"]+"/steps/security",{
            "expected_revision":"r001","values":{"risk":"High"},"extensions":{"future":None}},"PATCH")
        self.assertEqual(good.status_code,200,good.content)
        self.assertEqual(good.json()["state"]["steps"]["security"]["values"]["risk"],"High")

    def test_invalid_references_stale_revision_csrf_and_evidence_scope(self):
        camp=self.campaign()
        session=self.create_session(camp)
        b="/api/v1/sessions/"+session["id"]
        self.assertEqual(self.call(b+"/steps/unknown",{"expected_revision":"r001"},"PATCH").status_code,400)
        self.assertEqual(self.call(b+"/setup",{"expected_revision":"r001",
                         "installation_duration_minutes":-1},"PATCH").status_code,400)
        self.assertEqual(self.call(b+"/interactions",{"expected_revision":"r001",
                         "content":"bad tz","occurred_at":"2026-10-10T12:00:00"}).status_code,400)
        self.assertEqual(self.call(b+"/interactions",{"expected_revision":"r001",
                         "content":"bad metrics","agent_minutes":False}).status_code,400)
        self.assertEqual(self.call(b+"/interactions",{"expected_revision":"r001",
                         "content":"bad link","evidence_link_ids":["invalid"]}).status_code,400)
        foreign=self.evidence(self.other_guide.public_id)
        self.assertEqual(self.call(b+"/interactions",{"expected_revision":"r001",
                         "content":"foreign link","evidence_link_ids":[foreign["id"]]}).status_code,400)
        self.assertEqual(self.call(b+"/setup",{"expected_revision":"r001",
                         "environment":{"nullable":None}},"PATCH",csrf=False).status_code,403)
        self.assertEqual(SessionCheckpoint.objects.filter(session__public_id=session["id"]).count(),1)
        okay=self.call(b+"/interactions",{"expected_revision":"r001",
                          "content":"First real prompt"})
        self.assertEqual(okay.status_code,200,okay.content)
        self.assertIsNone(okay.json()["state"]["interactions"][0]["human_minutes"])
        self.assertIsNone(okay.json()["state"]["interactions"][0]["agent_minutes"])
        self.assertEqual(self.call(b+"/interactions",{"expected_revision":"r001",
                         "content":"Racing browser prompt"}).status_code,409)
        self.assertEqual(SessionCheckpoint.objects.filter(session__public_id=session["id"]).count(),2)

    def test_lifecycle_scoping_user_permissions_and_multiple_attempts(self):
        planned_payload={"name":"Not started","objective":"Compare","mode":"task_centred",
                         "task_id":self.task.item.public_id,
                         "test_case_ids":[self.case.item.public_id]}
        planned=self.call("/api/v1/campaigns",planned_payload).json()
        self.assertEqual(self.call("/api/v1/campaigns/"+planned["id"]+"/sessions",{
            "test_case_id":self.case.item.public_id}).status_code,409)
        camp=self.campaign(framework=True)
        self.assertEqual(self.call("/api/v1/campaigns/"+camp["id"]+"/sessions",{
            "test_case_id":self.case.item.public_id}).status_code,400)
        self.assertEqual(self.call("/api/v1/campaigns/"+camp["id"]+"/sessions",{
            "test_case_id":self.case.item.public_id,
            "selected_participant_ids":["ptp-fake-id"]}).status_code,400)
        one=self.create_session(camp)
        two=self.create_session(camp)
        self.assertNotEqual(one["id"],two["id"])
        self.assertEqual(one["selected_participant_ids"],
                         [p["id"] for p in camp["participants"]])
        b="/api/v1/sessions/"+one["id"]
        self.assertEqual(self.call(b+"/interactions",{"expected_revision":"r001",
                 "content":"Delegate work","participant_id":one["selected_participant_ids"][0]}).status_code,200)
        self.assertEqual(self.call(b+"/interactions",{"expected_revision":"r002",
                 "content":"Foreign agent","participant_id":"ptp-fake"}).status_code,400)

        # Contributor B may create and update their own draft in a shared campaign;
        # contributor C cannot mutate it, but campaign owner A can.
        another=Client(enforce_csrf_checks=True)
        another.force_login(self.other);another.get("/api/v1/auth/csrf")
        token=another.cookies["csrftoken"].value
        # Use the correct per-browser CSRF token for a real cross-user write.
        created=another.post("/api/v1/campaigns/"+camp["id"]+"/sessions",
            data=json.dumps({"test_case_id":self.case.item.public_id,
                            "selected_participant_ids":one["selected_participant_ids"]}),
            content_type="application/json",HTTP_X_CSRFTOKEN=token)
        self.assertEqual(created.status_code,201,created.content)
        other_session=created.json()
        outsider=Client(enforce_csrf_checks=True)
        outsider.force_login(self.third);outsider.get("/api/v1/auth/csrf")
        self.assertEqual(outsider.patch("/api/v1/sessions/"+other_session["id"]+"/setup",
          data=json.dumps({"expected_revision":"r001","notes":"tamper"}),
          content_type="application/json",
          HTTP_X_CSRFTOKEN=outsider.cookies["csrftoken"].value).status_code,403)
        self.assertEqual(self.call("/api/v1/sessions/"+other_session["id"]+"/setup",{
          "expected_revision":"r001","notes":"Campaign owner review"},"PATCH").status_code,200)
        anon=Client()
        self.assertEqual(anon.get(b).status_code,401)
        maintenance=Client();maintenance.force_login(self.maint)
        self.assertEqual(maintenance.get(b).status_code,403)
        read=Client();read.force_login(self.reader)
        self.assertEqual(read.get(b).status_code,200)
        self.assertEqual(self.call(b+"/setup",{"expected_revision":"r002","notes":"no"},
            "PATCH",client=read).status_code,403)

    def test_pg_immutable_session_and_evidence_guards(self):
        camp=self.campaign()
        one=self.create_session(camp)
        link=self.evidence(camp["id"])
        saved=self.call("/api/v1/sessions/"+one["id"]+"/setup",{
            "expected_revision":"r001","evidence_link_ids":[link["id"]]},"PATCH")
        self.assertEqual(saved.status_code,200,saved.content)
        session=BenchmarkSession.objects.get(public_id=one["id"])
        cp=SessionCheckpoint.objects.get(session=session,number=2)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                BenchmarkSession.objects.filter(pk=session.pk).update(method_descriptor={})
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                SessionCheckpoint.objects.filter(pk=cp.pk).update(state={})
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                SessionCheckpointEvidence.objects.filter(checkpoint=cp).delete()
        self.assertEqual(self.client.get("/api/v1/sessions/"+one["id"]+"/checkpoints/2")
                         .json()["evidence"][0]["sha256"],link["sha256"])
