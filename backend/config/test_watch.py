"""PLAT-18 Source library and Technology Watch: real Server, RBAC and immutable evidence."""
import hashlib
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError,transaction
from django.test import Client,TestCase,override_settings

from .identity import ensure_roles
from .models import (CatalogItem,CatalogRevision,CatalogAuditEvent,
                     EvidenceLink,WatchSourcePin,ObjectTypeVersion)

SRC="/api/v1/sources"
WATCH="/api/v1/watch-entries"


class WatchPersistenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        users=get_user_model()
        cls.editor=users.objects.create_user("watch-editor",password="test")
        cls.reader=users.objects.create_user("watch-reader",password="test")
        cls.reviewer=users.objects.create_user("watch-reviewer",password="test")
        cls.maint=users.objects.create_user("watch-maint",password="test")
        for user,role in ((cls.editor,"contributor"),(cls.reader,"user"),
                          (cls.reviewer,"reviewer"),(cls.maint,"data-maintainer")):
            user.groups.add(Group.objects.get(name=role))

    def setUp(self):
        folder=tempfile.TemporaryDirectory(prefix="ai-watch-evidence-")
        self.addCleanup(folder.cleanup)
        guard=override_settings(EVIDENCE_STORE_ROOT=Path(folder.name))
        guard.enable();self.addCleanup(guard.disable)
        self.browser=Client(enforce_csrf_checks=True)
        self.browser.get("/api/v1/auth/csrf")
        self.token=self.browser.cookies["csrftoken"].value
        self.browser.force_login(self.editor)

    def req(self,path,payload=None,method="POST",browser=None,csrf=None):
        client=browser or self.browser
        fn=client.post if method=="POST" else client.patch
        return fn(path,data=json.dumps(payload or {}),content_type="application/json",
                 HTTP_X_CSRFTOKEN=self.token if csrf is None else csrf)

    def as_user(self,user):
        browser=Client(enforce_csrf_checks=True)
        browser.get("/api/v1/auth/csrf")
        browser.force_login(user)
        return browser,browser.cookies["csrftoken"].value

    def source(self,title="Technical report"):
        r=self.req(SRC,{"name":title,"properties":{
            "claim":"Original benchmark observation",
            "citation":"Source citation with ISO dates",
            "url":"https://example.org/report","source_type":"benchmark",
            "published_on":None,"retrieved_on":"2026-10-10",
            "confidence":"medium","limitations":"Not a controlled in-house result",
            "unknown_meta":{"nullable":None},
        }})
        self.assertEqual(r.status_code,201,r.content)
        return r.json()

    def entry(self,title="Model signal",links=None):
        r=self.req(WATCH,{"name":title,"properties":{
            "hypothesis":"Potential for embedded C development",
            "assumptions":"Depends on platform and harness",
            "notes":"Evidence not the same as measured runs",
            "external":{"nullable":None}},
            "sources":links or []})
        self.assertEqual(r.status_code,201,r.content)
        return r.json()

    def review(self,path,revision,action):
        reviewer,csrf=self.as_user(self.reviewer)
        return self.req(path+"/actions/"+action,
                        {"expected_revision":revision},browser=reviewer,csrf=csrf)

    def upload(self,id,rev,text=b"original external report\n"):
        response=self.browser.post("/api/v1/catalog/items/"+id+"/evidence/upload",{
            "revision":rev,
            "file":SimpleUploadedFile("source.txt",text,content_type="text/plain"),
            "source":"research-original",
            "provenance":json.dumps({"extractor":"human","unknown":None}),
        },HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def test_empty_server_and_schema_registration_without_demo_seeding(self):
        self.assertEqual(self.browser.get(SRC).json(),{"results":[]})
        self.assertEqual(self.browser.get(WATCH).json(),{"results":[]})
        self.assertEqual(CatalogItem.objects.filter(type_slug__in=[
            "research_source","watch_entry"]).count(),0)
        self.assertEqual(ObjectTypeVersion.objects.filter(
            type_slug__in=["research_source","watch_entry"],version=1).count(),2)
        self.assertEqual(WatchSourcePin.objects.count(),0)

    def test_one_source_two_entries_unlink_revision_pins_and_provenance(self):
        source=self.source()
        entry1=self.entry("Signal A",[{"id":source["id"],"revision":"r001"}])
        entry2=self.entry("Signal B",[{"id":source["id"]}])
        self.assertEqual(len(entry1["sources"]),1)
        self.assertEqual(entry1["sources"][0]["revision_id"],source["revision_id"])
        self.assertEqual(entry2["sources"][0]["revision_id"],source["revision_id"])
        old=self.req(SRC+"/"+source["id"],{"expected_revision":"r001",
            "properties":{"claim":"Revised statement","confidence":"high"}},
            method="PATCH")
        self.assertEqual(old.status_code,200,old.content)
        newer=old.json()["record"]
        self.assertEqual(newer["revision"],"r002")
        self.assertEqual(newer["properties"]["unknown_meta"],{"nullable":None})
        self.assertEqual(self.browser.get(SRC+"/"+source["id"]+"/revisions/1").json()
                         ["properties"]["claim"],"Original benchmark observation")
        # Existing links are still EXACTLY the old source revision after source edits.
        self.assertEqual(self.browser.get(WATCH+"/"+entry2["id"]).json()
                         ["sources"][0]["revision_id"],source["revision_id"])
        unlink=self.req(WATCH+"/"+entry1["id"],{"expected_revision":"r001","sources":[]},
                        method="PATCH")
        self.assertEqual(unlink.status_code,200,unlink.content)
        self.assertEqual(unlink.json()["record"]["sources"],[])
        self.assertEqual(self.browser.get(WATCH+"/"+entry1["id"]+"/revisions/1").json()
                         ["sources"][0]["revision_id"],source["revision_id"])
        self.assertEqual(self.browser.get(WATCH+"/"+entry2["id"]).json()
                         ["sources"][0]["revision_id"],source["revision_id"])
        self.assertEqual(CatalogItem.objects.filter(type_slug="research_source").count(),1)
        self.assertEqual(WatchSourcePin.objects.count(),2)
        fresh=Client();fresh.force_login(self.editor)
        self.assertEqual(fresh.get(WATCH+"/"+entry1["id"]).json()["sources"],[])
        self.assertEqual(len(fresh.get(WATCH+"/"+entry2["id"]).json()["sources"]),1)
        for qs in (WatchSourcePin.objects,):
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    qs.filter(entry_revision_id=CatalogRevision.objects.get(
                        item__public_id=entry2["id"],number=1).pk).delete()
        self.assertTrue(CatalogAuditEvent.objects.filter(
            item__public_id=entry1["id"],action="revised").exists())

    def test_review_visibility_and_direct_generic_evidence_permissions(self):
        s=self.source()
        w=self.entry(links=[{"id":s["id"]}])
        draft_bytes=b"original and confidential prior to review\n"
        draft=self.upload(s["id"],"r001",draft_bytes)
        browser,_=self.as_user(self.reader)
        self.assertEqual(browser.get(SRC).json()["results"],[])
        self.assertEqual(browser.get(WATCH).json()["results"],[])
        self.assertEqual(browser.get(SRC+"/"+s["id"]).status_code,404)
        self.assertEqual(browser.get(WATCH+"/"+w["id"]).status_code,404)
        self.assertEqual(browser.get("/api/v1/catalog/items/"+s["id"]).status_code,404)
        self.assertEqual(browser.get("/api/v1/catalog/items/"+w["id"]).status_code,404)
        self.assertEqual(browser.get("/api/v1/catalog/items/"+s["id"]+"/evidence").status_code,404)
        self.assertEqual(browser.get("/api/v1/evidence/"+draft["id"]).status_code,404)
        self.assertEqual(browser.get("/api/v1/evidence/"+draft["id"]+"/download").status_code,404)
        self.assertEqual(self.review(SRC+"/"+s["id"],"r001","publish").status_code,200)
        # Public Watch may NOT publish until its original Source revision is public.
        w2=self.req(WATCH+"/"+w["id"],{
            "expected_revision":"r001","sources":[{"id":s["id"],"revision":"r002"}]},
            method="PATCH")
        self.assertEqual(w2.status_code,200,w2.content)
        self.assertEqual(self.review(WATCH+"/"+w["id"],"r002","submit").status_code,200)
        self.assertEqual(self.review(WATCH+"/"+w["id"],"r003","approve").status_code,200)
        self.assertEqual(self.review(WATCH+"/"+w["id"],"r004","publish").status_code,200)
        self.assertEqual(len(browser.get(SRC).json()["results"]),1)
        self.assertEqual(len(browser.get(WATCH).json()["results"]),1)
        self.assertEqual(browser.get(WATCH+"/"+w["id"]).json()["sources"][0]["revision"],"r002")
        self.assertEqual(browser.get(SRC+"/"+s["id"]+"/revisions/1").status_code,404)
        self.assertEqual(browser.get(WATCH+"/"+w["id"]+"/revisions/1").status_code,404)
        self.assertEqual(browser.get("/api/v1/evidence/"+draft["id"]+"/download").status_code,404)
        public_bytes=b"original publicly approved document\n"
        public=self.upload(s["id"],"r002",public_bytes)
        self.assertEqual(browser.get("/api/v1/catalog/items/"+s["id"]+"/evidence").json()
                         ["results"][0]["id"],public["id"])
        self.assertEqual(b"".join(browser.get("/api/v1/evidence/"+public["id"]+
                    "/download").streaming_content),public_bytes)
        self.assertEqual(public["sha256"],hashlib.sha256(public_bytes).hexdigest())
        # Make Source internal again: linked published Watch is hidden fail-closed.
        self.assertEqual(self.review(SRC+"/"+s["id"],"r002","unpublish").status_code,200)
        self.assertEqual(browser.get(SRC).json()["results"],[])
        self.assertEqual(browser.get(WATCH).json()["results"],[])
        self.assertEqual(browser.get("/api/v1/evidence/"+public["id"]).status_code,404)

    def test_invalid_links_stale_revisions_invalid_urls_and_csrf_atomicity(self):
        s=self.source()
        w=self.entry()
        for data in [
            {"sources":[{"id":s["id"]},{"id":s["id"]}]},
            {"sources":[{"id":"src-nonexistent"}]},
            {"sources":[{"id":s["id"],"revision":"r999"}]},
            {"sources":[{"id":s["id"],"revision":"r01"}]},
        ]:
            with self.subTest(data=data):
                result=self.req(WATCH+"/"+w["id"],{"expected_revision":"r001",**data},
                                method="PATCH")
                self.assertEqual(result.status_code,400,result.content)
        self.assertEqual(WatchSourcePin.objects.count(),0)
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=w["id"]).count(),1)
        self.assertEqual(self.req(WATCH+"/"+w["id"],{"expected_revision":"r999",
              "properties":{"notes":"Stale"}},"PATCH").status_code,409)
        self.assertEqual(self.req(SRC,{"name":"Bad URL","properties":{
            "claim":"Claim","url":"javascript:alert(1)"}}).status_code,400)
        self.assertEqual(self.req(SRC,{"name":"Bad URL","properties":{
            "claim":"Claim","url":"https://user:pass@example.org/secret"}}).status_code,400)
        self.assertEqual(self.req(SRC,{"name":"Bad date","properties":{
            "claim":"Claim","published_on":"tomorrow"}}).status_code,400)
        self.assertEqual(self.req(WATCH,{"name":"Bad","properties":{
            "hypothesis":"A","visibility":"published"}}).status_code,400)
        no_csrf=Client(enforce_csrf_checks=True)
        no_csrf.force_login(self.editor)
        self.assertEqual(no_csrf.post(SRC,json.dumps({"name":"Try","properties":{
            "claim":"Secret"}}),content_type="application/json").status_code,403)
        reader,token=self.as_user(self.reader)
        self.assertEqual(self.req(SRC,{"name":"Reader try","properties":{
            "claim":"Cannot"}} ,browser=reader,csrf=token).status_code,403)
        self.assertEqual(self.review(WATCH+"/"+w["id"],"r001","publish").status_code,400)
        no_revision=self.browser.post("/api/v1/catalog/items/"+s["id"]+"/evidence/upload",{
            "file":SimpleUploadedFile("unversioned.txt",b"no precise revision"),
        },HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(no_revision.status_code,400)

    def test_cannot_publish_watch_pinned_to_internal_source_and_no_implicit_repin(self):
        source=self.source()
        w=self.entry(links=[{"id":source["id"]}])
        self.assertEqual(self.review(WATCH+"/"+w["id"],"r001","submit").status_code,200)
        self.assertEqual(self.review(WATCH+"/"+w["id"],"r002","approve").status_code,200)
        refused=self.review(WATCH+"/"+w["id"],"r003","publish")
        self.assertEqual(refused.status_code,400,refused.content)
        self.assertEqual(self.browser.get(WATCH+"/"+w["id"]).json()["revision"],"r003")
        self.assertEqual(self.review(SRC+"/"+source["id"],"r001","publish").status_code,200)
        # Still linked to originally internal source r001: publication blocked.
        self.assertEqual(self.review(WATCH+"/"+w["id"],"r003","publish").status_code,400)
        relink=self.req(WATCH+"/"+w["id"],{"expected_revision":"r003",
              "sources":[{"id":source["id"],"revision":"r002"}]},"PATCH")
        self.assertEqual(relink.status_code,200,relink.content)
        self.assertEqual(self.review(WATCH+"/"+w["id"],"r004","publish").status_code,200)
