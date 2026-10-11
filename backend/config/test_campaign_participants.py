"""PLAT-13: complete Framework trios, durable identities, revision lineage and RBAC."""
import json
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase

from .catalog_services import create_component, revise_component
from .identity import ensure_roles
from .models import (CampaignParticipantIdentity, CampaignParticipantPin, CampaignSnapshot,
                     CatalogItem, CatalogRevision, ObjectTypeVersion)
from .task_services import create_task
from .test_case_services import create as create_test_case

BASE="/api/v1/campaigns"


class FrameworkParticipantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User=get_user_model()
        cls.writer=User.objects.create_user("participant-writer",password="safe-password-for-tests")
        cls.writer.groups.add(Group.objects.get(name="contributor"))
        cls.reader=User.objects.create_user("participant-reader",password="safe-password-for-tests")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=User.objects.create_user("participant-maintainer",password="safe-password-for-tests")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.writer,name="Embedded driver")
        cls.case=create_test_case(actor=cls.writer,task_id=cls.task.item.public_id,
             name="TC1",properties={"objective":"Implement driver","dod":"Build succeeds"})
        cls.framework=create_component(type_slug="framework",actor=cls.writer,
            name="Spec Kit",properties={"process":"Define, plan, implement"})
        cls.second_framework=create_component(type_slug="framework",actor=cls.writer,
            name="BMAD",properties={"process":"Multi agent methodology"})
        cls.catalog={}
        for kind in ("model","provider","harness"):
            cls.catalog[kind]=[create_component(type_slug=kind,actor=cls.writer,
                name=kind+" "+str(n),properties={}) for n in range(3)]

    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.csrf=self.client.cookies["csrftoken"].value
        self.client.force_login(self.writer)

    def send(self,path,payload,method="POST",csrf=True):
        func=self.client.post if method=="POST" else self.client.patch
        return func(path,json.dumps(payload),content_type="application/json",
            **({"HTTP_X_CSRFTOKEN":self.csrf} if csrf else {}))

    def trio(self,n,label=None,role=None):
        return {"label":label or "Participant "+str(n),
                "role":role or ["Planner","Implementer","Reviewer"][n],
                "configuration_version":str(n+1)+".1",
                "settings":{"temperature":n/10,"future":{"preserve":[None,n]}},
                "properties":{"access":n!=2,"tools":["shell","git"],
                              "extensions":{"nullable":None}},
                "component_ids":{kind:self.catalog[kind][n].public_id
                                 for kind in ("model","provider","harness")}}

    def payload(self,mode="task_centred"):
        p={"name":"Framework benchmark","objective":"Reproducible participant comparison",
           "mode":mode,"framework_id":self.framework.public_id,
           "test_case_ids":[self.case.item.public_id],
           "participants":[self.trio(i) for i in range(3)]}
        if mode=="task_centred":p["task_id"]=self.task.item.public_id
        return p

    def new(self,payload=None):
        response=self.send(BASE,payload if payload is not None else self.payload())
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def test_create_three_save_reopen_reorder_modify_remove_and_preserve_history(self):
        initial=self.new()
        self.assertTrue(initial["framework_id"].startswith("frm-"))
        self.assertEqual(initial["framework_revision_id"],str(self.framework.current_revision_id))
        self.assertEqual(initial["component_ids"],{})
        self.assertEqual(initial["status"],"planned")
        self.assertEqual(len(initial["participants"]),3)
        ids=[p["id"] for p in initial["participants"]]
        self.assertEqual(len(set(ids)),3)
        self.assertTrue(all(i.startswith("ptp-") for i in ids))
        self.assertEqual([p["position"] for p in initial["participants"]],[0,1,2])
        self.assertEqual([p["role"] for p in initial["participants"]],["Planner","Implementer","Reviewer"])
        self.assertEqual(initial["participants"][1]["settings"]["future"],{"preserve":[None,1]})
        other=Client();other.force_login(self.writer)
        cross_browser=other.get(BASE+"/"+initial["id"])
        self.assertEqual(cross_browser.status_code,200)
        self.assertEqual([p["id"] for p in cross_browser.json()["participants"]],ids)

        # Updating the Model/Framework catalog does not rebind a historical participant.
        before=deepcopy(initial["participants"])
        model=self.catalog["model"][1]
        revise_component(item=model,type_slug="model",actor=self.writer,
                         expected_revision="r001",name="New model release")
        revise_component(item=self.framework,type_slug="framework",actor=self.writer,
                         expected_revision="r001",name="Updated Spec Kit")
        # The service obtains a separate select_for_update ORM instance.
        model.refresh_from_db()
        self.framework.refresh_from_db()
        untouched=self.send(BASE+"/"+initial["id"],{
            "expected_revision":"r001","notes":"Only notes changed"},method="PATCH")
        self.assertEqual(untouched.status_code,200,untouched.content)
        current=untouched.json()["campaign"]
        self.assertEqual(current["framework_revision_id"],initial["framework_revision_id"])
        self.assertEqual(current["participants"],before)

        # An explicit replacement list can reorder and edit one, remove another,
        # add a new identity, and preserve old pinned component versions.
        changed=[deepcopy(current["participants"][2]),deepcopy(current["participants"][1])]
        for p in changed:
            p.pop("uuid");p.pop("position");p.pop("component_revisions")
        changed[0]["label"]="Lead reviewer"
        changed[1]["settings"]["temperature"]=0.42
        changed.append(self.trio(0,label="New integrator",role="Integrator"))
        update=self.send(BASE+"/"+initial["id"],{
             "expected_revision":"r002","participants":changed},method="PATCH")
        self.assertEqual(update.status_code,200,update.content)
        fresh=update.json()["campaign"]["participants"]
        self.assertEqual([x["id"] for x in fresh[:2]],[ids[2],ids[1]])
        self.assertNotIn(ids[0],[x["id"] for x in fresh])
        self.assertEqual(len({x["id"] for x in fresh}),3)
        self.assertEqual(fresh[0]["label"],"Lead reviewer")
        self.assertEqual(fresh[1]["settings"]["temperature"],0.42)
        self.assertEqual(fresh[1]["component_revisions"],before[1]["component_revisions"])
        self.assertEqual(CampaignParticipantIdentity.objects.filter(
                         campaign__public_id=initial["id"]).count(),4)
        self.assertEqual(CampaignParticipantPin.objects.filter(
                         snapshot__revision__item__public_id=initial["id"]).count(),9)
        original=other.get(BASE+"/"+initial["id"]+"/revisions/1").json()
        self.assertEqual(original["participants"],before)
        self.assertEqual(other.get(BASE+"/"+initial["id"]+"/revisions/2").json()["participants"],before)

        # Deliberate version repin changes current but never prior revisions.
        payload=[{"id":p["id"],"label":p["label"],"role":p["role"],
                  "configuration_version":p["configuration_version"],
                  "settings":p["settings"],"properties":p["properties"],
                  "component_ids":p["component_ids"]} for p in fresh]
        repinned=self.send(BASE+"/"+initial["id"],{"expected_revision":"r003",
                     "participants":payload,"repin":True},method="PATCH")
        self.assertEqual(repinned.status_code,200,repinned.content)
        latest=repinned.json()["campaign"]
        self.assertEqual(latest["participants"][1]["component_revisions"]["model"],
                         str(model.current_revision_id))
        self.assertEqual(other.get(BASE+"/"+initial["id"]+"/revisions/3").json()
                         ["participants"][1]["component_revisions"],
                         fresh[1]["component_revisions"])
        self.assertEqual(latest["framework_revision_id"],str(self.framework.current_revision_id))

    def test_solution_centred_framework_requires_participants_not_a_fixed_trio(self):
        framework=self.new(self.payload("solution_centred"))
        self.assertEqual(framework["mode"],"solution_centred")
        self.assertEqual(framework["component_ids"],{})
        self.assertIsNone(framework["task_id"])
        self.assertEqual(len(framework["participants"]),3)
        # Legacy non-framework single-trio campaign remains supported.
        plain={"name":"Single solution","objective":"Try one configuration",
               "mode":"solution_centred","test_case_ids":[self.case.item.public_id],
               "component_ids":{kind:self.catalog[kind][0].public_id
                                for kind in ("model","provider","harness")}}
        simple=self.new(plain)
        self.assertEqual(simple["framework_id"],None)
        self.assertEqual(len(simple["component_ids"]),3)
        self.assertEqual(simple["participants"],[])
        # Turning legacy solution into Framework keeps old revision and eliminates
        # obsolete fixed trios in the newly committed revision.
        modified=self.send(BASE+"/"+simple["id"],{
            "expected_revision":"r001","framework_id":self.framework.public_id,
            "participants":[self.trio(0)]},method="PATCH")
        self.assertEqual(modified.status_code,200,modified.content)
        new=modified.json()["campaign"]
        self.assertEqual(new["component_ids"],{})
        self.assertEqual(len(new["participants"]),1)
        self.assertEqual(self.client.get(BASE+"/"+simple["id"]+"/revisions/1").json()
                         ["component_ids"],plain["component_ids"])

    def test_invalid_trios_wrong_type_foreign_id_duplicate_identity_and_atomic_rollback(self):
        baseline=self.payload()
        invalids=[
            dict(baseline,framework_id="frm-unknown"),
            dict(baseline,framework_id=self.catalog["model"][0].public_id),
            dict(baseline,participants=[]),
            dict(baseline,participants=[dict(self.trio(0),component_ids={
                "model":self.catalog["model"][0].public_id,"provider":self.catalog["provider"][0].public_id})]),
            dict(baseline,participants=[dict(self.trio(0),component_ids={
                "model":self.catalog["harness"][0].public_id,
                "provider":self.catalog["provider"][0].public_id,"harness":self.catalog["harness"][0].public_id})]),
            dict(baseline,participants=[dict(self.trio(0),role="")]),
            dict(baseline,participants=[dict(self.trio(0),settings=[])]),
            dict(baseline,participants=[dict(self.trio(0),unexpected="reject")]),
            dict(baseline,participants=[dict(self.trio(0),configuration_version="")]),
            dict(baseline,framework_id=None),
        ]
        for bad in invalids:
            with self.subTest(case=bad):
                self.assertEqual(self.send(BASE,bad).status_code,400)
        self.assertEqual(CatalogItem.objects.filter(type_slug="campaign").count(),0)
        self.assertEqual(CampaignParticipantIdentity.objects.count(),0)
        original=self.new()
        outsider=self.new(dict(self.payload(),name="Other campaign"))
        first=original["participants"][0]
        intruder=deepcopy(outsider["participants"][0])
        for p in (intruder,):
            p.pop("uuid");p.pop("position");p.pop("component_revisions")
        r=self.send(BASE+"/"+original["id"],{"expected_revision":"r001",
                  "participants":[intruder]},method="PATCH")
        self.assertEqual(r.status_code,400,r.content)
        duplicated={"id":first["id"],"label":"Duplicate","role":"Planner",
                    "configuration_version":"1","component_ids":first["component_ids"]}
        self.assertEqual(self.send(BASE+"/"+original["id"],{"expected_revision":"r001",
                         "participants":[duplicated,duplicated]},method="PATCH").status_code,400)
        self.assertEqual(self.send(BASE+"/"+original["id"],{"expected_revision":"r000",
                         "participants":[self.trio(1)]},method="PATCH").status_code,409)
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=original["id"]).count(),1)

    def test_framework_switch_removal_and_state_carry_forward(self):
        initial=self.new()
        self.assertEqual(self.send(BASE+"/"+initial["id"],{"expected_revision":"r001",
                         "framework_id":self.second_framework.public_id},method="PATCH").status_code,400)
        new=self.send(BASE+"/"+initial["id"],{"expected_revision":"r001",
                         "framework_id":self.second_framework.public_id,
                         "participants":[self.trio(1)]},method="PATCH")
        self.assertEqual(new.status_code,200,new.content)
        cur=new.json()["campaign"]
        self.assertNotIn(cur["participants"][0]["id"],
                         [p["id"] for p in initial["participants"]])
        self.assertEqual(cur["framework_id"],self.second_framework.public_id)
        self.assertEqual(self.client.get(BASE+"/"+initial["id"]+"/revisions/1")
                         .json()["framework_id"],self.framework.public_id)
        # Explicitly remove the framework; the historical participant identities persist.
        unset=self.send(BASE+"/"+initial["id"],{"expected_revision":"r002",
                "framework_id":None,"participants":[]},method="PATCH")
        self.assertEqual(unset.status_code,200,unset.content)
        self.assertIsNone(unset.json()["campaign"]["framework_id"])
        self.assertEqual(unset.json()["campaign"]["participants"],[])
        self.assertEqual(CampaignParticipantIdentity.objects.filter(
                         campaign__public_id=initial["id"]).count(),4)
        started=self.send(BASE+"/"+initial["id"]+"/actions/start",
                          {"expected_revision":"r003"}).json()["campaign"]
        self.assertIsNone(started["framework_id"])
        self.assertEqual(started["revision"],"r004")
        # A separate framework campaign retains all participant pins across status changes.
        first=self.new()
        transitioned=self.send(BASE+"/"+first["id"]+"/actions/start",
                        {"expected_revision":"r001"}).json()["campaign"]
        self.assertEqual(transitioned["participants"],first["participants"])
        self.assertEqual(transitioned["framework_revision_id"],first["framework_revision_id"])

    def test_database_guards_and_access_controls(self):
        created=self.new()
        pin=CampaignParticipantPin.objects.filter(snapshot__revision__item__public_id=created["id"]).first()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CampaignParticipantPin.objects.filter(pk=pin.pk).update(label="Rewrite")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CampaignParticipantIdentity.objects.filter(pk=pin.participant_id).delete()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CampaignParticipantPin.objects.create(
                    snapshot=pin.snapshot,participant=pin.participant,position=44,
                    label="Wrong",role="Planner",configuration_version="1",
                    settings={},properties={},model=pin.provider,
                    model_revision=pin.provider_revision,
                    provider=pin.provider,provider_revision=pin.provider_revision,
                    harness=pin.harness,harness_revision=pin.harness_revision)
        self.assertEqual(self.send(BASE+"/"+created["id"],{
            "expected_revision":"r001","participants":[self.trio(0)]},method="PATCH",csrf=False).status_code,403)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(BASE+"/"+created["id"]).status_code,404)
        self.assertEqual(self.send(BASE+"/"+created["id"],{
            "expected_revision":"r001","participants":[self.trio(0)]},method="PATCH").status_code,403)
        self.client.force_login(self.maint)
        self.assertEqual(self.client.get(BASE+"/"+created["id"]).status_code,403)
        self.assertEqual(self.send(BASE,self.payload()).status_code,403)
