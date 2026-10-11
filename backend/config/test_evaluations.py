"""PLAT-21 real Server Results Explorer and versioned evaluations over immutable Runs."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction,DatabaseError
from django.test import Client,TestCase

from .identity import ensure_roles
from .catalog_services import create_component,revise_component
from .task_services import create_task
from .test_case_services import create as create_case
from .watch_services import create as create_watch
from .models import (BenchmarkRun,CompositeBenchmarkRun,MeasuredSolution,
                     CatalogItem,CatalogRevision,EvaluationSnapshot,
                     EvaluationIndividualRunPin,EvaluationCompositeRunPin,
                     ObjectTypeVersion)

EVALUATIONS="/api/v1/evaluations"
EXPLORER="/api/v1/results/explorer"


class ResultsAndEvaluationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U=get_user_model()
        cls.editor=U.objects.create_user("result-author",password="test")
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.reader=U.objects.create_user("result-reader",password="test")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=U.objects.create_user("result-maint",password="test")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.editor,name="SPI driver Results task")
        cls.other_task=create_task(actor=cls.editor,name="Other Results task")
        cls.case=create_case(actor=cls.editor,task_id=cls.task.item.public_id,
            name="Control the driver",properties={"objective":"SPI working",
                "dod":"Twister regression passed"})
        cls.components={kind:create_component(type_slug=kind,actor=cls.editor,
            name="Results "+kind,properties={}) for kind in ("model","provider","harness")}
        cls.framework=create_component(type_slug="framework",actor=cls.editor,
            name="Results orchestrated workflow",properties={})
        cls.source=create_watch("research_source",cls.editor,"Original external paper",
            {"claim":"Suggests possible driver improvement","source_type":"research"})
        cls.watch=create_watch("watch_entry",cls.editor,"Possible driver improvement",
            {"hypothesis":"Maybe improves driver quality"},
            sources=[{"id":cls.source.public_id}])

    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.token=self.client.cookies["csrftoken"].value
        self.client.force_login(self.editor)

    def call(self,path,data,method="POST",browser=None,token=None):
        browser=browser or self.client
        send=browser.patch if method=="PATCH" else browser.post
        return send(path,json.dumps(data),content_type="application/json",
                    HTTP_X_CSRFTOKEN=token if token is not None else self.token)

    def as_user(self,user):
        browser=Client(enforce_csrf_checks=True)
        browser.get("/api/v1/auth/csrf");browser.force_login(user)
        return browser,browser.cookies["csrftoken"].value

    def measured(self,composite=False):
        payload={"name":"Measured comparison","objective":"Verify driver setup",
                 "mode":"task_centred","task_id":self.task.item.public_id,
                 "test_case_ids":[self.case.item.public_id]}
        if composite:
            payload["framework_id"]=self.framework.public_id
            payload["participants"]=[{"label":label,"role":role,
                "configuration_version":"1","settings":{"nullable":None},
                "properties":{"tool":"git"},
                "component_ids":{k:v.public_id for k,v in self.components.items()}}
                for label,role in (("Planner","design"),("Builder","coding"))]
        campaign=self.call("/api/v1/campaigns",payload)
        self.assertEqual(campaign.status_code,201,campaign.content)
        camp=campaign.json()
        started=self.call("/api/v1/campaigns/"+camp["id"]+"/actions/start",
                          {"expected_revision":"r001"})
        self.assertEqual(started.status_code,200,started.content)
        camp=started.json()["campaign"]
        session={"test_case_id":self.case.item.public_id}
        if composite:
            session["selected_participant_ids"]=[p["id"] for p in camp["participants"]]
        else:
            session.update(component_ids={k:v.public_id for k,v in self.components.items()},
                           settings={"nullable":None},configuration_version="1",
                           properties={"tool":"shell"})
        created=self.call("/api/v1/campaigns/"+camp["id"]+"/sessions",session)
        self.assertEqual(created.status_code,201,created.content)
        sid=created.json()["id"]
        interacted=self.call("/api/v1/sessions/"+sid+"/interactions",{
            "expected_revision":"r001","type":"human_prompt","content":"Create SPI driver",
            "human_minutes":3,"agent_minutes":None,
            "extensions":{"unknown":None}})
        self.assertEqual(interacted.status_code,200,interacted.content)
        close=self.call("/api/v1/sessions/"+sid+"/close",{
            "expected_revision":"r002","outcome":"accepted",
            "quality_score":82,"quality_evaluation":"Regression passed",
            "information_utility_score":None,
            "tokens_count":None,"tokens_multiplier":1,
            "cost_mode":"flat_rate","cost_eur":None,
            "human_review_minutes":None,"human_correction_minutes":None,
            "produced_outputs":"driver.c and Twister output"})
        self.assertEqual(close.status_code,201,close.content)
        return close.json()

    def forecast(self):
        source={"name":"Task speculative candidate","task_id":self.task.item.public_id,
            "component_ids":{k:v.public_id for k,v in self.components.items()},
            "watch_links":[{"id":self.watch.public_id}],
            "configuration":{"new":{"unknown":None}},
            "properties":{"rationale":"External evidence, no actual execution",
                          "uncertainty":"Not tested in-house",
                          "predicted_metrics":{"quality_score":91,"ai_cost_eur":None},
                          "assumptions":{"future":None}}}
        f=self.call("/api/v1/forecasts",source)
        self.assertEqual(f.status_code,201,f.content)
        staged=self.call("/api/v1/forecasts/"+f.json()["id"]+"/actions/stage",
                         {"expected_revision":"r001"})
        self.assertEqual(staged.status_code,200,staged.content)
        return staged.json()["record"]

    def evaluation(self,run_ids):
        response=self.call(EVALUATIONS,{
            "name":"Manual evidence interpretation","run_ids":run_ids,
            "scoring_method_version":1,
            "scoring_config":{"selected_metrics":["quality_score","cost_eur"],
                              "comparison_basis":"descriptive_only",
                              "extensions":{"future":None}},
            "properties":{"assessment":"inconclusive","notes":"Missing EUR costs",
                          "limitations":"Small sample","extensions":{"future":None}}})
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def test_empty_stored_results_and_fresh_registered_scoring_schema(self):
        rows=self.client.get(EXPLORER).json()
        self.assertEqual(rows["matrix"],[])
        self.assertEqual(rows["results"],[])
        self.assertEqual(rows["counts"],{
            "individual_runs":0,"composite_workflows":0,"theoretical_forecasts":0})
        self.assertEqual(self.client.get(EVALUATIONS).json(),{"results":[]})
        self.assertEqual(CatalogItem.objects.filter(type_slug="evaluation").count(),0)
        self.assertTrue(ObjectTypeVersion.objects.filter(
            type_slug="evaluation_scoring_method",version=1).exists())

    def test_task_solution_matrices_and_forecasts_are_distinct_from_composites(self):
        individual=self.measured()
        composite=self.measured(composite=True)
        forecast=self.forecast()
        rows=self.client.get(EXPLORER).json()
        self.assertEqual(rows["counts"],{
            "individual_runs":1,"composite_workflows":1,"theoretical_forecasts":1})
        self.assertEqual(len(rows["matrix"]),1)
        self.assertEqual(len(rows["matrix"][0]["columns"]),3)
        self.assertEqual({r["kind"] for r in rows["results"]},
                         {"individual","composite","forecast"})
        predicted=next(r for r in rows["results"] if r["kind"]=="forecast")
        self.assertEqual(predicted["predicted_metrics"]["quality_score"],91)
        self.assertIsNone(predicted["metrics"]["quality_score"])
        self.assertEqual(predicted["evidence_class"],"theoretical")
        individual_row=next(r for r in rows["results"] if r["kind"]=="individual")
        composite_row=next(r for r in rows["results"] if r["kind"]=="composite")
        self.assertEqual(individual_row["solution_id"],individual["solution_id"])
        self.assertEqual(individual_row["metrics"]["quality_score"],82)
        self.assertIsNone(composite_row["solution_id"])
        self.assertEqual(composite_row["framework_id"],composite["framework_id"])
        self.assertEqual(composite_row["metrics"]["quality_score"],82)
        self.assertIsNone(individual_row["metrics"]["cost_eur"])
        self.assertIn("cost_eur",individual_row["missing_fields"])
        self.assertEqual(individual_row["experimental_method_version"],1)
        self.assertEqual(self.client.get(EXPLORER+"?view=solution").json()["row_axis"],"candidate")
        self.assertEqual(self.client.get(EXPLORER+"?task_id="+self.task.item.public_id)
                         .json()["counts"],rows["counts"])
        filtered=self.client.get(EXPLORER+"?solution_id="+individual["solution_id"]).json()
        self.assertEqual(filtered["counts"]["individual_runs"],1)
        self.assertEqual(filtered["counts"]["composite_workflows"],0)
        self.assertEqual(filtered["counts"]["theoretical_forecasts"],0)
        self.assertEqual(self.client.get(EXPLORER+"?kind=composite").json()
                         ["results"][0]["id"],composite["id"])
        self.assertEqual(self.client.get(EXPLORER+"?kind=theoretical").json()
                         ["results"][0]["id"],forecast["id"])
        self.assertEqual(self.client.get(EXPLORER+"?solution_id="+individual["solution_id"]+
                                         "&kind=composite").status_code,400)

    def test_evaluation_revisions_preserve_original_metrics_and_experimental_method(self):
        individual=self.measured()
        composite=self.measured(composite=True)
        f=self.forecast()
        first=self.evaluation([individual["id"],composite["id"]])
        self.assertEqual(first["revision"],"r001")
        self.assertEqual(first["properties"]["comparability"],"incomplete_metrics")
        self.assertEqual(first["properties"]["missing_fields"],["cost_eur"])
        self.assertEqual(first["scoring_method"]["version"],1)
        self.assertEqual([row["kind"] for row in first["inputs"]],
                         ["individual","composite"])
        self.assertEqual([row["context"]["experimental_method_version"]
                          for row in first["inputs"]],[1,1])
        self.assertEqual(first["inputs"][0]["context"]["test_case_id"],
                         self.case.item.public_id)
        self.assertEqual(first["inputs"][0]["context"]["metrics"]["quality_score"],82)
        self.assertEqual(first["inputs"][1]["context"]["solution_id"],None)
        self.assertEqual(first["scoring_config"]["extensions"],{"future":None})
        update=self.call(EVALUATIONS+"/"+first["id"],{
            "expected_revision":"r001",
            "scoring_config":{"selected_metrics":["quality_score"],
                              "comparison_basis":"descriptive_only"},
            "properties":{"assessment":"supported","notes":"Interpreted quality rubric"}},
            method="PATCH")
        self.assertEqual(update.status_code,200,update.content)
        second=update.json()["record"]
        self.assertEqual(second["revision"],"r002")
        self.assertEqual(second["properties"]["comparability"],"comparable")
        self.assertEqual(second["properties"]["missing_fields"],[])
        self.assertEqual(second["properties"]["assessment"],"supported")
        self.assertEqual(self.client.get(EVALUATIONS+"/"+first["id"]+
                                         "/revisions/1").json(),first)
        self.assertEqual(self.client.get(EVALUATIONS+"/"+first["id"]+
                                         "/revisions").json()["revisions"],
                         [first,second])
        self.assertEqual(self.client.get("/api/v1/runs/"+individual["id"])
                         .json()["metrics"],individual["metrics"])
        self.assertEqual(self.client.get("/api/v1/runs/"+composite["id"])
                         .json()["metrics"],composite["metrics"])
        self.assertEqual(BenchmarkRun.objects.count(),1)
        self.assertEqual(CompositeBenchmarkRun.objects.count(),1)
        self.assertEqual(MeasuredSolution.objects.count(),1)
        self.assertEqual(self.client.get("/api/v1/forecasts/"+f["id"])
                         .json()["properties"]["predicted_metrics"]["quality_score"],91)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EvaluationIndividualRunPin.objects.filter(
                    snapshot__revision_id=first["revision_id"]).delete()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EvaluationSnapshot.objects.filter(revision_id=first["revision_id"]).update(
                    scoring_config={"selected_metrics":[]})

    def test_missing_and_unreliable_inputs_rejected_transactionally(self):
        individual=self.measured()
        baseline={"name":"Malformed",
                  "run_ids":[individual["id"]]}
        for payload in [
            {**baseline,"run_ids":[individual["id"],individual["id"]]},
            {**baseline,"run_ids":["run-nonexistent"]},
            {**baseline,"run_ids":["fct-fake"]},
            {**baseline,"scoring_method_version":999},
            {**baseline,"scoring_config":{"comparison_basis":"arbitrary_weighting"}},
            {**baseline,"scoring_config":{"selected_metrics":["unsupported"]}},
        ]:
            with self.subTest(data=payload):
                self.assertEqual(self.call(EVALUATIONS,payload).status_code,400)
        self.assertEqual(CatalogItem.objects.filter(type_slug="evaluation").count(),0)
        first=self.evaluation([individual["id"]])
        self.assertEqual(self.call(EVALUATIONS+"/"+first["id"],
             {"expected_revision":"r900","properties":{"notes":"Too late"}},"PATCH").status_code,409)
        self.assertEqual(self.call(EVALUATIONS+"/"+first["id"],{
             "expected_revision":"r001","run_ids":["run-gone"]},"PATCH").status_code,400)
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=first["id"]).count(),1)
        for url in (EXPLORER+"?view=bad",EXPLORER+"?task_id=tsk-gone",
                    EXPLORER+"?solution_id=sol-gone",EXPLORER+"?unexpected=1"):
            self.assertEqual(self.client.get(url).status_code,400)

    def test_read_permissions_csrf_and_actual_serialized_provenance(self):
        individual=self.measured()
        record=self.evaluation([individual["id"]])
        browser,token=self.as_user(self.reader)
        self.assertEqual(browser.get(EVALUATIONS+"/"+record["id"]).json(),record)
        self.assertEqual(browser.get(EXPLORER).json()["counts"]["individual_runs"],0)
        self.assertEqual(self.client.get(EXPLORER).json()["counts"]["individual_runs"],1)
        self.assertEqual(self.call(EVALUATIONS,{"name":"Denied","run_ids":[individual["id"]]},
                    browser=browser,token=token).status_code,403)
        no_csrf=Client(enforce_csrf_checks=True)
        no_csrf.force_login(self.editor)
        self.assertEqual(no_csrf.post(EVALUATIONS,json.dumps({
             "name":"No CSRF","run_ids":[individual["id"]]}),
             content_type="application/json").status_code,403)
        outsider,_=self.as_user(self.maint)
        self.assertEqual(outsider.get(EVALUATIONS).status_code,403)
        self.assertEqual(outsider.get(EXPLORER).status_code,403)
        self.assertEqual(Client().get(EXPLORER).status_code,401)
