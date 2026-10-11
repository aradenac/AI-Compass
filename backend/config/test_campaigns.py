"""PLAT-12 campaign lifecycle: real Server FKs, revision/method pins, roles and Demo exclusion."""
import json
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError,transaction
from django.test import Client,TestCase

from .catalog_services import create_component,revise_component
from .identity import ensure_roles
from .models import (CampaignSnapshot,CampaignCasePin,CampaignComponentPin,
                     CatalogItem,CatalogRevision,ObjectTypeVersion)
from .setup_guide_services import create as create_guide,revise as revise_guide
from .task_services import create_task
from .test_case_services import create as create_case,revise as revise_case

BASE="/api/v1/campaigns"


class CampaignApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U=get_user_model()
        cls.writer=U.objects.create_user("campaign-writer",password="safe-test-password-2026")
        cls.writer.groups.add(Group.objects.get(name="contributor"))
        cls.reviewer=U.objects.create_user("campaign-reviewer",password="safe-test-password-2026")
        cls.reviewer.groups.add(Group.objects.get(name="reviewer"))
        cls.reader=U.objects.create_user("campaign-reader",password="safe-test-password-2026")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=U.objects.create_user("campaign-maintainer",password="safe-test-password-2026")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.writer,name="Driver KSZ8851SNL")
        cls.other_task=create_task(actor=cls.writer,name="Zephyr shell")
        cls.case=create_case(actor=cls.writer,task_id=cls.task.item.public_id,
                             name="TC1 driver SPI",properties={"objective":"Write driver",
                             "dod":"All required tests pass","custom":{"nullable":None}})
        cls.other_case=create_case(actor=cls.writer,task_id=cls.other_task.item.public_id,
                                   name="TC2 shell",properties={"objective":"Write shell","dod":"Build passes"})
        cls.guide=create_guide(actor=cls.writer,name="Setup SPI testbench",
                               properties={"text":"Configure bus and boot DUT"})
        cls.components={kind:create_component(type_slug=kind,actor=cls.writer,
                                              name=kind+" for test",properties={})
                        for kind in ("model","provider","harness")}

    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.token=self.client.cookies["csrftoken"].value
        self.client.force_login(self.writer)

    def call(self,path,payload,method="POST",user=None,csrf=True):
        if user is not None:
            self.client.force_login(user)
        func=self.client.post if method=="POST" else self.client.patch
        return func(path,json.dumps(payload),content_type="application/json",
                    **({"HTTP_X_CSRFTOKEN":self.token} if csrf else {}))

    def task_payload(self):
        return {"name":"SPI driver benchmark", "objective":"Choose best AI implementation",
                "mode":"task_centred","task_id":self.task.item.public_id,
                "test_case_ids":[self.case.item.public_id],
                "guide_id":self.guide.public_id,
                "configuration":{"temperature":None,"other":{"preserve":[1,None]}},
                "properties":{"ext":{"custom":True}}}

    def new(self,payload=None):
        response=self.call(BASE,payload if payload is not None else self.task_payload())
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def test_fresh_server_only_definitions_not_campaigns(self):
        self.assertEqual(self.client.get(BASE).json(),{"results":[]})
        self.assertEqual(self.client.get(BASE+"/pipeline").json()["columns"],
                         {state:[] for state in ("planned","in_progress","under_review","published")})
        self.assertEqual(CatalogItem.objects.filter(type_slug="campaign").count(),0)
        methods=self.client.get("/api/v1/campaign-methods").json()["results"]
        self.assertEqual({m["mode"] for m in methods},{"task_centred","solution_centred"})
        self.assertTrue(all(m["version"]==1 and m["descriptor"]["steps"] for m in methods))

    def test_workgroup_cross_browser_edit_pins_and_historical_guide_case(self):
        new=self.new()
        self.assertTrue(new["id"].startswith("cmp-"))
        self.assertEqual(new["revision"],"r001")
        self.assertEqual(new["status"],"planned")
        self.assertEqual(new["method_version"],1)
        self.assertEqual(new["task_revision_id"],str(self.task.item.current_revision_id))
        original_case=new["test_case_revisions"][0]["revision_id"]
        original_guide=new["guide_revision_id"]
        self.assertEqual(new["properties"]["ext"],{"custom":True})
        browser2=Client()
        browser2.force_login(self.writer)
        self.assertEqual(browser2.get(BASE+"/"+new["id"]).json()["revision_id"],new["revision_id"])
        self.assertEqual(browser2.get(BASE).json()["results"][0]["id"],new["id"])
        # Changes elsewhere do not silently re-pin the selected original revision.
        revise_guide(actor=self.writer,public_id=self.guide.public_id,
                     expected_revision="r001",properties={"text":"New instructions"})
        revise_case(actor=self.writer,public_id=self.case.item.public_id,
                    expected_revision="r001",properties={"dod":"Strengthened test criteria"})
        result=self.call(BASE+"/"+new["id"],{"expected_revision":"r001",
                     "notes":"Add a new note"},method="PATCH")
        self.assertEqual(result.status_code,200,result.content)
        updated=result.json()["campaign"]
        self.assertEqual(updated["revision"],"r002")
        self.assertEqual(updated["guide_revision_id"],original_guide)
        self.assertEqual(updated["test_case_revisions"][0]["revision_id"],original_case)
        self.assertEqual(updated["configuration"],new["configuration"])
        self.assertEqual(updated["properties"]["ext"],{"custom":True})
        hist=browser2.get(BASE+"/"+new["id"]+"/revisions").json()["revisions"]
        self.assertEqual([x["revision"] for x in hist],["r001","r002"])
        self.assertEqual(hist[0]["revision_id"],new["revision_id"])
        self.assertEqual(hist[0]["properties"]["notes"] if "notes" in hist[0]["properties"] else "", "")
        self.assertEqual(self.client.get(BASE+"/"+new["id"]+"/revisions/1").json()["guide_revision_id"],
                         original_guide)
        repin=self.call(BASE+"/"+new["id"],{"expected_revision":"r002",
                          "guide_id":self.guide.public_id,
                          "test_case_ids":[self.case.item.public_id],"repin":True},method="PATCH")
        self.assertEqual(repin.status_code,200,repin.content)
        rev3=repin.json()["campaign"]
        self.assertNotEqual(rev3["guide_revision_id"],original_guide)
        self.assertNotEqual(rev3["test_case_revisions"][0]["revision_id"],original_case)
        self.assertEqual(CampaignSnapshot.objects.filter(revision__item__public_id=new["id"]).count(),3)
        self.assertEqual(CampaignCasePin.objects.filter(snapshot__revision__item__public_id=new["id"]).count(),3)
        self.assertEqual(self.call(BASE+"/"+new["id"],{"expected_revision":"r001",
                         "name":"lost update"},method="PATCH").status_code,409)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CampaignSnapshot.objects.filter(revision_id=new["revision_id"]).update(configuration={})
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CampaignCasePin.objects.filter(snapshot__revision_id=new["revision_id"]).delete()

    def test_solution_fixed_components_and_method_v1_v2_never_reinterpreted(self):
        payload={"name":"One model across tasks","objective":"Compare tasks",
                 "mode":"solution_centred",
                 "component_ids":{k:v.public_id for k,v in self.components.items()},
                 "test_case_ids":[self.case.item.public_id,self.other_case.item.public_id],
                 "configuration":{"model_args":{"x":None}}}
        original=self.new(payload)
        self.assertEqual(set(original["component_ids"]),set(self.components))
        old_pins=deepcopy(original["component_revisions"])
        first_method_id=original["method_definition_id"]
        row=ObjectTypeVersion.objects.get(type_slug="campaign_method_solution_centred",version=1)
        next_definition=deepcopy(row.json_schema)
        next_definition["criteria"].append({"key":"safety","label":"Safety review"})
        ObjectTypeVersion.objects.create(type_slug=row.type_slug,version=2,json_schema=next_definition)
        self.assertEqual(self.client.get(BASE+"/"+original["id"]).json()["method_definition_id"],
                         first_method_id)
        changed=self.call(BASE+"/"+original["id"],{"expected_revision":"r001",
                    "method_version":2,"notes":"New method version applied"},method="PATCH")
        self.assertEqual(changed.status_code,200,changed.content)
        v2=changed.json()["campaign"]
        self.assertEqual(v2["method_version"],2)
        self.assertNotEqual(v2["method_definition_id"],first_method_id)
        self.assertEqual(v2["component_revisions"],old_pins)
        self.assertEqual(self.client.get(BASE+"/"+original["id"]+"/revisions/1").json()["method_version"],1)
        self.assertEqual(self.client.get(BASE+"/"+original["id"]+"/revisions/1").json()["method_definition_id"],
                         first_method_id)
        second=self.new(dict(payload,name="Campaign method v2",method_version=2))
        self.assertEqual(second["method_version"],2)
        model=self.components["model"]
        revised=revise_component(item=model,type_slug="model",actor=self.writer,
                                 expected_revision="r001",name="Updated model")
        self.assertIsNotNone(revised)
        self.assertEqual(self.client.get(BASE+"/"+original["id"]).json()["component_revisions"],
                         old_pins)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CampaignComponentPin.objects.filter(snapshot__revision_id=original["revision_id"]).delete()

    def test_transitions_role_checks_archive_restore_and_history(self):
        row=self.new()
        self.assertEqual(self.call(BASE+"/"+row["id"]+"/actions/close",{
                         "expected_revision":"r001"}).status_code,409)
        self.assertEqual(self.call(BASE+"/"+row["id"]+"/actions/start",{
                         "expected_revision":"r001"},csrf=False).status_code,403)
        started=self.call(BASE+"/"+row["id"]+"/actions/start",{"expected_revision":"r001"}).json()["campaign"]
        self.assertEqual(started["status"],"in_progress")
        reviewed=self.call(BASE+"/"+row["id"]+"/actions/close",{
                           "expected_revision":"r002"}).json()["campaign"]
        self.assertEqual(reviewed["status"],"under_review")
        self.assertEqual(self.call(BASE+"/"+row["id"]+"/actions/publish",{
                         "expected_revision":"r003"}).status_code,403)
        # FUT-10 rejects a publication without any completed, eligible Run.
        published_response=self.call(BASE+"/"+row["id"]+"/actions/publish",{
                                    "expected_revision":"r003","run_ids":[]},user=self.reviewer)
        self.assertEqual(published_response.status_code,400,published_response.content)
        self.assertEqual(self.client.get(BASE+"/"+row["id"]).json()["status"],"under_review")
        self.assertEqual(self.call(BASE+"/"+row["id"],{"expected_revision":"r003",
                         "notes":"Illegal edit"},method="PATCH",user=self.writer).status_code,409)
        self.assertEqual(self.call(BASE+"/"+row["id"]+"/actions/restore",{
                         "expected_revision":"r003"},user=self.writer).status_code,409)
        archived=self.call(BASE+"/"+row["id"]+"/actions/archive",{
                          "expected_revision":"r003"}).json()["campaign"]
        self.assertTrue(archived["archived"])
        self.assertEqual(self.call(BASE+"/"+row["id"]+"/actions/reopen",{
                         "expected_revision":"r004"}).status_code,409)
        restored=self.call(BASE+"/"+row["id"]+"/actions/restore",{
                          "expected_revision":"r004"}).json()["campaign"]
        self.assertFalse(restored["archived"])
        self.assertEqual(restored["status"],"under_review")
        reopened=self.call(BASE+"/"+row["id"]+"/actions/reopen",{
                          "expected_revision":"r005"}).json()["campaign"]
        self.assertEqual(reopened["status"],"in_progress")
        all_revs=self.client.get(BASE+"/"+row["id"]+"/revisions").json()["revisions"]
        self.assertEqual(len(all_revs),6)
        self.assertEqual(all_revs[3]["archived"],True)
        self.assertEqual(self.client.get(BASE+"/pipeline").json()["columns"]["in_progress"][0]["id"],
                         row["id"])
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=row["id"]).count(),6)

    def test_referential_integrity_no_partial_records_and_mode_change_history(self):
        base=self.task_payload()
        wrong=[
            dict(base,task_id="tsk-does-not-exist"),
            dict(base,guide_id="gui-does-not-exist"),
            dict(base,test_case_ids=[self.other_case.item.public_id]),
            dict(base,test_case_ids=[self.case.item.public_id,self.case.item.public_id]),
            dict(base,component_ids={"model":self.components["model"].public_id}),
            dict(base,owner="nonexistent-user"),
            dict(base,method_version=999),
            dict(base,properties={"status":"published"}),
        ]
        for input_data in wrong:
            with self.subTest(data=input_data):
                self.assertEqual(self.call(BASE,input_data).status_code,400)
        self.assertEqual(CatalogItem.objects.filter(type_slug="campaign").count(),0)
        row=self.new()
        modified=self.call(BASE+"/"+row["id"],{"expected_revision":"r001",
                   "mode":"solution_centred",
                   "component_ids":{k:v.public_id for k,v in self.components.items()},
                   "test_case_ids":[self.case.item.public_id]},method="PATCH")
        self.assertEqual(modified.status_code,200,modified.content)
        self.assertIsNone(modified.json()["campaign"]["task_id"])
        first=self.client.get(BASE+"/"+row["id"]+"/revisions/1").json()
        self.assertEqual(first["mode"],"task_centred")
        self.assertEqual(first["task_id"],self.task.item.public_id)
        self.assertEqual(first["method_version"],1)

    def test_authentication_reader_maintainer_csrf_and_no_fake_import(self):
        self.assertEqual(self.call(BASE,self.task_payload(),csrf=False).status_code,403)
        row=self.new()
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(BASE).status_code,200)
        self.assertEqual(self.call(BASE,self.task_payload()).status_code,403)
        self.assertEqual(self.call(BASE+"/"+row["id"]+"/actions/start",{
                         "expected_revision":"r001"}).status_code,403)
        self.client.force_login(self.maint)
        self.assertEqual(self.client.get(BASE).status_code,403)
        self.assertEqual(self.call(BASE,self.task_payload()).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(BASE).status_code,401)
        # Django runs CSRF before view authentication: obtain a fresh valid
        # anonymous token so this assertion isolates the 401 auth boundary.
        self.client.get("/api/v1/auth/csrf")
        self.token=self.client.cookies["csrftoken"].value
        self.assertEqual(self.call(BASE,self.task_payload()).status_code,401)
        self.assertEqual(CatalogItem.objects.filter(type_slug="campaign").count(),1)
        self.assertEqual(CatalogItem.objects.get(public_id=row["id"]).current_revision.number,1)

    def test_publish_requires_challenges_not_bogus_run_evidence(self):
        payload=self.task_payload()
        payload["test_case_ids"]=[]
        row=self.new(payload)
        self.call(BASE+"/"+row["id"]+"/actions/start",{"expected_revision":"r001"})
        self.call(BASE+"/"+row["id"]+"/actions/close",{"expected_revision":"r002"})
        self.assertEqual(self.call(BASE+"/"+row["id"]+"/actions/publish",{
                         "expected_revision":"r003"},user=self.reviewer).status_code,400)
        self.assertEqual(self.client.get(BASE+"/pipeline").json()["columns"]["published"],[])
