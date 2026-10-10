"""FUT-05: real DB pricing, status, authorization and exact historical campaign pins."""
import copy
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase

from .identity import ensure_roles
from .catalog_services import create_component
from .models import CatalogItem, CampaignPricingPin, SessionPricingPin
from .pricing_services import offer_create, offer_revise, offer_record, pricing_status
from .task_services import create_task
from .test_case_services import create as create_case


BASE="/api/v1/pricing"


class PricingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User=get_user_model()
        cls.writer=User.objects.create_user("fut05-writer",password="test-not-secret")
        cls.writer.groups.add(Group.objects.get(name="contributor"))
        cls.reader=User.objects.create_user("fut05-reader",password="test-not-secret")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=User.objects.create_user("fut05-maint",password="test-not-secret")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.comps={kind:create_component(type_slug=kind,actor=cls.writer,
                   name="FUT05 "+kind,properties={}) for kind in
                   ("model","provider","harness","framework")}
        cls.task=create_task(actor=cls.writer,name="Driver test")
        cls.case=create_case(actor=cls.writer,task_id=cls.task.item.public_id,
                   name="HW driver test",properties={"objective":"exercise","dod":"all pass"})

    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.csrf=self.client.cookies["csrftoken"].value
        self.client.force_login(self.writer)

    def call(self,url,payload,method="POST",csrf=True):
        handler=self.client.post if method=="POST" else self.client.patch
        return handler(url,json.dumps(payload),content_type="application/json",
                       **({"HTTP_X_CSRFTOKEN":self.csrf} if csrf else {}))

    def props(self,kind="model",billing="billing-owner",charge="api-invocation"):
        return {"component_id":self.comps[kind].public_id,"billing_owner":billing,
                "currency":"EUR","source":"https://example.invalid/tariff",
                "checked_on":"2026-10-10","status":"active",
                "effective_from":None,"effective_to":None,
                "lines":[{"charge_id":charge,"family":"token",
                          "charge_type":"variable","meter":"input_tokens",
                          "unit_size":1000000,"rate":"2.500"}]}

    def offer(self,kind="model",billing=None,charge=None,props=None):
        data=props or self.props(kind,
                 billing or kind+"-bill",charge or kind+"-charge")
        response=self.call(BASE+"/offers",{"name":"Vendor commercial alternative",
                                           "properties":data})
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def campaign_payload(self):
        return {"name":"FUT05 price pins", "objective":"Compare work",
                "mode":"solution_centred","component_ids":{
                    k:self.comps[k].public_id for k in ("model","provider","harness")},
                "test_case_ids":[self.case.item.public_id],
                "configuration":{"temperature":0.2},"pricing_selections":[]}

    def selection(self,offer,kind,source_prefix="root"):
        return {"source_key":source_prefix+":"+kind,
                "component_id":self.comps[kind].public_id,
                "offer_id":offer["id"],"offer_revision_id":offer["revision_id"]}

    def test_alternative_offers_fixed_and_variable_and_historical_rate(self):
        props=self.props()
        props["lines"] += [{"charge_id":"licence-month","family":"subscription",
                            "charge_type":"fixed","period":"month","rate":"49.99"}]
        first=self.offer(props=props)
        self.assertTrue(first["readiness"]["complete"])
        self.assertEqual(len(first["readiness"]["required_meters"]),1)
        self.assertEqual(len(first["readiness"]["fixed_commitments"]),1)
        second=self.offer(props={**self.props(), "lines":[{"charge_id":"free-licence",
                  "family":"free","charge_type":"free","rate":"0"}]})
        self.assertNotEqual(first["id"],second["id"])
        self.assertEqual(len(self.client.get(BASE+"/offers?component_id="+self.comps["model"].public_id)
                         .json()["results"]),2)
        changed=copy.deepcopy(props)
        changed["lines"][0]["rate"]="3.10"
        revised=self.call(BASE+"/offers/"+first["id"],
            {"name":"Updated vendor tariff","expected_revision":"r001","properties":changed},
            method="PATCH")
        self.assertEqual(revised.status_code,200,revised.content)
        self.assertEqual(revised.json()["revision"],"r002")
        history=self.client.get(BASE+"/offers/"+first["id"]+"/revisions").json()["revisions"]
        self.assertEqual([v["revision"] for v in history],["r001","r002"])
        self.assertEqual(history[0]["properties"]["lines"][0]["rate"],"2.500")
        self.assertEqual(history[1]["properties"]["lines"][0]["rate"],"3.10")
        self.assertEqual(self.call(BASE+"/offers/"+first["id"],{"name":"Stale",
                         "expected_revision":"r001","properties":changed},
                         method="PATCH").status_code,409)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                from .models import CatalogRevision
                CatalogRevision.objects.filter(pk=first["revision_id"]).update(
                    display_name="illegal mutable overwrite")

    def test_missing_price_invalid_families_credits_and_auth(self):
        incomplete=self.props()
        incomplete["lines"][0]["rate"]=None
        row=self.offer(props=incomplete)
        self.assertFalse(row["readiness"]["complete"])
        self.assertTrue(row["readiness"]["required_meters"])
        for change in [
            {"lines":[{"charge_id":"x","family":"token","charge_type":"variable",
                       "meter":"arbitrary_token_estimate","unit_size":1,"rate":1}]},
            {"lines":[{"charge_id":"x","family":"credit","charge_type":"variable",
                       "meter":"provider_credits","unit_size":1,"rate":"1"}]},
            {"currency":"???"},
            {"lines":[{"charge_id":"x","family":"negotiated","charge_type":"unknown","rate":"1"}]}
        ]:
            payload=self.props()
            payload.update(change)
            response=self.call(BASE+"/offers",{"name":"Bad","properties":payload})
            self.assertEqual(response.status_code,400,response.content)
        credit=self.props()
        credit["lines"]=[{"charge_id":"provider-credits","family":"credit",
                          "charge_type":"variable","meter":"provider_credits",
                          "provider_credit_namespace":"vendor-credit-A",
                          "unit_size":100,"rate":"2.20"}]
        self.assertEqual(self.offer(props=credit)["readiness"]["required_meters"][0]["credit_namespace"],
                         "vendor-credit-A")
        self.assertEqual(self.call(BASE+"/offers",{"name":"No CSRF",
                          "properties":self.props()},csrf=False).status_code,403)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(BASE+"/offers").status_code,200)
        self.assertEqual(self.call(BASE+"/offers",{"name":"Reader cannot",
                         "properties":self.props()}).status_code,403)
        self.client.force_login(self.maint)
        self.assertEqual(self.client.get(BASE+"/offers").status_code,403)

    def test_enterprise_status_separate_from_individual_entitlement(self):
        component=self.comps["harness"]
        url=BASE+"/access/harness/"+component.public_id
        unknown=self.client.get(url).json()
        self.assertEqual(unknown["enterprise_accessibility"],"unknown")
        self.assertEqual(unknown["individual_entitlement"],"not_recorded_here")
        updated=self.call(url,{"expected_revision":"r001",
                         "enterprise_accessibility":"not_accessible"},method="PATCH")
        self.assertEqual(updated.status_code,200,updated.content)
        self.assertEqual(updated.json()["revision"],"r002")
        self.assertTrue(CatalogItem.objects.filter(pk=component.pk).exists())
        self.assertEqual(self.call(url,{"expected_revision":"r001",
                         "enterprise_accessibility":"accessible"},method="PATCH").status_code,409)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(url).json()["enterprise_accessibility"],"not_accessible")
        self.assertEqual(self.call(url,{"expected_revision":"r002",
                         "enterprise_accessibility":"accessible"},method="PATCH").status_code,403)

    def test_exact_campaign_selection_revision_and_no_double_charge(self):
        offers={kind:self.offer(kind) for kind in ("model","provider","harness")}
        body=self.campaign_payload()
        body["pricing_selections"]=[self.selection(offers[k],k)
                                  for k in ("model","provider","harness")]
        created=self.call("/api/v1/campaigns",body)
        self.assertEqual(created.status_code,201,created.content)
        row=created.json()
        self.assertTrue(row["pricing_readiness"]["complete"])
        self.assertEqual(len(row["pricing_readiness"]["required_meters"]),3)
        self.assertEqual(row["pricing_policy"],"offer_revisions_v1")
        self.assertEqual(CampaignPricingPin.objects.filter(
            snapshot__revision__item__public_id=row["id"]).count(),3)
        # Vendor rate revisions do NOT silently repin an existing campaign.
        p=self.props("model",billing="model-bill",charge="model-charge")
        p["lines"][0]["rate"]="100.0"
        revised=offer_revise(actor=self.writer,
                 item=CatalogItem.objects.get(public_id=offers["model"]["id"]),
                 expected_revision="r001",name="Higher price",properties=p)
        updated=self.call("/api/v1/campaigns/"+row["id"],
            {"expected_revision":"r001","notes":"No tariff repin"},method="PATCH")
        self.assertEqual(updated.status_code,200,updated.content)
        next=updated.json()["campaign"]
        self.assertEqual(next["pricing_selections"],row["pricing_selections"])
        self.assertEqual(self.client.get("/api/v1/campaigns/"+row["id"]+"/revisions/1")
                         .json()["pricing_selections"],row["pricing_selections"])
        bad=copy.deepcopy(body)
        bad["pricing_selections"][1]["offer_id"]=offers["model"]["id"]
        self.assertEqual(self.call("/api/v1/campaigns",bad).status_code,400)
        # A model and provider sharing the same invoice line cannot both bill it.
        dup=self.offer("provider",billing="model-bill",charge="model-charge")
        bad=copy.deepcopy(body)
        bad["pricing_selections"][1]=self.selection(dup,"provider")
        self.assertEqual(self.call("/api/v1/campaigns",bad).status_code,400)
        self.assertEqual(self.call("/api/v1/campaigns",{
            **body,"pricing_selections":[{"source_key":"root:model",
             "component_id":self.comps["model"].public_id,"offer_id":offers["model"]["id"],
             "offer_revision_id":"00000000-0000-0000-0000-000000000000"}]
        }).status_code,400)

    def test_unpriced_opted_in_session_blocked_but_legacy_campaign_survives(self):
        data={"name":"Pricing incomplete","objective":"Benchmark Driver",
              "mode":"task_centred","task_id":self.task.item.public_id,
              "test_case_ids":[self.case.item.public_id],"pricing_selections":[]}
        created=self.call("/api/v1/campaigns",data)
        self.assertEqual(created.status_code,201,created.content)
        row=created.json()
        self.assertFalse(row["pricing_readiness"]["complete"])
        self.assertEqual(row["pricing_readiness"]["missing_sources"],[])
        started=self.call("/api/v1/campaigns/"+row["id"]+"/actions/start",
                          {"expected_revision":"r001"})
        self.assertEqual(started.status_code,200,started.content)
        attempt=self.call("/api/v1/campaigns/"+row["id"]+"/sessions",
                         {"test_case_id":self.case.item.public_id})
        self.assertIn(attempt.status_code,(400,409),attempt.content)
        self.assertIn(b"Pricing incomplete",attempt.content)
        legacy=copy.deepcopy(data)
        legacy.pop("pricing_selections")
        legacy["name"]="Historical API still works"
        old=self.call("/api/v1/campaigns",legacy)
        self.assertEqual(old.status_code,201,old.content)
        self.assertEqual(old.json()["pricing_policy"],"legacy_unclassified")

    def test_framework_participant_prices_are_pinned_separately(self):
        """Repeated vendor usage in distinct participant invocations is billed once per invocation."""
        offers={kind:self.offer(kind) for kind in ("model","provider","harness","framework")}
        participants=[{"label":"Agent "+str(i),"role":"Planner" if i==0 else "Reviewer",
                       "configuration_version":"1",
                       "settings":{"temperature":0.1*i},"properties":{},
                       "component_ids":{k:self.comps[k].public_id
                                        for k in ("model","provider","harness")}}
                      for i in range(2)]
        new=self.call("/api/v1/campaigns",{
            "name":"Multi participant pricing","objective":"Compare a workflow",
            "mode":"task_centred","task_id":self.task.item.public_id,
            "test_case_ids":[self.case.item.public_id],
            "framework_id":self.comps["framework"].public_id,
            "participants":participants,"pricing_selections":[]
        })
        self.assertEqual(new.status_code,201,new.content)
        row=new.json()
        self.assertEqual(len(row["participants"]),2)
        self.assertFalse(row["pricing_readiness"]["complete"])
        picks=[self.selection(offers["framework"],"framework")]
        for participant in row["participants"]:
            picks += [self.selection(offers[k],k,participant["id"])
                      for k in ("model","provider","harness")]
        patch=self.call("/api/v1/campaigns/"+row["id"],{
            "expected_revision":row["revision"],"pricing_selections":picks
        },method="PATCH")
        self.assertEqual(patch.status_code,200,patch.content)
        current=patch.json()["campaign"]
        self.assertEqual(current["revision"],"r002")
        self.assertEqual(len(current["pricing_selections"]),7)
        self.assertTrue(current["pricing_readiness"]["complete"])
        self.assertEqual(len(current["pricing_readiness"]["required_meters"]),7)
        self.assertEqual(len(self.client.get(
            "/api/v1/campaigns/"+row["id"]+"/revisions/1"
        ).json()["pricing_selections"]),0)
        # Each participant is a distinct billable invocation of the exact same
        # Provider, with identical vendor charge identity but no cross-invocation dedupe.
        self.assertEqual(CampaignPricingPin.objects.filter(
            snapshot__revision__item__public_id=row["id"]).count(),7)

    def test_task_centred_session_pins_its_own_selected_trio_offers(self):
        """Task-centred Campaign chooses AI components at session time, not plan time."""
        body={"name":"Task-centred with dynamic setups","objective":"Measure options",
              "mode":"task_centred","task_id":self.task.item.public_id,
              "test_case_ids":[self.case.item.public_id],"pricing_selections":[]}
        response=self.call("/api/v1/campaigns",body)
        self.assertEqual(response.status_code,201,response.content)
        row=response.json()
        self.assertFalse(row["pricing_readiness"]["complete"])
        self.assertEqual(self.call("/api/v1/campaigns/"+row["id"]+"/actions/start",
                         {"expected_revision":"r001"}).status_code,200)
        offers={k:self.offer(k) for k in ("model","provider","harness")}
        url="/api/v1/campaigns/"+row["id"]+"/sessions"
        base={"test_case_id":self.case.item.public_id,
              "component_ids":{k:self.comps[k].public_id
                               for k in ("model","provider","harness")}}
        blocked=self.call(url,base)
        self.assertIn(blocked.status_code,(400,409),blocked.content)
        self.assertEqual(SessionPricingPin.objects.count(),0)
        payload=dict(base,pricing_selections=[
            self.selection(offers[k],k) for k in ("model","provider","harness")
        ])
        created=self.call(url,payload)
        self.assertEqual(created.status_code,201,created.content)
        session=created.json()
        self.assertEqual(session["pricing_source"],"session")
        self.assertEqual(len(session["pricing_selections"]),3)
        self.assertEqual(SessionPricingPin.objects.count(),3)
        self.assertEqual(self.client.get("/api/v1/sessions/"+session["id"]).json()[
            "pricing_selections"],session["pricing_selections"])
        # Reprice the underlying vendor without modifying the immutable session.
        newer=self.props("model",billing="model-bill",charge="model-charge")
        newer["lines"][0]["rate"]="98.6"
        offer_revise(actor=self.writer,
                     item=CatalogItem.objects.get(public_id=offers["model"]["id"]),
                     name="New price",expected_revision="r001",properties=newer)
        self.assertEqual(self.client.get("/api/v1/sessions/"+session["id"]).json()[
            "pricing_selections"],session["pricing_selections"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                SessionPricingPin.objects.filter(session__public_id=session["id"]).delete()
