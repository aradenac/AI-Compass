"""FUT-09: end-to-end price-derived Run costs and interrupted metering.

All records are disposable real PostgreSQL test fixtures; no provider API, no
shared credit wallet, no fabricated observed usage or published results.
"""
import copy
import json
import tempfile
from pathlib import Path
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from .test_pricing import PricingTests
from .pricing_services import offer_revise
from .models import CatalogItem, BenchmarkRun, CompositeBenchmarkRun, SessionCheckpointEvidence
from .run_cost_services import _tiers, quote, MissingMeter, InvalidMeter


class TariffRunTests(PricingTests):
    def setUp(self):
        super().setUp()
        # All bytes uploaded by this transactional test database must remain
        # physically isolated. Otherwise rollback drops their EvidenceBlob
        # rows but leaves orphan files in the platform's real evidence volume,
        # which the full-archive verifier correctly rejects.
        temporary=tempfile.TemporaryDirectory(prefix="aic-tariff-evidence-")
        self.addCleanup(temporary.cleanup)
        settings_override=override_settings(EVIDENCE_STORE_ROOT=Path(temporary.name))
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def chosen(self):
        model=self.props("model",billing="input-gateway",charge="input")
        model["lines"]=[
            {"charge_id":"in","family":"token","charge_type":"variable",
             "meter":"input_tokens","unit_size":1000000,"rate":"2.0"},
            {"charge_id":"out","family":"token","charge_type":"variable",
             "meter":"output_tokens","unit_size":1000000,"rate":"3.0"},
            {"charge_id":"calls","family":"tiered","charge_type":"variable",
             "meter":"requests","unit_size":1,
             "tiers":[{"up_to":10,"rate":"0.1"},{"up_to":None,"rate":"0.2"}]}
        ]
        provider=self.props("provider",billing="gateway-free",charge="free")
        provider["lines"]=[{"charge_id":"free","family":"free","charge_type":"free",
                            "rate":"0"}]
        harness=self.props("harness",billing="license",charge="seat")
        harness["lines"]=[{"charge_id":"seat","family":"per_seat","charge_type":"fixed",
                           "period":"seat_month","rate":"49.99"}]
        props={"model":model,"provider":provider,"harness":harness}
        offers={k:self.offer(k,props=v) for k,v in props.items()}
        return props,offers

    def prepared(self):
        original,offers=self.chosen()
        campaign=self.campaign_payload()
        campaign["pricing_selections"]=[self.selection(offers[k],k)
                                         for k in ("model","provider","harness")]
        created=self.call("/api/v1/campaigns",campaign)
        self.assertEqual(created.status_code,201,created.content)
        row=created.json()
        path="/api/v1/campaigns/"+row["id"]
        started=self.call(path+"/actions/start",{"expected_revision":"r001"})
        self.assertEqual(started.status_code,200,started.content)
        ses=self.call(path+"/sessions",{"test_case_id":self.case.item.public_id})
        self.assertEqual(ses.status_code,201,ses.content)
        return ses.json(),original,offers

    def interaction(self,session):
        response=self.call("/api/v1/sessions/"+session["id"]+"/interactions",
                           {"expected_revision":session["revision"],
                            "type":"human_prompt","content":"Run driver and regression",
                            "human_minutes":3,"agent_minutes":6})
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def results(self):
        return {"outcome":"failed","quality_score":29,"quality_evaluation":"Compilation failed",
                "information_utility_score":55,"information_utility_evaluation":"Useful negative evidence",
                "tokens_count":None,"tokens_multiplier":1,
                "produced_outputs":"Compiler diagnostic and failed Twister XML",
                "human_review_minutes":2,"human_correction_minutes":None,
                "notes":"Retained negative result, not an accepted solution"}

    def test_metering_pending_stable_negative_run_and_original_price(self):
        ses,props,offers=self.prepared()
        self.assertEqual(ses["pricing_source"],"campaign")
        self.assertTrue(ses["metering"]["schema"]["complete"])
        self.assertEqual({x["meter"] for x in ses["metering"]["schema"]["required_meters"]},
                         {"input_tokens","output_tokens","requests"})
        self.assertEqual(len(ses["metering"]["schema"]["fixed_commitments"]),1)
        self.assertFalse(ses["metering"]["ready"])
        changed=self.interaction(ses)
        base="/api/v1/sessions/"+ses["id"]
        partial=self.call(base+"/metering",{"expected_revision":changed["revision"],
            "consumption":{"root:model":{"input_tokens":"1000000",
                                          "requests":"15"}}},method="PATCH")
        self.assertEqual(partial.status_code,200,partial.content)
        self.assertFalse(partial.json()["metering"]["ready"])
        self.assertIn("output_tokens",partial.json()["metering"]["missing"][0])
        upload=self.client.post("/api/v1/catalog/items/"+ses["campaign_id"]+
            "/evidence/upload",{
                "file":SimpleUploadedFile("compile-output.txt",
                           b"error: driver compilation failed\\n",content_type="text/plain"),
                "revision":ses["campaign_revision"],"source":"experiment:test-case",
                "provenance":json.dumps({"stage":"pending results"})
            },HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(upload.status_code,201,upload.content)
        eid=upload.json()["id"]
        draft=self.call(base+"/results",{"expected_revision":partial.json()["revision"],
                                        **self.results(),"evidence_link_ids":[eid]},
                        method="PATCH")
        self.assertEqual(draft.status_code,200,draft.content)
        self.assertEqual(draft.json()["state"]["results_draft"]["outcome"],"failed")
        self.assertTrue(SessionCheckpointEvidence.objects.filter(
            checkpoint__session__public_id=ses["id"],checkpoint__number=4,
            evidence_id=eid).exists())
        incomplete=self.call(base+"/close",{"expected_revision":draft.json()["revision"]})
        self.assertEqual(incomplete.status_code,409,incomplete.content)
        self.assertEqual(BenchmarkRun.objects.count(),0)
        unchanged=self.client.get(base).json()
        self.assertEqual(unchanged["state"]["results_draft"]["produced_outputs"],
                         self.results()["produced_outputs"])
        self.assertEqual(unchanged["state"]["metering"]["root:model"]["input_tokens"],"1000000")
        finished=self.call(base+"/metering",{
            "expected_revision":unchanged["revision"],
            "consumption":{"root:model":{"output_tokens":2000000}}},method="PATCH")
        self.assertEqual(finished.status_code,200,finished.content)
        self.assertTrue(finished.json()["metering"]["ready"])
        quote_data=finished.json()["metering"]["quote"]
        self.assertEqual(quote_data["variable_reference_by_currency"]["EUR"],"10.0")
        self.assertEqual(len(quote_data["variable_charges"]),3)
        self.assertEqual(quote_data["fixed_commitments"][0]["rate"],"49.99")
        closed=self.call(base+"/close",{"expected_revision":finished.json()["revision"]})
        self.assertEqual(closed.status_code,201,closed.content)
        run=closed.json()
        self.assertEqual(run["outcome"],"failed")
        self.assertEqual(run["metrics"]["cost_mode"],"amount")
        self.assertEqual(run["metrics"]["cost_eur"],10.0)
        self.assertEqual(run["metrics"]["reference_cost"],quote_data)
        self.assertIn(eid,[x["id"] for x in run["evidence"]])
        self.assertTrue(run["provenance"]["setup_composition"]["missing_coverage"])
        self.assertEqual(run["provenance"]["test_case_revision_id"],
                         ses["test_case_revision_id"])
        self.assertEqual(self.call(base+"/close",{
            "expected_revision":finished.json()["revision"]}).status_code,409)
        # Vendor changes cannot rerate the original completed Run or original Session.
        new=copy.deepcopy(props["model"])
        new["lines"][0]["rate"]="999"
        offer_revise(actor=self.writer,item=CatalogItem.objects.get(
            public_id=offers["model"]["id"]),expected_revision="r001",
            name="Updated price",properties=new)
        self.assertEqual(self.client.get("/api/v1/runs/"+run["id"]).json(),run)

    def test_unknown_not_zero_manual_override_and_auth(self):
        ses,_,_=self.prepared()
        path="/api/v1/sessions/"+ses["id"]
        denied=self.call(path+"/metering",{"expected_revision":"r001",
            "consumption":{"root:model":{"output_tokens":0}}},method="PATCH",csrf=False)
        self.assertEqual(denied.status_code,403)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.call(path+"/metering",{"expected_revision":"r001",
            "consumption":{"root:model":{"output_tokens":0}}},method="PATCH").status_code,403)
        self.client.force_login(self.writer)
        zero=self.call(path+"/metering",{"expected_revision":"r001",
            "consumption":{"root:model":{"output_tokens":0}}},method="PATCH")
        self.assertEqual(zero.status_code,200,zero.content)
        self.assertFalse(zero.json()["metering"]["ready"])
        self.assertEqual(zero.json()["state"]["metering"]["root:model"]["output_tokens"],"0")
        self.assertEqual(self.call(path+"/metering",{"expected_revision":"r001",
            "consumption":{}},method="PATCH").status_code,409)
        wrong=self.call(path+"/metering",{"expected_revision":"r002",
            "consumption":{"root:model":{"gpu_hours":"17"}}},method="PATCH")
        self.assertEqual(wrong.status_code,400)
        self.interaction(zero.json())
        blocked=self.call(path+"/close",{"expected_revision":"r003",
            **self.results(),"cost_mode":"amount","cost_eur":0.0})
        self.assertEqual(blocked.status_code,400)
        self.assertEqual(BenchmarkRun.objects.count(),0)

    def test_tier_math_and_credit_namespace_without_pooled_balances(self):
        tiers={"unit_size":"10","tiers":[{"up_to":"100","rate":"1.5"},
                                          {"up_to":None,"rate":"0.5"}]}
        self.assertEqual(_tiers(Decimal("150"),tiers),Decimal("17.5"))
        self.assertEqual(_tiers(Decimal("0"),tiers),Decimal("0"))
        with self.assertRaises(MissingMeter):
            _tiers(Decimal("101"),{"unit_size":1,"tiers":[{"up_to":100,"rate":1}]})
        with self.assertRaises(InvalidMeter):
            _tiers(Decimal("1"),{"unit_size":0,"tiers":[{"up_to":None,"rate":1}]})

    def test_framework_composite_sources_and_no_individual_attribution(self):
        offers={k:self.offer(k) for k in ("model","provider","harness","framework")}
        payload={"name":"Composite metered workflow","objective":"Two collaborating agents",
            "mode":"task_centred","task_id":self.task.item.public_id,
            "test_case_ids":[self.case.item.public_id],
            "framework_id":self.comps["framework"].public_id,
            "participants":[{
                "label":"Builder","role":"Implementer",
                "configuration_version":"1","settings":{},
                "component_ids":{k:self.comps[k].public_id for k in ("model","provider","harness")}},
                {"label":"Reviewer","role":"Verifier","configuration_version":"1",
                 "settings":{},"component_ids":{k:self.comps[k].public_id
                                                 for k in ("model","provider","harness")}}],
            "pricing_selections":[]}
        created=self.call("/api/v1/campaigns",payload)
        self.assertEqual(created.status_code,201,created.content)
        row=created.json()
        ids=[x["id"] for x in row["participants"]]
        selections=[self.selection(offers["framework"],"framework")]
        for pid in ids:
            selections.extend(self.selection(offers[k],k,pid)
                              for k in ("model","provider","harness"))
        patched=self.call("/api/v1/campaigns/"+row["id"],{
            "expected_revision":"r001","pricing_selections":selections},method="PATCH")
        self.assertEqual(patched.status_code,200,patched.content)
        started=self.call("/api/v1/campaigns/"+row["id"]+"/actions/start",
                          {"expected_revision":"r002"})
        self.assertEqual(started.status_code,200,started.content)
        ses=self.call("/api/v1/campaigns/"+row["id"]+"/sessions",{
            "test_case_id":self.case.item.public_id,"selected_participant_ids":ids})
        self.assertEqual(ses.status_code,201,ses.content)
        s=ses.json()
        self.assertEqual(len(s["metering"]["schema"]["required_meters"]),7)
        sources={x["source_key"] for x in s["metering"]["schema"]["required_meters"]}
        self.assertEqual(len(sources),7)
        base="/api/v1/sessions/"+s["id"]
        interact=self.call(base+"/interactions",{
            "expected_revision":"r001","type":"agent_response",
            "content":"Builder: initial driver patch","participant_id":ids[0],
            "human_minutes":0,"agent_minutes":8})
        self.assertEqual(interact.status_code,200,interact.content)
        all_usage={k:{"input_tokens":"1000000"} for k in sources}
        meter=self.call(base+"/metering",{"expected_revision":"r002",
                    "consumption":all_usage},method="PATCH")
        self.assertEqual(meter.status_code,200,meter.content)
        self.assertEqual(Decimal(meter.json()["metering"]["quote"][
            "variable_reference_by_currency"]["EUR"]),Decimal("17.5"))
        closed=self.call(base+"/close",{"expected_revision":"r003",
            "outcome":"failed","produced_outputs":"Two-agent review report",
            "quality_evaluation":"Rejected due to failing tests"})
        self.assertEqual(closed.status_code,201,closed.content)
        run=closed.json()
        self.assertEqual(run["kind"],"composite")
        self.assertIsNone(run["solution_id"])
        self.assertEqual(len(run["metrics"]["reference_cost"]["selected_sources"]),7)
        self.assertEqual(len(run["participants"]),2)
        self.assertEqual(CompositeBenchmarkRun.objects.count(),1)
        self.assertEqual(BenchmarkRun.objects.count(),0)
    def test_unused_unpriced_framework_participant_cannot_block_independent_run(self):
        offers={k:self.offer(k) for k in ("model","provider","harness","framework")}
        new=self.call("/api/v1/campaigns",{
            "name":"Partial Framework pricing","objective":"Execute selected priced participant",
            "mode":"task_centred","task_id":self.task.item.public_id,
            "test_case_ids":[self.case.item.public_id],
            "framework_id":self.comps["framework"].public_id,
            "participants":[{
              "label":label,"role":"Agent","configuration_version":"1",
              "component_ids":{k:self.comps[k].public_id
                               for k in ("model","provider","harness")}}
              for label in ("Active agent","Unused candidate")],
            "pricing_selections":[]})
        self.assertEqual(new.status_code,201,new.content)
        row=new.json()
        ids=[p["id"] for p in row["participants"]]
        selected=[self.selection(offers["framework"],"framework")]
        selected.extend(self.selection(offers[k],k,ids[0])
                        for k in ("model","provider","harness"))
        patched=self.call("/api/v1/campaigns/"+row["id"],{
            "expected_revision":"r001","pricing_selections":selected},method="PATCH")
        self.assertEqual(patched.status_code,200,patched.content)
        self.assertFalse(patched.json()["campaign"]["pricing_readiness"]["complete"])
        started=self.call("/api/v1/campaigns/"+row["id"]+"/actions/start",
            {"expected_revision":"r002"})
        self.assertEqual(started.status_code,200,started.content)
        base="/api/v1/campaigns/"+row["id"]+"/sessions"
        allowed=self.call(base,{"test_case_id":self.case.item.public_id,
                               "selected_participant_ids":[ids[0]]})
        self.assertEqual(allowed.status_code,201,allowed.content)
        self.assertEqual(len(allowed.json()["metering"]["schema"]["required_meters"]),4)
        self.assertEqual(self.call(base,{"test_case_id":self.case.item.public_id,
                        "selected_participant_ids":[ids[1]]}).status_code,409)
        self.assertEqual(self.call(base,{"test_case_id":self.case.item.public_id,
                        "selected_participant_ids":ids}).status_code,409)
