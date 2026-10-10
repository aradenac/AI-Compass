"""PLAT-20 end-to-end theoretical forecast, immutable provenance, governed review and campaign prep."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError,transaction
from django.test import Client,TestCase
from .identity import ensure_roles
from .catalog_services import create_component,revise_component
from .task_services import create_task
from .test_case_services import create as create_case
from .watch_services import create as create_watch,revise as revise_watch
from .models import (CatalogItem,CatalogRevision,ForecastSnapshot,ForecastWatchPin,
                     CampaignForecastOrigin,CampaignForecastWatchPin,MeasuredSolution,
                     BenchmarkRun,CampaignSnapshot)

BASE="/api/v1/forecasts"


class ForecastTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U=get_user_model()
        cls.writer=U.objects.create_user("forecast-author",password="test")
        cls.writer.groups.add(Group.objects.get(name="contributor"))
        cls.reviewer=U.objects.create_user("forecast-reviewer",password="test")
        cls.reviewer.groups.add(Group.objects.get(name="reviewer"))
        cls.reader=U.objects.create_user("forecast-reader",password="test")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=U.objects.create_user("forecast-maint",password="test")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.writer,name="Zephyr KSZ8851SNL driver")
        cls.case=create_case(actor=cls.writer,task_id=cls.task.item.public_id,
            name="SPI controlled test",properties={"objective":"Implement SPI driver",
                                                   "dod":"Twister passes"})
        cls.components={kind:create_component(type_slug=kind,actor=cls.writer,
            name=kind+" test",properties={}) for kind in ("model","provider","harness")}
        cls.source=create_watch("research_source",cls.writer,
            "External technical report",{"claim":"Measured externally, no internal test",
            "citation":"Cited paper","source_type":"research"})
        cls.watch=create_watch("watch_entry",cls.writer,
            "Research-based coding hypothesis",{"hypothesis":"Agent may reduce human work"},
            sources=[{"id":cls.source.public_id}])

    def setUp(self):
        self.browser=Client(enforce_csrf_checks=True)
        self.browser.get("/api/v1/auth/csrf")
        self.browser.force_login(self.writer)
        self.csrf=self.browser.cookies["csrftoken"].value

    def send(self,path,data,method="POST",browser=None,csrf=None):
        browser=browser or self.browser
        handler=browser.post if method=="POST" else browser.patch
        return handler(path,json.dumps(data),content_type="application/json",
                       HTTP_X_CSRFTOKEN=csrf if csrf is not None else self.csrf)

    def login(self,user):
        client=Client(enforce_csrf_checks=True)
        client.get("/api/v1/auth/csrf")
        client.force_login(user)
        return client,client.cookies["csrftoken"].value

    def payload(self):
        return {"name":"Theoretical embedded driver AI candidate",
                "task_id":self.task.item.public_id,
                "component_ids":{k:v.public_id for k,v in self.components.items()},
                "configuration":{"temperature":0.2,"tools":{"shell":True,"unknown":None}},
                "watch_links":[{"id":self.watch.public_id}],
                "properties":{"rationale":"External signals suggest positive performance",
                    "uncertainty":"No internal controlled verification",
                    "confidence":"low",
                    "predicted_metrics":{"quality_score":79,
                        "acceptance_probability":None,"autonomy_score":55,
                        "human_minutes":80,"ai_cost_eur":None,"tokens":None,
                        "unmodeled":{"unknown":None}},
                    "assumptions":{"hourly_rate":60,"future":None},
                    "extra":{"unverified":True}}}

    def create(self):
        r=self.send(BASE,self.payload())
        self.assertEqual(r.status_code,201,r.content)
        return r.json()

    def stage(self,f):
        r=self.send(BASE+"/"+f["id"]+"/actions/stage",{"expected_revision":f["revision"]})
        self.assertEqual(r.status_code,200,r.content)
        return r.json()["record"]

    def act(self,f,action,user=None,**extra):
        client,csrf=self.login(user or self.reviewer)
        return self.send(BASE+"/"+f["id"]+"/actions/"+action,
                         {"expected_revision":f["revision"],**extra},
                         browser=client,csrf=csrf)

    def published_watch(self):
        source,_=revise_watch("research_source",actor=self.reviewer,
             item=self.source,expected_revision="r001",review_action="publish")
        watch,_=revise_watch("watch_entry",actor=self.writer,item=self.watch,
             expected_revision="r001",
             sources=[{"id":source.public_id,"revision":"r002"}])
        for action,revision in (("submit","r002"),("approve","r003"),("publish","r004")):
            watch,_=revise_watch("watch_entry",actor=self.reviewer,
                     item=watch,expected_revision=revision,review_action=action)
        self.assertEqual(watch.current_revision.number,5)
        return watch

    def test_empty_server_registers_forecast_without_real_fixtures(self):
        self.assertEqual(self.browser.get(BASE).json(),{"results":[]})
        self.assertEqual(CatalogItem.objects.filter(type_slug="forecast").count(),0)
        self.assertEqual(MeasuredSolution.objects.count(),0)
        self.assertEqual(BenchmarkRun.objects.count(),0)

    def test_forecast_stage_review_publish_and_immutable_version_pins(self):
        self.published_watch()
        forecast=self.create()
        self.assertTrue(forecast["id"].startswith("fct-"))
        self.assertEqual(forecast["status"],"draft")
        self.assertEqual(forecast["evidence_class"],"theoretical")
        self.assertIsNone(forecast["measured_solution_id"])
        self.assertEqual(forecast["properties"]["predicted_metrics"]["ai_cost_eur"],None)
        self.assertEqual(forecast["watch_links"][0]["revision"],"r005")
        self.assertEqual(forecast["component_revisions"]["model"],
                         str(self.components["model"].current_revision_id))
        stage=self.stage(forecast)
        self.assertEqual(stage["status"],"staged")
        self.assertEqual(self.act(stage,"publish").status_code,400)
        missing_note=self.act(stage,"review")
        self.assertEqual(missing_note.status_code,400)
        reviewed=self.act(stage,"review",review_notes="Uncertain but corroborated source").json()["record"]
        self.assertEqual(reviewed["status"],"reviewed")
        self.assertEqual(reviewed["properties"]["reviewer"],self.reviewer.username)
        published=self.act(reviewed,"publish").json()["record"]
        self.assertEqual(published["status"],"published")
        self.assertEqual(published["revision"],"r004")
        self.assertEqual(published["properties"]["predicted_metrics"],
                         forecast["properties"]["predicted_metrics"])
        self.assertEqual(self.browser.get(BASE+"/"+forecast["id"]+"/revisions/1").json(),
                         forecast)
        other,_=self.login(self.reader)
        self.assertEqual(other.get(BASE).json()["results"][0]["id"],forecast["id"])
        self.assertEqual(other.get(BASE+"/"+forecast["id"]).json()["status"],"published")
        self.assertEqual(other.get(BASE+"/"+forecast["id"]+"/revisions/1").status_code,404)
        self.assertEqual(other.get("/api/v1/catalog/items/"+forecast["id"]).status_code,200)
        self.assertEqual(MeasuredSolution.objects.count(),0)
        # A revised component never retroactively changes the theoretical claim.
        revise_component(item=self.components["model"],type_slug="model",
            actor=self.writer,expected_revision="r001",name="Next model version")
        self.assertEqual(self.browser.get(BASE+"/"+forecast["id"]).json(),published)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ForecastSnapshot.objects.filter(revision_id=forecast["revision_id"]).delete()

    def test_staged_forecast_starts_real_campaign_with_historical_watch_pins(self):
        f=self.create()
        stage=self.stage(f)
        # The candidate remains internal and theoretical; validation does not require publication.
        body={"forecast_revision":stage["revision"],
              "name":"Validate SPI driver projection",
              "test_case_ids":[self.case.item.public_id]}
        response=self.send(BASE+"/"+stage["id"]+"/campaigns",body)
        self.assertEqual(response.status_code,201,response.content)
        camp=response.json()
        self.assertEqual(camp["status"],"planned")
        self.assertEqual(camp["mode"],"task_centred")
        self.assertEqual(camp["task_id"],self.task.item.public_id)
        self.assertEqual(camp["test_case_ids"],[self.case.item.public_id])
        self.assertEqual(camp["forecast_origin"]["revision"],"r002")
        self.assertEqual(camp["forecast_origin"]["revision_id"],stage["revision_id"])
        self.assertEqual(camp["forecast_origin"]["watch_links"][0]["id"],self.watch.public_id)
        self.assertEqual(camp["configuration"]["forecast_candidate"]["component_ids"],
                         stage["component_ids"])
        self.assertEqual(camp["configuration"]["forecast_candidate"]["assumptions"],
                         stage["properties"]["assumptions"])
        self.assertEqual(CampaignForecastOrigin.objects.count(),1)
        self.assertEqual(CampaignForecastWatchPin.objects.count(),1)
        self.assertEqual(BenchmarkRun.objects.count(),0)
        self.assertEqual(MeasuredSolution.objects.count(),0)
        # Revisions of signal/source or Forecast don't change historical linkage.
        changed=self.send(BASE+"/"+f["id"],{"expected_revision":"r002",
            "properties":{"predicted_metrics":{"quality_score":50,"ai_cost_eur":0}},
            "configuration":{"temperature":0.9}},method="PATCH")
        self.assertEqual(changed.status_code,200,changed.content)
        self.assertEqual(changed.json()["record"]["status"],"draft")
        self.assertEqual(self.browser.get(BASE+"/"+f["id"]+"/revisions/2").json(),stage)
        prior=self.browser.get("/api/v1/campaigns/"+camp["id"]).json()
        self.assertEqual(prior["forecast_origin"],camp["forecast_origin"])
        newer=self.send("/api/v1/campaigns/"+camp["id"],{"expected_revision":"r001",
                          "notes":"A more controlled challenge"},method="PATCH")
        self.assertEqual(newer.status_code,200,newer.content)
        actual=newer.json()["campaign"]
        self.assertEqual(actual["forecast_origin"],camp["forecast_origin"])
        self.assertEqual(CampaignForecastOrigin.objects.count(),2)
        self.assertEqual(CampaignForecastWatchPin.objects.count(),2)
        self.assertEqual(self.browser.get("/api/v1/campaigns/"+camp["id"]+
                                         "/revisions/1").json()["forecast_origin"],
                         camp["forecast_origin"])

    def test_publication_requires_visible_immutable_watch_evidence(self):
        f=self.create()
        staged=self.stage(f)
        reviewed=self.act(staged,"review",review_notes="Literature rationale").json()["record"]
        self.assertEqual(self.act(reviewed,"publish").status_code,400)
        self.published_watch()
        self.assertEqual(self.act(reviewed,"publish").status_code,400)
        changed=self.send(BASE+"/"+f["id"],{"expected_revision":"r003",
                        "watch_links":[{"id":self.watch.public_id,"revision":"r005"}]},
                        method="PATCH")
        self.assertEqual(changed.status_code,200,changed.content)
        self.assertEqual(changed.json()["record"]["status"],"draft")
        stage=self.stage(changed.json()["record"])
        reviewed=self.act(stage,"review",review_notes="Now published evidence").json()["record"]
        self.assertEqual(self.act(reviewed,"publish").status_code,200)

    def test_invalid_metrics_links_review_roles_conflicts_and_csrf(self):
        p=self.payload()
        p["properties"]["predicted_metrics"]["quality_score"]=110
        self.assertEqual(self.send(BASE,p).status_code,400)
        p=self.payload()
        p["watch_links"]=[{"id":self.watch.public_id},{"id":self.watch.public_id}]
        self.assertEqual(self.send(BASE,p).status_code,400)
        p=self.payload()
        p["watch_links"]=[{"id":"wat-not-found"}]
        self.assertEqual(self.send(BASE,p).status_code,400)
        original=self.create()
        self.assertEqual(self.send(BASE+"/"+original["id"],{
           "expected_revision":"r999","properties":{"rationale":"stale"}},method="PATCH").status_code,409)
        self.assertEqual(self.send(BASE+"/"+original["id"],{
           "expected_revision":"r001","properties":{"status":"published"}},method="PATCH").status_code,400)
        self.assertEqual(self.send(BASE+"/"+original["id"]+"/campaigns",{
           "forecast_revision":"r001"}).status_code,400)
        no_csrf=Client(enforce_csrf_checks=True);no_csrf.force_login(self.writer)
        self.assertEqual(no_csrf.post(BASE,json.dumps(self.payload()),
                         content_type="application/json").status_code,403)
        reader,token=self.login(self.reader)
        self.assertEqual(reader.get(BASE).json(),{"results":[]})
        self.assertEqual(reader.get(BASE+"/"+original["id"]).status_code,404)
        self.assertEqual(reader.get("/api/v1/catalog/items/"+original["id"]).status_code,404)
        self.assertEqual(self.send(BASE,self.payload(),browser=reader,csrf=token).status_code,403)
        self.assertEqual(self.send(BASE+"/"+original["id"]+"/actions/stage",{
            "expected_revision":"r001"},browser=reader,csrf=token).status_code,403)
        maint,_=self.login(self.maint)
        self.assertEqual(maint.get(BASE).status_code,403)
        self.assertEqual(CatalogItem.objects.filter(type_slug="forecast").count(),1)
