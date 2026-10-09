"""PLAT-27: diagnostic detection, deduplication, recovery, RBAC, CSRF and immutable triage."""
import hashlib
import json
from datetime import timedelta
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .catalog_ids import new_public_id
from .data_health_services import inspect_findings, scan
from .identity import ensure_roles
from .models import (CatalogItem, CatalogRevision, DataHealthEvent, DataHealthIssue,
                     EvidenceBlob, ObjectTypeVersion)

BASE = "/api/v1/maintenance"
PASS = "Secure-Fictitious-Health-Password-2026!"


class DataHealthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U = get_user_model()
        cls.operator = U.objects.create_user("health-maintainer", password=PASS)
        cls.operator.groups.add(Group.objects.get(name="data-maintainer"))
        cls.reader = U.objects.create_user("health-reader", password=PASS)
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.admin = U.objects.create_user("health-admin", password=PASS)
        cls.admin.groups.add(Group.objects.get(name="user-admin"))
        cls.writer = U.objects.create_user("health-writer", password=PASS)
        cls.writer.groups.add(Group.objects.get(name="contributor"))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="data-health-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        setting = override_settings(EVIDENCE_STORE_ROOT=self.root)
        setting.enable()
        self.addCleanup(setting.disable)
        self.client = Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.token = self.client.cookies["csrftoken"].value
        self.client.force_login(self.operator)

    def post(self, path, payload=None, csrf=True):
        return self.client.post(
            BASE + path, data=json.dumps({} if payload is None else payload),
            content_type="application/json",
            **({"HTTP_X_CSRFTOKEN":self.token} if csrf else {}))

    def patch(self, public, payload, csrf=True):
        return self.client.patch(
            BASE + "/issues/" + public + "/triage",
            data=json.dumps(payload), content_type="application/json",
            **({"HTTP_X_CSRFTOKEN":self.token} if csrf else {}))

    def make_obsolete(self):
        item = CatalogItem.objects.create(
            type_slug="model",public_id="mdl-health-green-river")
        revision = CatalogRevision.objects.create(
            item=item,number=1,schema_version=ObjectTypeVersion.objects.get(type_slug="model",version=1),
            display_name="Legacy compatibility",properties={
                "release_channel":"preview","custom":{"null":None}
            },created_by=self.writer)
        item.current_revision=revision
        item.save(update_fields=["current_revision"])
        return item

    def blob(self):
        body = b"PLAT27-original-evidence-payload"
        sha = hashlib.sha256(body).hexdigest()
        blob = EvidenceBlob.objects.create(sha256=sha,size=len(body),media_type="text/plain")
        return blob,body

    def test_missing_blob_is_stably_deduplicated_and_auto_resolves_then_reopens(self):
        blob, data = self.blob()
        report = self.post("/scan")
        self.assertEqual(report.status_code, 201, report.content)
        self.assertEqual(report.json()["new"],1)
        issue=DataHealthIssue.objects.get(category="blob_missing")
        self.assertTrue(issue.public_id.startswith("mnt-"))
        self.assertEqual(uuid.UUID(str(issue.id)).version, 7)
        self.assertEqual(issue.subject_ref,blob.pk)
        self.assertEqual(issue.events.count(),1)
        listed = self.client.get(BASE + "/issues?status=open").json()
        self.assertEqual(listed["total"],1)
        self.assertIsNone(listed["results"][0]["subject_id"])
        self.assertNotIn(blob.pk, json.dumps(listed))
        self.assertNotIn(blob.pk, self.client.get(BASE + "/issues/" + issue.public_id).content.decode())
        self.assertEqual(self.post("/scan").json()["new"],0)
        issue.refresh_from_db()
        self.assertEqual(issue.detection_count,2)
        self.assertEqual(issue.events.count(),1)
        file = self.root/"blobs"/blob.sha256[:2]/blob.sha256[2:4]/blob.sha256
        file.parent.mkdir(parents=True)
        file.write_bytes(data)
        resolved = self.post("/scan").json()
        self.assertEqual(resolved["resolved"],1)
        issue.refresh_from_db()
        self.assertEqual(issue.status,"resolved")
        file.write_bytes(b"tampered")
        result = self.post("/scan").json()
        self.assertEqual(result["reopened"],1)
        issue.refresh_from_db()
        self.assertEqual(issue.status,"open")
        self.assertEqual(DataHealthIssue.objects.count(),1)
        self.assertEqual([e.action for e in issue.events.all()],
                         ["detected","auto_resolved","reopened"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                DataHealthEvent.objects.filter(issue=issue).delete()

    def test_obsolete_schema_and_required_fields_preserve_original_revision(self):
        obsolete=self.make_obsolete()
        schema=ObjectTypeVersion.objects.create(
            type_slug="experimental-check",version=1,
            json_schema={"type":"object", "required":["mandatory"],
                         "properties":{"mandatory":{"type":"string"}},
                         "additionalProperties":True})
        x=CatalogItem.objects.create(type_slug="experimental-check",
                                     public_id="ext-required-check")
        rev=CatalogRevision.objects.create(
            item=x,number=1, schema_version=schema,
            display_name="Broken required field", properties={"future":{"raw":None}},
            created_by=self.writer)
        x.current_revision=rev; x.save(update_fields=["current_revision"])
        summary=self.post("/scan")
        self.assertEqual(summary.status_code,201,summary.content)
        self.assertGreaterEqual(summary.json()["findings"],2)
        self.assertTrue(DataHealthIssue.objects.filter(
            category="schema_obsolete",subject_ref=obsolete.public_id).exists())
        self.assertTrue(DataHealthIssue.objects.filter(
            category="schema_missing",subject_ref=x.public_id).exists())
        self.assertEqual(CatalogRevision.objects.get(pk=rev.pk).properties, {"future":{"raw":None}})
        self.assertEqual(CatalogRevision.objects.get(pk=obsolete.current_revision_id).number,1)

    def test_triage_assignee_exception_review_and_repeated_scans(self):
        self.blob()
        self.post("/scan")
        issue=DataHealthIssue.objects.get()
        deadline=(timezone.now().date()+timedelta(days=14)).isoformat()
        self.assertEqual(self.patch(issue.public_id,
            {"status":"exception","rationale":"External source has restricted re-upload",
             "review_after":deadline,"assigned_to":self.operator.username}).status_code,200)
        issue.refresh_from_db()
        self.assertEqual(issue.status,"exception")
        self.assertEqual(issue.assigned_to,self.operator)
        self.assertEqual(self.post("/scan").json()["exceptions"],1)
        issue.refresh_from_db()
        self.assertEqual(issue.status,"exception")
        self.assertEqual(self.patch(issue.public_id,
            {"status":"exception","rationale":"","review_after":deadline}).status_code,400)
        self.assertEqual(self.patch(issue.public_id,
            {"status":"exception","rationale":"ignored","review_after":"2020-01-01"}).status_code,400)
        self.assertEqual(self.patch(issue.public_id,
            {"status":"resolved","assigned_to":"health-writer"}).status_code,400)
        self.assertEqual(self.patch(issue.public_id,
            {"status":"resolved","assigned_to":None}).status_code,200)
        issue.refresh_from_db()
        self.assertEqual(issue.status,"resolved")
        self.assertIsNone(issue.assigned_to)
        self.assertFalse(issue.exception_rationale)
        self.assertEqual(self.post("/scan").json()["reopened"],1)
        actions=[x.action for x in issue.events.order_by("created_at","id")]
        self.assertEqual(actions,["detected","triaged","triaged","reopened"])
        self.assertEqual(self.client.get(BASE+"/issues/"+issue.public_id).json()["history"][-1]["action"],"reopened")

    def test_isolated_maintenance_role_and_read_only_provenance(self):
        self.blob()
        self.assertEqual(self.client.get(BASE+"/health").status_code,200)
        self.assertEqual(self.client.get(BASE+"/issues").json()["total"],0)
        self.assertEqual(self.client.get(BASE+"/migrations").status_code,200)
        self.assertEqual(self.client.get("/api/v1/models").status_code,403)
        self.assertEqual(self.client.get("/api/v1/admin/users").status_code,403)
        self.assertEqual(self.post("/scan",csrf=False).status_code,403)
        self.assertEqual(self.post("/scan",{"source":"arbitrary-python"}).status_code,400)
        self.assertEqual(DataHealthIssue.objects.count(),0)
        self.assertEqual(self.post("/scan").status_code,201)
        issue=DataHealthIssue.objects.get()
        self.assertEqual(self.patch(issue.public_id,{"status":"resolved"},csrf=False).status_code,403)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(BASE+"/health").status_code,403)
        self.assertEqual(self.client.get(BASE+"/issues").status_code,403)
        self.assertEqual(self.client.get(BASE+"/issues/"+issue.public_id).status_code,403)
        self.assertEqual(self.post("/scan").status_code,403)
        self.assertEqual(self.patch(issue.public_id,{"status":"resolved"}).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(BASE+"/health").status_code,403)
        self.client.logout()
        self.client.get("/api/v1/auth/csrf")
        self.token = self.client.cookies["csrftoken"].value
        self.assertEqual(self.client.get(BASE+"/health").status_code,401)
        self.assertEqual(self.post("/scan").status_code,401)

    def test_invalid_filter_and_incomplete_scan_rolls_back(self):
        self.blob()
        self.assertEqual(self.client.get(BASE+"/issues?status=surprise").status_code,400)
        self.assertEqual(self.client.get(BASE+"/issues?page=0").status_code,400)
        with patch("config.data_health_services.inspect_findings", side_effect=RuntimeError("scanner crash")):
            with self.assertRaisesRegex(RuntimeError,"scanner crash"):
                scan(actor=self.operator)
        self.assertEqual(DataHealthIssue.objects.count(),0)
        self.assertEqual(DataHealthEvent.objects.count(),0)
