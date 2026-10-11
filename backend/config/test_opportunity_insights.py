"""FUT-14: source-backed Management Insights, paginated heatmap and frozen provenance."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client

from .test_opportunities import OpportunityTests
from .opportunity_services import create as create_scenario
from .opportunity_insights_services import delta_factors
from .run_lifecycle_services import change as change_run
from .task_services import create_task

ROOT = "/api/v1/planning"


class ManagementInsightsTests(OpportunityTests.__bases__[0]):
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
    config = OpportunityTests.config
    priced_published = OpportunityTests.priced_published
    forecast = OpportunityTests.forecast

    def get(self, client, route, **params):
        from urllib.parse import urlencode
        return client.get(ROOT+route+("?" + urlencode(params) if params else ""))

    def test_empty_planning_and_unauthorized_access_are_fail_closed(self):
        actor, client, token, profile = self.plan()
        for path in ("/heatmap", "/insights", "/insights/explain",
                     "/insights/suggestions"):
            self.assertEqual(self.get(client,path).status_code,400)
            self.assertEqual(self.get(Client(),path,profile_id=profile.public_id).status_code,401)
            self.client.force_login(self.editor)
            self.assertEqual(self.get(self.client,path,profile_id=profile.public_id).status_code,403)
        page = self.get(client,"/heatmap",profile_id=profile.public_id)
        self.assertEqual(page.status_code,200,page.content)
        doc=page.json()
        self.assertEqual(doc["total_columns"],0)
        self.assertEqual(doc["cells"],[])
        self.assertEqual(doc["total_rows"],1)
        self.assertIsNone(doc["chosen_scenario"])
        self.assertEqual(doc["period"],"annual")
        self.assertEqual(self.get(client,"/insights",profile_id=profile.public_id).json()["portfolio"],None)
        self.assertEqual(self.get(client,"/heatmap",profile_id=profile.public_id,
                         period="monthly").status_code,400)
        self.assertEqual(self.get(client,"/heatmap",profile_id=profile.public_id,
                         extra="bad").status_code,400)
        self.assertEqual(self.get(client,"/heatmap",profile_id=profile.public_id,
                         row_size=999).status_code,400)
        self.assertEqual(self.get(client,"/heatmap",profile_id=profile.public_id,
                         row_page="-1").status_code,400)
        self.assertEqual(self.get(client,"/insights",profile_id=profile.public_id,
                         revision="r004").status_code,400)
        self.assertEqual(self.get(client,"/heatmap",profile_id="wlp-no-such").status_code,400)

    def test_authoritative_same_math_candidates_and_provenance_with_no_rate_leaks(self):
        actor,client,token,profile=self.plan(rate="375.75",headcount=3)
        run,_=self.priced_published(metric_time=60,cost=2)
        forecast=self.forecast(minutes=90,cost=3)
        entry=create_scenario(actor,{
            "profile_id":profile.public_id,
            "scenario":self.config("benchmark",run["solution_id"],
                                    forecast.public_id)})
        details=self.get(client,"/opportunities/"+entry.public_id).json()
        values=self.get(client,"/insights",
                        profile_id=profile.public_id,scenario_id=entry.public_id)
        self.assertEqual(values.status_code,200,values.content)
        insights=values.json()
        self.assertEqual(insights["portfolio"]["totals"],details["current"]["totals"])
        self.assertEqual(len(insights["snapshots"]),1)
        self.assertEqual(insights["snapshots"][0]["original_algorithm"],"dap-opportunity-v1")
        self.assertFalse(insights["source_changed_since_snapshot"])
        self.assertNotIn("375.75",json.dumps(insights))
        self.assertNotIn("valuation_eur_per_hour",json.dumps(insights))
        self.assertNotIn("baseline_human_hours",json.dumps(insights))
        self.assertNotIn("linked_user",json.dumps(insights))
        matrix=self.get(client,"/heatmap",profile_id=profile.public_id,
                        scenario_id=entry.public_id).json()
        self.assertEqual(matrix["chosen_scenario"]["totals"],insights["portfolio"]["totals"])
        self.assertEqual(len(matrix["columns"]),2)
        self.assertEqual(len(matrix["cells"]),2)
        selected=next(c for c in matrix["cells"] if c["selected"])
        theoretical=next(c for c in matrix["cells"] if not c["selected"])
        self.assertEqual(selected["candidate_id"],run["solution_id"])
        self.assertEqual(selected["maturity"],"B")
        self.assertEqual(theoretical["maturity"],"F")
        self.assertEqual(selected["intensity_eur"],str(Decimal(
            insights["portfolio"]["totals"]["benchmarked_opportunity_eur"])))
        self.assertNotIn("375.75",json.dumps(matrix))
        detail=self.get(client,"/insights/explain",
                        profile_id=profile.public_id,scenario_id=entry.public_id,
                        task_id=self.task.item.public_id,kind="benchmark",
                        candidate_id=run["solution_id"])
        self.assertEqual(detail.status_code,200,detail.content)
        body=detail.json()
        self.assertEqual(body["summary"]["annual_eur"],
                         insights["portfolio"]["cells"][0]["economic"]["annual_eur"])
        self.assertEqual(body["revision"],"r001")
        self.assertEqual(len(body["branches"]),6)
        self.assertEqual(body["branches"][2]["refs"][0]["revision"],"r002")
        self.assertEqual(body["branches"][4]["factors"]["recorded_cost"],"2")
        self.assertNotIn("375.75",json.dumps(body))
        self.assertNotIn("linked_user",json.dumps(body))
        denied=self.get(client,"/insights/explain",
                        profile_id=profile.public_id,scenario_id=entry.public_id,
                        task_id=self.task.item.public_id,kind="forecast",
                        candidate_id=forecast.public_id)
        self.assertEqual(denied.status_code,400) # Unselected alternative
        sugg=self.get(client,"/insights/suggestions",profile_id=profile.public_id)
        self.assertEqual(sugg.status_code,200,sugg.content)
        self.assertEqual(sugg.json()["total_candidates"],2)
        self.assertEqual(sugg.json()["suggestions"][0]["kind"],"benchmark")
        self.assertTrue(all(x["not_selected"] and not x["deployment_started"]
                            for x in sugg.json()["suggestions"]))
        self.assertNotIn("375.75",json.dumps(sugg.json()))

    def test_as_of_sources_and_delta_after_live_correction_and_withdrawal(self):
        actor,client,token,profile=self.plan(rate="90.00")
        run,reviewer=self.priced_published(metric_time=60)
        scenario=self.config("benchmark",run["solution_id"])
        entry=create_scenario(actor,{"profile_id":profile.public_id,"scenario":scenario})
        old=self.get(client,"/insights",profile_id=profile.public_id,
                     scenario_id=entry.public_id).json()
        old_money=old["portfolio"]["totals"]["positive_modeled_total_eur"]
        change_run(actor=reviewer,identifier=run["id"],expected_revision="r002",
                   action="corrected",reason="Further independently verified labor expenditure",
                   metrics_patch={"interaction_human_minutes":110})
        live=self.get(client,"/insights",profile_id=profile.public_id,
                     scenario_id=entry.public_id).json()
        self.assertTrue(live["source_changed_since_snapshot"])
        self.assertNotEqual(live["portfolio"]["totals"]["positive_modeled_total_eur"],old_money)
        # Explicitly append original as-of second snapshot after changed source.
        revised=self.request(client,token,ROOT+"/opportunities/"+entry.public_id,{
            "expected_revision":"r001","scenario":scenario},method="PATCH")
        self.assertEqual(revised.status_code,200,revised.content)
        history=self.get(client,"/insights",profile_id=profile.public_id,
                         scenario_id=entry.public_id).json()
        self.assertEqual(len(history["snapshots"]),2)
        self.assertEqual(history["snapshots"][0]["total_eur"],old_money)
        self.assertIn("measured_run_revision_or_eligibility_changed",
                      history["snapshots"][1]["possible_change_factors"])
        frozen=self.get(client,"/insights",profile_id=profile.public_id,
                        scenario_id=entry.public_id,revision="r001").json()
        self.assertTrue(frozen["historical"])
        self.assertEqual(frozen["portfolio"]["totals"]["positive_modeled_total_eur"],old_money)
        freeze_matrix=self.get(client,"/heatmap",profile_id=profile.public_id,
                           scenario_id=entry.public_id,revision="r001").json()
        self.assertTrue(freeze_matrix["historical"])
        self.assertEqual(freeze_matrix["cells"][0]["annual_eur"],old_money)
        orig=self.get(client,"/insights/explain",profile_id=profile.public_id,
                     scenario_id=entry.public_id,task_id=self.task.item.public_id,
                     kind="benchmark",candidate_id=run["solution_id"],revision="r001").json()
        self.assertEqual(orig["branches"][2]["refs"][0]["revision"],"r002")
        change_run(actor=reviewer,identifier=run["id"],expected_revision="r003",
            action="withdrawn",reason="Source invalidated by an independent review")
        latest=self.get(client,"/insights",profile_id=profile.public_id,
                        scenario_id=entry.public_id).json()
        self.assertEqual(latest["portfolio"]["totals"]["positive_modeled_total_eur"],"0.00")
        self.assertTrue(latest["source_changed_since_snapshot"])
        mat=self.get(client,"/heatmap",profile_id=profile.public_id,
                     scenario_id=entry.public_id).json()
        self.assertEqual(mat["total_columns"],1)
        self.assertEqual(mat["cells"][0]["status"],"unquantifiable")
        self.assertIsNone(mat["cells"][0]["intensity_eur"])
        self.assertEqual(self.get(client,"/insights",profile_id=profile.public_id,
               scenario_id=entry.public_id,revision="r001").json()[
                   "portfolio"]["totals"]["positive_modeled_total_eur"],old_money)

    def test_bounded_taxonomy_pages_and_selected_population_scope(self):
        actor,client,token,profile=self.plan()
        for i in range(20):
            create_task(actor=self.editor,name="Large grid sample task %02d"%i,
                        parent_id=self.task.item.public_id)
        result=self.get(client,"/heatmap",profile_id=profile.public_id,
                        row_page=0,row_size=8,column_size=8).json()
        self.assertGreater(result["total_rows"],16)
        self.assertEqual(len(result["rows"]),8)
        self.assertEqual(len({r["id"] for r in result["rows"]}),8)
        self.assertTrue(any(r["parent_id"]==self.task.item.public_id for r in result["rows"]))
        second=self.get(client,"/heatmap",profile_id=profile.public_id,
                        row_page=1,row_size=8,column_size=8).json()
        self.assertTrue(set(r["id"] for r in result["rows"]).isdisjoint(
            set(r["id"] for r in second["rows"])))
        self.assertEqual(len(second["rows"]),8)
        self.assertEqual(self.get(client,"/heatmap",profile_id=profile.public_id,
                              row_size=17).status_code,400)

    def test_aggregation_delta_only_claims_observable_possible_change_factors(self):
        before={"totals":{"activated_potential_eur":"0.00",
                "benchmarked_opportunity_eur":"500.00","forecast_opportunity_eur":"0.00"},
                "cells":[],"profile_revision_id":"version-A"}
        after={"totals":{"activated_potential_eur":"0.00",
                "benchmarked_opportunity_eur":"600.00","forecast_opportunity_eur":"0.00"},
               "cells":[],"profile_revision_id":"version-B"}
        factors=delta_factors(before,after,{"choices":[]},{"choices":[]})
        self.assertIn("workload_revision_changed",factors)
        self.assertIn("modeled_slice_values_changed",factors)
        self.assertNotIn("forecast_source_revision_or_eligibility_changed",factors)
