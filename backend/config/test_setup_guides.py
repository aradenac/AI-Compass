"""PLAT-11: reusable Setup Guide CRUD, immutable history, URL validation and RBAC."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError,transaction
from django.test import Client,TestCase
from .identity import ensure_roles
from .models import CatalogItem,CatalogRevision,CatalogAuditEvent,ObjectTypeVersion

BASE="/api/v1/guides"


class SetupGuideTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U=get_user_model()
        cls.editor=U.objects.create_user("guide-editor",password="long-test-password-2026")
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.reader=U.objects.create_user("guide-reader",password="long-test-password-2026")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=U.objects.create_user("guide-maint",password="long-test-password-2026")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))

    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.csrf=self.client.cookies["csrftoken"].value
        self.client.force_login(self.editor)

    def send(self,path,body,method="POST",csrf=True):
        handler=self.client.post if method=="POST" else self.client.patch
        return handler(path,data=json.dumps(body),content_type="application/json",
                       **({"HTTP_X_CSRFTOKEN":self.csrf} if csrf else {}))

    def new(self,properties=None,name="Tool installation"):
        response=self.send(BASE,{"name":name,"properties":properties if properties is not None
            else {"text":"Run a documented shell command","opaque":{"future":[None,3]}}})
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def test_empty_server_and_registered_schema_without_business_fixtures(self):
        self.assertEqual(CatalogItem.objects.filter(type_slug="setup_guide").count(),0)
        self.assertEqual(self.client.get(BASE).json(),{"results":[]})
        schema=ObjectTypeVersion.objects.get(type_slug="setup_guide",version=1)
        self.assertIn("anyOf",schema.json_schema)
        self.assertEqual(CatalogRevision.objects.filter(item__type_slug="setup_guide").count(),0)

    def test_text_only_url_only_and_both_have_permanent_ids(self):
        text=self.new()
        url=self.new({"url":"https://docs.example.org/setup?version=1"},"Reference-only guide")
        both=self.new({"text":"Install version 3","url":"https://example.org/guide",
                       "description":"Vendor documentation","future":{"arbitrary":{"keep":None}}},
                      "Mixed guide")
        for guide in (text,url,both):
            self.assertTrue(guide["id"].startswith("gui-"))
            self.assertEqual(guide["revision"],"r001")
            self.assertEqual(guide["schema_version"],1)
            self.assertTrue(guide["revision_id"])
            self.assertEqual(guide["type"],"setup_guide")
            self.assertEqual(self.client.get(BASE+"/"+guide["id"]).json()["id"],guide["id"])
        self.assertNotEqual(text["id"],url["id"])
        self.assertNotIn("url",text["properties"])
        self.assertNotIn("text",url["properties"])
        self.assertEqual(both["properties"]["future"],{"arbitrary":{"keep":None}})
        self.assertEqual(self.client.get(BASE+"?q=reference").json()["results"][0]["id"],url["id"])
        self.assertEqual(self.client.get(BASE+"?q="+text["id"]).json()["results"][0]["id"],text["id"])
        self.assertEqual(CatalogItem.objects.filter(type_slug="setup_guide").count(),3)
        self.assertEqual(CatalogAuditEvent.objects.filter(item__type_slug="setup_guide",action="created").count(),3)

    def test_revise_retains_unknown_fields_and_exact_original_revision(self):
        old=self.new({"url":"https://old.example.org/docs",
                      "text":"Original instructions","future":{"null":None}})
        response=self.send(BASE+"/"+old["id"],{"expected_revision":"r001",
             "properties":{"url":"https://new.example.org/docs",
                           "description":"Updated references"}},method="PATCH")
        self.assertEqual(response.status_code,200,response.content)
        self.assertTrue(response.json()["changed"])
        current=response.json()["guide"]
        self.assertEqual(current["revision"],"r002")
        self.assertNotEqual(current["revision_id"],old["revision_id"])
        self.assertEqual(current["properties"]["text"],"Original instructions")
        self.assertEqual(current["properties"]["future"],{"null":None})
        self.assertEqual(self.client.get(BASE+"/"+old["id"]+"/revisions/1").json()["properties"]["url"],
                         "https://old.example.org/docs")
        history=self.client.get(BASE+"/"+old["id"]+"/revisions")
        self.assertEqual(history.status_code,200)
        self.assertEqual([r["revision"] for r in history.json()["revisions"]],["r001","r002"])
        self.assertEqual(history.json()["revisions"][0]["revision_id"],old["revision_id"])
        self.assertEqual(CatalogAuditEvent.objects.filter(item__public_id=old["id"]).count(),2)
        stale=self.send(BASE+"/"+old["id"],{"expected_revision":"r001",
                        "properties":{"text":"Conflicting edit"}},method="PATCH")
        self.assertEqual(stale.status_code,409)
        unchanged=self.send(BASE+"/"+old["id"],{"expected_revision":"r002"},method="PATCH")
        self.assertEqual(unchanged.status_code,200)
        self.assertFalse(unchanged.json()["changed"])
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=old["id"]).count(),2)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CatalogRevision.objects.filter(item__public_id=old["id"],number=1).update(
                    display_name="Overwritten")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CatalogAuditEvent.objects.filter(item__public_id=old["id"]).delete()

    def test_switch_between_forms_preserving_historical_urls_and_text(self):
        original=self.new({"text":"Step 1","url":"https://example.org/original"})
        patched=self.send(BASE+"/"+original["id"],{"expected_revision":"r001",
             "properties":{"url":""}},method="PATCH")
        self.assertEqual(patched.status_code,200,patched.content)
        self.assertEqual(patched.json()["guide"]["properties"]["text"],"Step 1")
        self.assertNotIn("url",patched.json()["guide"]["properties"])
        with_url=self.send(BASE+"/"+original["id"],{"expected_revision":"r002",
             "properties":{"text":"","url":"https://example.org/replacement"}},method="PATCH")
        self.assertEqual(with_url.status_code,200,with_url.content)
        self.assertNotIn("text",with_url.json()["guide"]["properties"])
        self.assertEqual(self.client.get(BASE+"/"+original["id"]+"/revisions/1").json()["properties"]["url"],
                         "https://example.org/original")
        self.assertEqual(self.client.get(BASE+"/"+original["id"]+"/revisions/2").json()["properties"]["text"],
                         "Step 1")

    def test_bad_payloads_urls_and_no_content_cannot_create_partial_records(self):
        invalid=[
            {"text":" "},{"text":""},{"url":""},{"url":"ftp://example.org/docs"},
            {"url":"javascript:alert(1)"},{"url":"file:///etc/passwd"},
            {"url":"https://user:pass@example.org/secret"},
            {"url":"https://example.org/space in path"},
            {"url":"http://"},{"url":"https://example.org:abc/setup"},
            {"text":17},{"url":1},
        ]
        for props in invalid:
            with self.subTest(properties=props):
                response=self.send(BASE,{"name":"Invalid", "properties":props})
                self.assertEqual(response.status_code,400,response.content)
        self.assertEqual(self.send(BASE,{"name":"Invalid","properties":{"text":"Okay"},"extra":1}).status_code,400)
        self.assertEqual(self.send(BASE,{"name":"Invalid","properties":[]}).status_code,400)
        self.assertEqual(CatalogItem.objects.filter(type_slug="setup_guide").count(),0)

    def test_non_writers_and_csrf_never_mutate(self):
        self.assertEqual(self.send(BASE,{"name":"A","properties":{"text":"Guide"}},
                                   csrf=False).status_code,403)
        original=self.new()
        self.assertEqual(self.send(BASE+"/"+original["id"],{"expected_revision":"r001",
                         "properties":{"text":"Altered"}},method="PATCH",csrf=False).status_code,403)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(BASE).status_code,200)
        self.assertEqual(self.client.get(BASE+"/"+original["id"]).status_code,200)
        self.assertEqual(self.client.get(BASE+"/"+original["id"]+"/revisions").status_code,200)
        self.assertEqual(self.send(BASE,{"name":"B","properties":{"text":"Not allowed"}}).status_code,403)
        self.client.force_login(self.maint)
        self.assertEqual(self.client.get(BASE).status_code,403)
        self.assertEqual(self.client.get(BASE+"/"+original["id"]).status_code,403)
        self.assertEqual(self.send(BASE,{"name":"B","properties":{"text":"Not allowed"}}).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(BASE).status_code,401)
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=original["id"]).count(),1)

    def test_guide_is_reusable_reference_not_a_demo_or_campaign_import(self):
        item=self.new({"text":"Actual Server-authored installation steps"})
        self.assertEqual(self.client.get("/api/v1/catalog/items/"+item["id"]).status_code,200)
        guide=self.client.get(BASE+"/"+item["id"]).json()
        self.assertEqual(guide["id"],item["id"])
        self.assertEqual(guide["revision_id"],item["revision_id"])
        self.assertNotIn("campaign_id",guide)
        self.assertEqual(CatalogItem.objects.filter(type_slug="test_case").count(),0)
