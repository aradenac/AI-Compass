"""FUT-13: real confidential annual scenarios, published-source gates and immutable economics."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client

from .test_runs import IndividualRunTests
from .test_publication import PublicationTests
from .models import (OpportunityScenario, OpportunitySnapshot, CatalogItem,
                     CatalogRevision, ForecastSnapshot, ObjectTypeVersion,
                     BenchmarkRun)
from .workload_services import create_profile
from .opportunity_services import allocate_slices
from .run_lifecycle_services import change as change_run

BASE="/api/v1/planning/opportunities"


class OpportunityTests(IndividualRunTests.__bases__[0]):
    setUpTestData=classmethod(IndividualRunTests.setUpTestData.__func__)
    setUp=IndividualRunTests.setUp
    send=IndividualRunTests.send
    campaign=IndividualRunTests.campaign
    session=IndividualRunTests.session
    interaction=IndividualRunTests.interaction
    result=IndividualRunTests.result
    close=IndividualRunTests.close
    ready_guide=PublicationTests.ready_guide
    review=PublicationTests.review
    publisher=PublicationTests.publisher
    publish=PublicationTests.publish

    def planner(self):
        actor,_=get_user_model().objects.get_or_create(username="opp-planner")
        actor.groups.add(Group.objects.get(name="deployment-planner"))
        browser=Client(enforce_csrf_checks=True)
        browser.get("/api/v1/auth/csrf")
        browser.force_login(actor)
        return actor,browser,browser.cookies["csrftoken"].value

    def plan(self,rate="80",headcount=3,frequency="10",hours="3"):
        actor,client,token=self.planner()
        p=create_profile(actor=actor,kind="cohort",data={
            "name":"Synthetic cohort", "headcount":headcount,
            "hourly_rate_eur":rate,
            "workloads":[{"task_id":self.task.item.public_id,
                          "annual_occurrences":frequency,
                          "baseline_human_hours":hours}]})
        return actor,client,token,p

    def request(self,browser,token,path,payload,method="POST"):
        return getattr(browser,method.lower())(
            path,json.dumps(payload),content_type="application/json",
            HTTP_X_CSRFTOKEN=token)

    def config(self,kind,identifier,forecast_id=None):
        row={"task_id":self.task.item.public_id,"kind":kind,"candidate_id":identifier}
        if forecast_id:row["forecast_id"]=forecast_id
        return {"name":"Yearly possible value scenario","benchmark_weight":"0.8",
                "choices":[row]}

    def priced_published(self,outcome="accepted",metric_time=60,cost=2):
        self.ready_guide()
        camp=self.campaign()
        sess=self.session(camp)
        self.interaction(sess)
        recorded=self.close(sess,self.result(outcome=outcome,
            cost_mode="amount",cost_eur=cost))
        self.assertEqual(recorded.status_code,201,recorded.content)
        run=recorded.json()
        reviewed=self.review(camp)
        reviewer=self.publisher()
        published=self.publish(reviewed,[run["id"]])
        self.assertEqual(published.status_code,200,published.content)
        corrected=change_run(actor=reviewer,identifier=run["id"],
            expected_revision="r001",action="corrected",
            reason="Verified declared setup and human labor totals",
            metrics_patch={"installation_minutes":0,
                           "interaction_human_minutes":metric_time})
        self.assertEqual(corrected.number,2)
        return run,reviewer

    def forecast(self,*,status="published",minutes=90,cost=3,probability=100):
        from .catalog_ids import new_public_id
        source=BenchmarkRun.objects.select_related("session__individual_setup").first()
        pin=source.session.individual_setup
        item=CatalogItem.objects.create(public_id=new_public_id("fct"),type_slug="forecast")
        schema=ObjectTypeVersion.objects.get(type_slug="forecast",version=1)
        revision=CatalogRevision.objects.create(
            item=item,number=1,schema_version=schema,
            display_name="Synthetic theoretical qualified forecast",
            created_by=self.editor,properties={
                "status":status,"evidence_class":"theoretical",
                "rationale":"Synthetic prior theoretical research",
                "confidence":"medium","uncertainty":"Never an actual Run",
                "predicted_metrics":{"human_minutes":minutes,
                    "ai_cost_eur":cost,"acceptance_probability":probability},
                "assumptions":{},"reviewer":"synthetic-test"})
        item.current_revision=revision;item.save(update_fields=["current_revision"])
        ForecastSnapshot.objects.create(revision=revision,task=self.case.task,
            task_revision=self.task.item.current_revision,
            model=pin.model,model_revision=pin.model_revision,
            provider=pin.provider,provider_revision=pin.provider_revision,
            harness=pin.harness,harness_revision=pin.harness_revision,
            configuration=pin.settings)
        return item

    def test_empty_privacy_csrf_and_one_chosen_task(self):
        actor,reader,token,p=self.plan()
        self.assertEqual(reader.get(BASE).json(),{"results":[]})
        self.assertEqual(reader.get(BASE+"/candidates").json(),{"results":[]})
        value={"profile_id":p.public_id,
            "scenario":self.config("benchmark","sol-not-published")}
        self.assertEqual(self.request(reader,token,BASE+"/preview",value).status_code,200)
        result=self.request(reader,token,BASE+"/preview",value).json()
        self.assertEqual(result["unquantifiable_count"],1)
        self.assertEqual(result["totals"]["positive_modeled_total_eur"],"0.00")
        self.assertEqual(result["cells"][0]["status"],"unquantifiable")
        self.assertEqual(self.request(reader,token,BASE,value).status_code,201)
        self.assertEqual(self.request(reader,token,BASE,value,method="PATCH").status_code,405)
        denied=reader.post(BASE,json.dumps(value),content_type="application/json")
        self.assertEqual(denied.status_code,403)
        self.client.force_login(self.editor)
        for endpoint in (BASE,BASE+"/candidates"):
            self.assertEqual(self.client.get(endpoint).status_code,403)
        self.assertEqual(self.client.get(BASE+"/preview").status_code,405)
        self.assertEqual(self.request(self.client,self.token,BASE+"/preview",value).status_code,403)
        self.client.force_login(self.maint)
        self.assertEqual(self.client.get(BASE).status_code,403)
        self.assertEqual(Client().get(BASE).status_code,401)
        bad=self.config("benchmark","sol-another")
        bad["choices"].append(dict(bad["choices"][0]))
        self.assertEqual(self.request(reader,token,BASE+"/preview",
            {"profile_id":p.public_id,"scenario":bad}).status_code,400)
        self.assertEqual(OpportunityScenario.objects.count(),1)

    def test_live_effective_correction_withdrawal_and_immutable_history(self):
        actor,client,token,p=self.plan()
        run,reviewer=self.priced_published()
        args={"profile_id":p.public_id,
              "scenario":self.config("benchmark",run["solution_id"])}
        response=self.request(client,token,BASE,args)
        self.assertEqual(response.status_code,201,response.content)
        original=response.json()
        cell=original["snapshot"]["cells"][0]
        self.assertEqual(cell["status"],"quantified_annual_potential")
        self.assertEqual(cell["slices"]["activated_potential_eur"],"0.00")
        self.assertGreater(Decimal(cell["slices"]["benchmarked_opportunity_eur"]),0)
        self.assertEqual(original["snapshot"]["totals"]["forecast_opportunity_eur"],"0.00")
        self.assertEqual(cell["measured_reference"]["run_revisions"][0]["revision"],"r002")
        entry=OpportunityScenario.objects.get(public_id=original["id"])
        self.assertEqual(entry.snapshots.count(),1)
        nochange=client.get(BASE+"/"+original["id"])
        self.assertFalse(nochange.json()["source_changed"])
        change_run(actor=reviewer,identifier=run["id"],expected_revision="r002",
            action="corrected",reason="Further audit finds underestimated steering time",
            metrics_patch={"interaction_human_minutes":90})
        current=client.get(BASE+"/"+original["id"])
        self.assertEqual(current.status_code,200,current.content)
        self.assertTrue(current.json()["source_changed"])
        self.assertNotEqual(current.json()["current"]["totals"],
                            current.json()["snapshot"]["totals"])
        self.assertEqual(current.json()["current"]["cells"][0][
            "measured_reference"]["run_revisions"][0]["revision"],"r003")
        self.assertEqual(client.get(BASE+"/"+original["id"]+
            "/revisions/1").json()["snapshot"],original["snapshot"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                OpportunitySnapshot.objects.filter(scenario=entry).update(
                    algorithm="silently_changed")
        change_run(actor=reviewer,identifier=run["id"],expected_revision="r003",
            action="withdrawn",reason="Test outcome invalidated after independent source review")
        withdrawn=client.get(BASE+"/"+original["id"]).json()
        self.assertEqual(withdrawn["current"]["cells"][0]["status"],"unquantifiable")
        self.assertEqual(withdrawn["current"]["totals"]["positive_modeled_total_eur"],"0.00")
        self.assertEqual(withdrawn["snapshot"],original["snapshot"])
        self.assertEqual(client.get(BASE+"/"+original["id"]+"/revisions").json()[
            "revisions"][0]["revision"],"r001")
        self.assertEqual(self.request(client,token,BASE+"/"+original["id"],{
            "expected_revision":"r000","scenario":self.config("benchmark",run["solution_id"])},
            method="PATCH").status_code,409)
        revised=self.request(client,token,BASE+"/"+original["id"],{
            "expected_revision":"r001","scenario":self.config("benchmark",run["solution_id"])},
            method="PATCH")
        self.assertEqual(revised.status_code,200,revised.content)
        self.assertEqual(revised.json()["revision"],"r002")
        self.assertEqual(entry.snapshots.count(),2)

    def test_theoretical_blended_failed_and_missing_sources(self):
        actor,client,token,p=self.plan()
        run,_=self.priced_published()
        forecast=self.forecast()
        theory={"profile_id":p.public_id,
            "scenario":self.config("forecast",forecast.public_id)}
        result=self.request(client,token,BASE+"/preview",theory)
        self.assertEqual(result.status_code,200,result.content)
        data=result.json()
        self.assertEqual(data["cells"][0]["evidence_class"],"theoretical")
        self.assertEqual(data["cells"][0]["status"],"quantified_annual_potential")
        self.assertGreater(Decimal(data["totals"]["forecast_opportunity_eur"]),0)
        self.assertEqual(data["totals"]["benchmarked_opportunity_eur"],"0.00")
        blended=self.request(client,token,BASE+"/preview",{
            "profile_id":p.public_id,"scenario":self.config("benchmark",
                run["solution_id"],forecast.public_id)})
        self.assertEqual(blended.status_code,200,blended.content)
        b=blended.json()["cells"][0]
        self.assertTrue(b["blended"])
        self.assertIsNotNone(b["measured_economics"])
        self.assertIsNotNone(b["theoretical_economics"])
        self.assertEqual(b["slices"]["forecast_opportunity_eur"],"0.00")
        self.assertIsNone(b["slices"].get("unknown"))
        old=forecast.current_revision
        newer=CatalogRevision.objects.create(item=forecast,number=2,
            schema_version=old.schema_version,display_name=old.display_name,
            properties={**old.properties,"status":"draft"},created_by=self.editor)
        forecast.current_revision=newer;forecast.save(update_fields=["current_revision"])
        self.assertEqual(self.request(client,token,BASE+"/preview",theory).json()[
            "cells"][0]["status"],"unquantifiable")
        negative=self.request(client,token,BASE+"/preview",{
            "profile_id":p.public_id,"scenario":self.config("benchmark","sol-not-existent")})
        self.assertEqual(negative.json()["cells"][0]["status"],"unquantifiable")
        norate=create_profile(actor=actor,kind="person",data={
            "name":"Missing rate", "workloads":[{
                "task_id":self.task.item.public_id,
                "annual_occurrences":"5","baseline_human_hours":"3"}]})
        missing=self.request(client,token,BASE+"/preview",{
            "profile_id":norate.public_id,
            "scenario":self.config("benchmark",run["solution_id"])}).json()
        self.assertIn("labor_rate_unknown",missing["cells"][0]["reasons"])

    def test_partial_activation_mathematical_partition_without_fake_provisioning(self):
        six=allocate_slices(Decimal("100"),Decimal("20"),10,6,"measured")
        self.assertEqual(six["activated_potential_eur"],"12000.00")
        self.assertEqual(six["benchmarked_opportunity_eur"],"8000.00")
        self.assertEqual(six["forecast_opportunity_eur"],"0.00")
        theory=allocate_slices(Decimal("100"),Decimal("20"),10,6,"theoretical")
        self.assertEqual(theory["activated_potential_eur"],"12000.00")
        self.assertEqual(theory["forecast_opportunity_eur"],"8000.00")
        self.assertEqual(sum(Decimal(six[k]) for k in (
            "activated_potential_eur","benchmarked_opportunity_eur",
            "forecast_opportunity_eur")),Decimal("20000"))
