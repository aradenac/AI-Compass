"""FUT-17: source-specific committed audit, exact diffs and strict RBAC/privacy."""
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client
from django.utils import timezone

from .test_activity import ActivityFeedTests
from .test_opportunities import OpportunityTests
from .models import (BudgetPlan, BudgetRevision, WorkloadRevision,
                     UserAccessAuditEvent, CatalogAuditEvent, DataHealthIssue,
                     DataHealthEvent, DeploymentTarget, DeploymentRevision,
                     CatalogItem, CatalogRevision, BenchmarkRun)
from .workload_services import create_profile
from .run_lifecycle_services import change as change_run

BASE = "/api/v1/maintenance/audit"


class GovernanceAuditTests(ActivityFeedTests.__bases__[0]):
    setUpTestData = classmethod(ActivityFeedTests.setUpTestData.__func__)
    setUp = ActivityFeedTests.setUp
    post = ActivityFeedTests.post
    make_model = ActivityFeedTests.make_model

    def _as_auditor(self):
        self.client.force_login(self.maintainer)

    def test_catalog_revision_before_after_and_shared_activity_event(self):
        self._as_auditor()
        self.assertEqual(self.client.get(BASE).json()["results"], [])
        self.assertEqual(self.client.get("/api/v1/models").status_code, 403)
        self.client.force_login(self.writer)
        first = self.make_model("Original safe model")
        edited = self.post("/api/v1/models/"+first["id"]+"/revisions",{
            "expected_revision":"r001","name":"Revised safe model"})
        self.assertEqual(edited.status_code, 201, edited.content)
        activity=self.client.get("/api/v1/activity?type=model").json()["results"]
        self.assertEqual(len(activity),2)
        event_id=activity[0]["id"]
        self._as_auditor()
        response=self.client.get(BASE+"?source=catalog&object_id="+first["id"])
        self.assertEqual(response.status_code,200,response.content)
        rows=response.json()["results"]
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["id"],"catalog:"+event_id)
        self.assertEqual(rows[0]["revision"],"r002")
        self.assertEqual(rows[0]["object_type"],"model")
        self.assertEqual(rows[0]["actor"],"feed-writer")
        detail=self.client.get(BASE+"/catalog:"+event_id)
        self.assertEqual(detail.status_code,200,detail.content)
        self.assertIn({"field":"display_name","operation":"changed",
            "before":"Original safe model","after":"Revised safe model"},detail.json()["changes"])
        self.assertEqual(detail.json()["after_revision_id"],activity[0]["revision_id"])
        self.assertEqual(detail.json()["before_revision_id"],activity[1]["revision_id"])
        self.assertEqual(len(self.client.get(BASE+"?field=display_name").json()["results"]),2)
        history=self.client.get(BASE+"/history/"+first["id"]).json()
        self.assertEqual(len(history["results"]),2)
        self.assertEqual(self.client.get(BASE+"/export?source=catalog&format=json").status_code,200)
        self.assertEqual(self.client.get(BASE+"/export?source=catalog&format=csv").status_code,200)
        self.assertEqual(self.client.get(BASE+"/export").headers["Cache-Control"],"no-store")

    def test_account_secrets_and_internal_sources_never_leak(self):
        secret="DO_NOT_EXPOSE_TEST_SECRET_8531"
        model=self.make_model("Safe public catalog name")
        # No guessed read permission from maintenance/audit grants.
        event=UserAccessAuditEvent.objects.create(
            actor=self.admin,subject=self.reader,action="account_updated",
            details={"active":{"from":True,"to":False},
                     "password":"scrypt$"+secret,"secret_token":secret})
        self._as_auditor()
        response=self.client.get(BASE)
        self.assertEqual(response.status_code,200)
        text=response.content.decode()
        self.assertIn(model["id"],text)
        self.assertNotIn("user:"+str(self.reader.pk),text)
        self.assertNotIn(secret,text)
        self.assertEqual(self.client.get(BASE+"?source=access").status_code,403)
        self.assertEqual(self.client.get(BASE+"/access:"+str(event.pk)).status_code,403)
        self.assertEqual(self.client.get(BASE+"/export?source=access").status_code,403)
        self.client.force_login(self.dual)
        # Workgroup+Users rights alone are insufficient for audit_view.
        self.assertEqual(self.client.get(BASE).status_code,403)
        self.dual.groups.add(Group.objects.get(name="data-maintainer"))
        response=self.client.get(BASE+"/access:"+str(event.pk))
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()["changes"][0]["field"],"active")
        self.assertNotIn(secret,response.content.decode())
        self.assertNotIn("password",response.content.decode())
        self.assertNotIn(secret,self.client.get(BASE+"/export?source=access").content.decode())

    def test_native_immutable_workload_budget_and_maintenance_event_without_person_rate(self):
        auditor=self.maintainer
        # Build synthetic infrastructure data, not a production seed.
        profile=create_profile(actor=auditor,kind="cohort",data={
            "name":"Confidential synthetic cohort", "headcount":2,
            "hourly_rate_eur":"876.54",
            "workloads":[]})
        old=profile.revisions.first()
        WorkloadRevision.objects.create(profile=profile,number=2,
            name="Confidential renamed cohort",headcount=4,
            hourly_rate_eur=Decimal("9999.99"),notes={"password":"should-be-private"},
            created_by=auditor)
        budget=BudgetPlan.objects.create(public_id="bdg-synthetic-audit",
            profile=profile,created_by=auditor)
        BudgetRevision.objects.create(budget=budget,number=1,
            assumptions={"name":"private budget","period_months":3,
                "include_active":False,"items":[]},
            projection={"person_profile_id":"very-private"},created_by=auditor)
        issue=DataHealthIssue.objects.create(public_id="mnt-synthetic-audit",
            dedupe_key="0"*64,category="missing_info",severity="medium",
            subject_type="model",subject_ref="private-check",summary="An internal issue")
        health=DataHealthEvent.objects.create(issue=issue,actor=None,action="detected",
            detail={"from":"open","to":"resolved","private_token":"hidden"})
        self._as_auditor()
        docs=self.client.get(BASE+"?object_id="+profile.public_id).json()["results"]
        self.assertEqual(len(docs),2)
        self.assertEqual(docs[0]["object_type"],"workload")
        before=self.client.get(BASE+"/workload:"+str(old.pk)).json()
        self.assertIsNone(before["event"]["actor_roles_at_event"])
        record=self.client.get(BASE+"/workload:"+str(docs[0]["revision_id"])).json()
        self.assertEqual(record["changes"],[{
            "field":"headcount","operation":"changed","before":2,"after":4}])
        other=self.client.get(BASE+"?source=budget").json()["results"]
        self.assertEqual(len(other),1)
        self.assertEqual(other[0]["object_id"],budget.public_id)
        unknown=self.client.get(BASE+"/health:"+str(health.pk)).json()
        self.assertIsNone(unknown["event"]["actor"])
        self.assertEqual(unknown["actor_attribution"],"unknown_not_inferred")
        dumped=self.client.get(BASE+"/export").content.decode()
        for forbidden in ("876.54","9999.99","private budget",
                          "very-private","should-be-private","private-token"):
            self.assertNotIn(forbidden,dumped)

    def test_bounded_queries_strict_filters_readonly_and_nonfabrication(self):
        self._as_auditor()
        self.assertEqual(self.client.post(BASE,data="{}",
            content_type="application/json").status_code,405)
        self.assertEqual(self.client.get(BASE+"?page=21").status_code,400)
        self.assertEqual(self.client.get(BASE+"?source=unknown").status_code,400)
        self.assertEqual(self.client.get(BASE+"?unexpected=1").status_code,400)
        self.assertEqual(self.client.get(BASE+"?from=2026-01-01").status_code,400)
        self.assertEqual(self.client.get(BASE+"/catalog:bad").status_code,400)
        self.assertEqual(self.client.get(BASE+"/catalog:00000000-0000-0000-0000-000000000000").status_code,404)
        self.assertEqual(self.client.get(BASE+"?format=csv").status_code,400)
        self.assertEqual(self.client.get(BASE+"/export?format=pdf").status_code,400)
        self.client.force_login(self.writer)
        self.assertEqual(self.client.get(BASE).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(BASE).status_code,401)


class GovernanceRunTests(OpportunityTests.__bases__[0]):
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
    priced_published = OpportunityTests.priced_published

    def test_published_run_correction_uses_original_catalog_audit_identity(self):
        run, reviewer = self.priced_published()
        from .models import RunAmendment
        original=BenchmarkRun.objects.get(public_id=run["id"])
        previous=RunAmendment.objects.get(individual_run=original,number=2)
        number=previous.number
        before=previous.metrics["tokens_count"]
        result=change_run(actor=reviewer,identifier=run["id"],
            expected_revision="r%03d"%number,action="corrected",
            reason="Source evidence double-checked for governance audit",
            metrics_patch={"tokens_count":23})
        self.client.force_login(self.maint)
        # OppTests default maintainer account should have audit_view via roles.
        record=self.client.get(BASE+"/catalog:"+str(result.audit_event_id))
        self.assertEqual(record.status_code,200,record.content)
        body=record.json()
        self.assertEqual(body["event"]["object_id"],run["id"])
        self.assertEqual(body["event"]["object_type"],"run")
        self.assertEqual(body["event"]["revision"],"r003")
        self.assertIn({"field":"tokens_count","operation":"changed",
            "before":before,"after":23},body["changes"])
        self.assertEqual(body["correlation"],str(result.audit_event_id))
