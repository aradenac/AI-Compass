"""FUT-16: security, deterministic native tariffs, capacity partition and history."""
import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.test import Client

from .test_opportunities import OpportunityTests
from .models import BudgetPlan, BudgetRevision

API = "/api/v1/planning/budgets"


class BudgetTests(OpportunityTests.__bases__[0]):
    setUpTestData = classmethod(OpportunityTests.setUpTestData.__func__)
    setUp = OpportunityTests.setUp
    send = OpportunityTests.send
    campaign = OpportunityTests.campaign
    session = OpportunityTests.session
    interaction = OpportunityTests.interaction
    result = OpportunityTests.result
    close = OpportunityTests.close
    ready_guide = OpportunityTests.ready_guide
    review = OpportunityTests.review
    publisher = OpportunityTests.publisher
    publish = OpportunityTests.publish
    planner = OpportunityTests.planner
    plan = OpportunityTests.plan
    request = OpportunityTests.request
    priced_published = OpportunityTests.priced_published
    forecast = OpportunityTests.forecast

    def data(self, profile, *, pilot=True):
        return {"profile_id": profile.public_id, "plan": {
            "name": "Synthetic authorized resource request",
            "start_date": "2026-10-11", "period_months": 6,
            "margin_pct": "0", "include_active": False,
            "items": [{"purpose": "pilot", "task_id": self.task.item.public_id,
                       "candidate_id": "fct-synthetic-forecast", "pilot_headcount": 2,
                       "offer_pins": [], "meter_overrides": {}}
                      if pilot else {"purpose": "rollout", "target_id": "dpt-fake"}]}}

    @staticmethod
    def fake_source(rate="1", units="1"):
        offer = SimpleNamespace(public_id="off-synthetic")
        rev = SimpleNamespace(pk=UUID("d5de5cec-2841-44c8-a73e-bf874fb9f523"),
            properties={"component_id":"prv-synthetic", "billing_owner": "Example provider",
                "status":"active", "currency":"EUR", "source":"synthetic tariff",
                "lines":[{"charge_id":"tiered-requests", "family":"tiered",
                    "charge_type":"variable", "meter":"requests", "unit_size":"1",
                    "tiers":[{"up_to":"5","rate":rate},
                             {"up_to":None,"rate":"2"}]},
                    {"charge_id":"seats", "family":"per_seat",
                     "charge_type":"fixed", "rate":"3", "period":"seat_month"}]})
        return ({"root:provider": (SimpleNamespace(public_id="prv-synthetic"),
                                    rev.pk)},
                [("root:provider", offer, rev)],
                {"root:provider": {"requests":units}},
                {"kind":"synthetic_pinned_evidence","revision_id":"source-r001"},
                "measured_fixture", {})

    def test_preview_native_tiers_fixed_seats_history_and_revisions(self):
        _, browser, csrf, population = self.plan(headcount=3, frequency="10")
        payload = self.data(population)
        with patch("config.budget_services._source", return_value=self.fake_source()):
            preview = self.request(browser, csrf, API+"/preview", payload)
            self.assertEqual(preview.status_code, 200, preview.content)
            result = preview.json()
            self.assertTrue(result["ready_for_request"])
            self.assertEqual(result["segments"][0]["estimated_task_occurrences"], "10")
            self.assertEqual(result["quantities"][0]["quantity"], "10")
            # 5 requests at 1, 5 at 2, plus 2 seats * 6 months * 3.
            self.assertEqual(result["amounts_by_native_currency"]["EUR"],
                {"fixed":"36.00", "variable":"15.00", "total":"51.00"})
            response=self.request(browser,csrf,API,payload)
            self.assertEqual(response.status_code,201,response.content)
            doc=response.json()
            self.assertEqual(doc["snapshot"],result)
            self.assertFalse(doc["source_changed"])
            saved_id=doc["id"]
            self.assertEqual(BudgetPlan.objects.count(),1)
            self.assertEqual(BudgetRevision.objects.count(),1)
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    BudgetRevision.objects.filter(budget__public_id=saved_id).update(
                        algorithm="silent_rewrite")
            old=browser.get(API+"/"+saved_id+"/revisions/1").json()
            self.assertEqual(old["snapshot"],result)
            exported=browser.get(API+"/"+saved_id+"/export")
            self.assertEqual(exported.status_code,200)
            self.assertNotIn("hourly_rate",exported.content.decode())
            self.assertNotIn("person_profile_id",exported.content.decode())
        with patch("config.budget_services._source", return_value=self.fake_source(units="2")):
            live=browser.get(API+"/"+saved_id).json()
            self.assertTrue(live["source_changed"])
            self.assertEqual(live["snapshot"],result)
            self.assertNotEqual(live["current"]["quantities"][0]["quantity"],"10")
            stale=self.request(browser,csrf,API+"/"+saved_id,{
                "expected_revision":"r000","plan":payload["plan"]},method="PATCH")
            self.assertEqual(stale.status_code,409)
            version=self.request(browser,csrf,API+"/"+saved_id,{
                "expected_revision":"r001","plan":payload["plan"]},method="PATCH")
            self.assertEqual(version.status_code,200,version.content)
            self.assertEqual(version.json()["revision"],"r002")
            self.assertEqual(browser.get(API+"/"+saved_id+"/revisions/1").json()[
                "snapshot"],result)
            self.assertEqual(len(browser.get(API+"/"+saved_id+"/revisions").json()["revisions"]),2)

    def test_no_invention_bad_inputs_and_permission_boundaries(self):
        _,browser,csrf,population=self.plan()
        args=self.data(population)
        self.assertEqual(Client().get(API).status_code,401)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(API).status_code,403)
        self.assertEqual(self.request(self.client,self.token,API,args).status_code,403)
        self.assertEqual(browser.post(API,json.dumps(args),content_type="application/json").status_code,403)
        self.assertEqual(browser.get(API+"/preview").status_code,405)
        self.assertEqual(browser.get(API+"?unexpected=1").status_code,400)
        self.assertEqual(browser.get(API+"/options").status_code,200)
        self.assertEqual(self.request(browser,csrf,API,args).status_code,400)
        self.assertEqual(BudgetPlan.objects.count(),0)
        bad=json.loads(json.dumps(args))
        bad["plan"]["items"][0]["pilot_headcount"]=0
        self.assertEqual(self.request(browser,csrf,API+"/preview",bad).status_code,400)
        bad=json.loads(json.dumps(args))
        bad["plan"]["items"].append(dict(bad["plan"]["items"][0]))
        self.assertEqual(self.request(browser,csrf,API+"/preview",bad).status_code,400)
        bad=json.loads(json.dumps(args))
        bad["profile_id"]="wlp-does-not-exist"
        self.assertEqual(self.request(browser,csrf,API+"/preview",bad).status_code,400)
        with patch("config.budget_services._source",return_value=self.fake_source()):
            bad=json.loads(json.dumps(args))
            bad["plan"]["items"][0]["meter_overrides"]={"other-owner":{"requests":"1"}}
            # Even with mocked upstream evidence, an unpriced source is not accepted.
            self.assertEqual(self.request(browser,csrf,API+"/preview",bad).status_code,400)

    def test_rollout_active_capacity_disjoint_and_missing_source(self):
        _,browser,csrf,population=self.plan(headcount=3,frequency="10")
        run,_=self.priced_published()
        selected=self.request(browser,csrf,"/api/v1/planning/deployments",{
            "profile_id":population.public_id,"task_id":self.task.item.public_id,
            "kind":"benchmark","candidate_id":run["solution_id"],
            "selection":{"seats":[{"key":"selected-a","available_os":["windows"]}]}})
        self.assertEqual(selected.status_code,201,selected.content)
        target_id=selected.json()["id"]
        data=self.data(population,pilot=False)
        data["plan"]["items"]=[{"purpose":"rollout","target_id":target_id}]
        data["plan"]["period_months"]=12
        data["plan"]["include_active"]=True
        fake=self.fake_source()
        with patch("config.budget_services.deployment_status",return_value={
            "status":"selected","ready_count":2,"activated_count":1,
            "revision_id":"fake-revision"}), patch("config.budget_services._source",
                return_value=fake):
            projection=self.request(browser,csrf,API+"/preview",data)
            self.assertEqual(projection.status_code,200,projection.content)
            result=projection.json()
            self.assertEqual([s["purpose"] for s in result["segments"]],["rollout","active"])
            self.assertEqual([s["headcount"] for s in result["segments"]],[1,1])
            # Both purposes are disjoint, so licenses cover TWO seats, not max(1,1).
            fixed=[c for c in result["charges"] if c["charge_type"]=="fixed"][0]
            self.assertEqual(fixed["seats"],2)
            self.assertEqual(result["quantities"][0]["quantity"],"20")
            self.assertEqual(result["amounts_by_native_currency"]["EUR"]["fixed"],"72.00")

    def test_real_forecast_only_still_cannot_fabricate_provider_units(self):
        _,browser,csrf,population=self.plan(headcount=3,frequency="10")
        self.priced_published()
        forecast=self.forecast()
        data=self.data(population)
        data["plan"]["items"][0]["candidate_id"]=forecast.public_id
        response=self.request(browser,csrf,API+"/preview",data)
        self.assertEqual(response.status_code,200,response.content)
        calculated=response.json()
        self.assertTrue(calculated["gaps"])
        self.assertFalse(calculated["ready_for_request"])
        self.assertTrue(any(x.startswith("unselected_offer:") for x in calculated["gaps"]))
        self.assertEqual(calculated["amounts_by_native_currency"],{})
        self.assertEqual(calculated["segments"][0]["purpose"],"pilot")
        self.assertEqual(calculated["segments"][0]["headcount"],2)
