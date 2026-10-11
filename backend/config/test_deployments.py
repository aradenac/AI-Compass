"""FUT-15: Server deployment source pins, first-use authority, security and immutable history."""
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client

from .test_opportunities import OpportunityTests
from .models import (DeploymentTarget, DeploymentRevision, DeploymentEvent,
                     OpportunityScenario, UserEnvironmentRevision)
from .workload_services import create_profile

BASE = "/api/v1/planning/deployments"


class DeploymentTests(OpportunityTests.__bases__[0]):
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

    def select(self, client, csrf, population, run, seats=None, **extra):
        return self.request(client, csrf, BASE, {
            "profile_id": population.public_id,
            "task_id": self.task.item.public_id,
            "kind": "benchmark", "candidate_id": run["solution_id"],
            "selection": {"seats": seats or [
                {"key": "seat-a", "person_profile_id": None,
                 "available_os": ["windows"]}]}, **extra})

    def event(self, client, csrf, target, seat, component, action,
              evidence=""):
        return self.request(client, csrf, BASE + "/" + target["id"] + "/events", {
            "expected_revision": target["revision"], "seat_key": seat,
            "component_id": component, "action": action,
            "evidence_reference": evidence})

    def test_empty_auth_csrf_and_deliberate_selection(self):
        actor, client, token, population = self.plan()
        self.assertEqual(client.get(BASE).json()["results"], [])
        self.assertEqual(Client().get(BASE).status_code, 401)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(BASE).status_code, 403)
        self.assertEqual(client.post(BASE, json.dumps({}), content_type="application/json").status_code, 403)
        run, _ = self.priced_published()
        selected = self.select(client, token, population, run)
        self.assertEqual(selected.status_code, 201, selected.content)
        doc = selected.json()
        self.assertEqual(doc["selected_count"], 1)
        self.assertEqual(doc["activated_count"], 0)
        self.assertFalse(doc["beneficiaries"][0]["ready"])
        self.assertEqual(DeploymentTarget.objects.count(), 1)
        self.assertEqual(DeploymentEvent.objects.count(), 0)
        self.assertEqual(self.select(client, token, population, run).status_code, 400)
        # No planning action can manipulate actual AI Compass roles.
        self.assertFalse(actor.has_perm("auth.users_manage"))
        self.assertFalse(actor.has_perm("auth.business_write"))
        self.assertEqual(client.get(BASE + "/" + doc["id"] + "/revisions").json()[
            "revisions"][0]["selection"]["source"]["type"], "measured_run")

    def test_entitlement_setup_first_use_revocation_and_frozen_economics(self):
        actor, client, token, population = self.plan()
        run, _ = self.priced_published()
        original = self.request(client, token, "/api/v1/planning/opportunities", {
            "profile_id": population.public_id,
            "scenario": self.config("benchmark", run["solution_id"])})
        self.assertEqual(original.status_code, 201, original.content)
        historical = original.json()["snapshot"]
        target_response = self.select(client, token, population, run,
                                      scenario_id=original.json()["id"])
        self.assertEqual(target_response.status_code, 201, target_response.content)
        target = target_response.json()
        self.assertEqual(target["origin_snapshot_id"], original.json()["revision_id"])
        components = [x["id"] for x in target["components"]]
        self.assertEqual(len(components), 3)
        # Exact pre-existing fixture metadata is independent of the manually
        # verified access state; simulate a matching OS, accessible offer and
        # successfully verified pinned guide without external provider calls.
        with patch("config.deployment_services.compose", return_value={
                "status": "compatible", "matching_os": ["windows"]}), patch(
                "config.deployment_services.accessibility", return_value="accessible"), patch(
                "config.deployment_services.from_revision", return_value={"ready": True}):
            self.assertEqual(self.event(client, token, target, "seat-a", None,
                                        "first_use", "Ticket FORGED-001").status_code, 400)
            for item in components:
                for action in ("requested", "approved", "provisioned", "verified"):
                    response = self.event(client, token, target, "seat-a",
                                          item, action, "Ticket APPROVED-001")
                    self.assertEqual(response.status_code, 201, response.content)
            premature = self.event(client, token, target, "seat-a", None,
                                   "first_use", "Ticket FIRST-001")
            self.assertEqual(premature.status_code, 400)
            self.assertEqual(self.event(client, token, target, "seat-a", None,
                                        "setup_verified", "Ticket SETUP-001").status_code, 201)
            self.assertEqual(self.event(client, token, target, "seat-a", None,
                                        "first_use", "Ticket FIRST-001").status_code, 201)
            now = client.get("/api/v1/planning/opportunities/" + original.json()["id"]).json()
            self.assertTrue(now["source_changed"])
            self.assertEqual(now["snapshot"], historical)
            self.assertEqual(now["current"]["cells"][0]["slices"]["verified_headcount"], 1)
            self.assertGreater(Decimal(now["current"]["totals"]["activated_potential_eur"]), 0)
            self.assertEqual(client.get(BASE + "/" + target["id"]).json()["activated_count"], 1)
            refused = self.event(client, token, target, "seat-a", components[0],
                                 "verified", "Repeated VERIFY")
            self.assertEqual(refused.status_code, 400)
            self.assertEqual(self.event(client, token, target, "seat-a", components[0],
                                        "revoked", "Lost access").status_code, 201)
            revoked = client.get("/api/v1/planning/opportunities/" + original.json()["id"]).json()
            self.assertEqual(revoked["current"]["cells"][0]["slices"]["verified_headcount"], 0)
            self.assertEqual(revoked["current"]["totals"]["activated_potential_eur"], "0.00")
            self.assertEqual(revoked["snapshot"], historical)
            # Re-granting an entitlement must NOT reactivate the previous use
            # attestation after explicit revocation.
            for action in ("requested", "approved", "provisioned", "verified"):
                self.assertEqual(self.event(client, token, target, "seat-a",
                    components[0], action, "Ticket REGRANT-001").status_code, 201)
            after_regrant = client.get(BASE + "/" + target["id"]).json()
            self.assertEqual(after_regrant["activated_count"], 0)
            self.assertEqual(self.event(client, token, target, "seat-a", None,
                "setup_verified", "Ticket RECHECK-001").status_code, 201)
            self.assertEqual(self.event(client, token, target, "seat-a", None,
                "first_use", "Ticket REUSED-001").status_code, 201)
            self.assertEqual(client.get(BASE + "/" + target["id"]).json()["activated_count"], 1)

    def test_invalid_scope_transitions_revision_and_protected_history(self):
        actor, client, token, population = self.plan(headcount=2)
        run, _ = self.priced_published()
        self.assertEqual(self.select(client, token, population, run, seats=[
            {"key": "x"}, {"key": "x"}]).status_code, 400)
        self.assertEqual(self.select(client, token, population, run, seats=[
            {"key": "bad", "available_os": []}]).status_code, 400)
        bad_guide = self.request(client, token, BASE, {
            "profile_id": population.public_id, "task_id": self.task.item.public_id,
            "kind": "benchmark", "candidate_id": run["solution_id"],
            "selection": {"seats": [{"key": "x"}],
                          "guide_revision_id": "00000000-0000-0000-0000-000000000000"}})
        self.assertEqual(bad_guide.status_code, 400)
        chosen = self.select(client, token, population, run)
        self.assertEqual(chosen.status_code, 201, chosen.content)
        entry = chosen.json()
        self.assertEqual(self.event(client, token, entry, "seat-a", "mdl-not-a-pin",
                                    "requested").status_code, 400)
        self.assertEqual(self.event(client, token, entry, "seat-a",
                                    entry["components"][0]["id"], "verified",
                                    "Without workflow").status_code, 400)
        self.assertEqual(self.event(client, token, entry, "seat-a", None,
                                    "setup_verified", "Ticket setup").status_code, 400)
        stale = self.request(client, token, BASE + "/" + entry["id"], {
            "expected_revision": "r000", "selection": {
                "seats": [{"key": "seat-a"}]}}, method="PATCH")
        self.assertEqual(stale.status_code, 409)
        revised = self.request(client, token, BASE + "/" + entry["id"], {
            "expected_revision": "r001", "selection": {
                "seats": [{"key": "seat-a", "available_os": ["linux"]}]}},
                              method="PATCH")
        self.assertEqual(revised.status_code, 200, revised.content)
        self.assertEqual(revised.json()["revision"], "r002")
        self.assertEqual(DeploymentRevision.objects.count(), 2)
        self.assertEqual(self.event(client, token, entry, "seat-a",
                                    entry["components"][0]["id"], "requested").status_code, 409)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                DeploymentRevision.objects.update(number=5)
        self.assertEqual(client.get(BASE + "/" + entry["id"] + "/revisions").status_code, 200)

    def test_person_self_only_does_not_expose_others_or_rates(self):
        actor, client, token, population = self.plan(headcount=2)
        run, _ = self.priced_published()
        first = get_user_model().objects.create_user("deployment-member")
        first.groups.add(Group.objects.get(name="user"))
        second = get_user_model().objects.create_user("deployment-stranger")
        second.groups.add(Group.objects.get(name="user"))
        p1 = create_profile(actor=actor, kind="person", data={
            "name": "Member", "linked_user_id": first.pk,
            "hourly_rate_eur": "123.00"})
        p2 = create_profile(actor=actor, kind="person", data={
            "name": "Stranger", "linked_user_id": second.pk,
            "hourly_rate_eur": "456.00"})
        created = self.select(client, token, population, run, seats=[
            {"key": "member", "person_profile_id": p1.public_id, "available_os": ["linux"]},
            {"key": "stranger", "person_profile_id": p2.public_id,
             "available_os": ["windows"]}])
        self.assertEqual(created.status_code, 201, created.content)
        person_client = Client()
        person_client.force_login(first)
        self.assertEqual(person_client.get(BASE).status_code, 403)
        own = person_client.get("/api/v1/engineer/deployments")
        self.assertEqual(own.status_code, 200, own.content)
        self.assertEqual(len(own.json()["results"]), 1)
        serialized = json.dumps(own.json())
        self.assertNotIn("stranger", serialized)
        self.assertNotIn("456.00", serialized)
        self.assertNotIn("123.00", serialized)
        self.assertNotIn("population_headcount", serialized)
        disabled = get_user_model().objects.get(pk=first.pk)
        disabled.is_active = False
        disabled.save(update_fields=["is_active"])
        self.assertEqual(person_client.get("/api/v1/engineer/deployments").status_code, 401)
        other = Client()
        other.force_login(second)
        self.assertEqual(len(other.get("/api/v1/engineer/deployments").json()["results"]), 1)
