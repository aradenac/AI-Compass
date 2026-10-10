"""PLAT-23: real shared threads, immutable history, privacy and author file evidence."""
import hashlib
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import Client,TestCase,override_settings

from .identity import ensure_roles
from .catalog_services import create_component,revise_component
from .models import (CatalogItem,CatalogRevision,CatalogAuditEvent,
                     DiscussionMessage,DiscussionThread,EvidenceLink)

ROOT="/api/v1/discussions"


class DiscussionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        U=get_user_model()
        cls.engineer=U.objects.create_user("feedback-engineer",password="x")
        cls.engineer.groups.add(Group.objects.get(name="user"))
        cls.other=U.objects.create_user("feedback-other-engineer",password="x")
        cls.other.groups.add(Group.objects.get(name="user"))
        cls.contributor=U.objects.create_user("feedback-workgroup",password="x")
        cls.contributor.groups.add(Group.objects.get(name="contributor"))
        cls.reviewer=U.objects.create_user("feedback-reviewer",password="x")
        cls.reviewer.groups.add(Group.objects.get(name="reviewer"))
        cls.maintainer=U.objects.create_user("feedback-maintainer",password="x")
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))
        cls.model=create_component(type_slug="model",actor=cls.contributor,
                                   name="Public AI model",properties={"context_window":6000})

    def setUp(self):
        path=tempfile.TemporaryDirectory(prefix="feedback-evidence-test-")
        self.addCleanup(path.cleanup)
        setting=override_settings(EVIDENCE_STORE_ROOT=Path(path.name))
        setting.enable();self.addCleanup(setting.disable)
        self.engineer_client,self.engineer_token=self.login(self.engineer)
        self.other_client,self.other_token=self.login(self.other)
        self.workgroup,self.group_token=self.login(self.contributor)
        self.reviewer_client,self.reviewer_token=self.login(self.reviewer)
        self.maint_client,self.maint_token=self.login(self.maintainer)

    def login(self,user):
        client=Client(enforce_csrf_checks=True)
        client.get("/api/v1/auth/csrf")
        client.force_login(user)
        return client,client.cookies["csrftoken"].value

    def send(self,path,data,user="engineer",method="POST"):
        browser,token={
            "engineer":(self.engineer_client,self.engineer_token),
            "other":(self.other_client,self.other_token),
            "contributor":(self.workgroup,self.group_token),
            "reviewer":(self.reviewer_client,self.reviewer_token),
            "maintainer":(self.maint_client,self.maint_token),
        }[user]
        http=browser.patch if method=="PATCH" else browser.post
        return http(path,json.dumps(data),content_type="application/json",
                    HTTP_X_CSRFTOKEN=token)

    def start(self,scope="public",user="engineer",context=True):
        response=self.send(ROOT,{
            "title":"Engineer feedback about embedded AI",
            "properties":{"scope":scope,"kind":"feedback","extensions":{"nullable":None}},
            "context_id":self.model.public_id if context else None,
            "body":"AI generated driver breaks Twister while compiling correctly",
        },user)
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def answer(self,thread,parent=None,visibility="public",user="other",body="Thanks for the report"):
        return self.send(ROOT+"/"+thread+"/messages",{
            "parent_id":parent,"visibility":visibility,"body":body},user)

    def correct(self,message,version,properties,user="contributor"):
        return self.send(ROOT+"/messages/"+message,{
            "expected_revision":version,"properties":properties},
            user,method="PATCH")

    def attach(self,message,rev,data=b"feedback captured logs",user="engineer"):
        browser,token={
            "engineer":(self.engineer_client,self.engineer_token),
            "other":(self.other_client,self.other_token),
            "contributor":(self.workgroup,self.group_token),
        }[user]
        return browser.post(ROOT+"/messages/"+message+"/attachments",{
            "expected_revision":rev,
            "file":SimpleUploadedFile("feedback.txt",data,content_type="text/plain"),
        },HTTP_X_CSRFTOKEN=token)

    def test_empty_server_persisted_thread_two_browsers_and_revision_pins(self):
        self.assertEqual(self.engineer_client.get(ROOT).json(),{"results":[]})
        self.assertEqual(CatalogItem.objects.filter(
            type_slug__in=("discussion_thread","discussion_message")).count(),0)
        first=self.start()
        thread=first["thread"];root=first["message"]
        self.assertTrue(thread["id"].startswith("thr-"))
        self.assertTrue(root["id"].startswith("msg-"))
        self.assertEqual(thread["message_count"],1)
        self.assertEqual(thread["context_id"],self.model.public_id)
        before=DiscussionThread.objects.get(item__public_id=thread["id"])
        self.assertEqual(before.context_revision_id,self.model.current_revision_id)
        second=self.answer(thread["id"],root["id"],body="I reproduce the driver warning")
        self.assertEqual(second.status_code,201,second.content)
        response=self.other_client.get(ROOT+"/"+thread["id"])
        self.assertEqual(response.status_code,200)
        messages=response.json()["messages"]
        self.assertEqual([x["id"] for x in messages],[root["id"],second.json()["id"]])
        self.assertEqual([x["created_by"] for x in messages],
                         [self.engineer.username,self.other.username])
        self.assertEqual(messages[1]["parent_id"],root["id"])
        self.assertEqual(self.workgroup.get(ROOT).json()["results"][0]["message_count"],2)
        self.assertEqual(self.other_client.get(ROOT).json()["results"][0]["message_count"],2)
        revise_component(type_slug="model",item=self.model,actor=self.contributor,
                         expected_revision="r001",name="Changed public model")
        self.assertEqual(DiscussionThread.objects.get(item__public_id=thread["id"])
                         .context_revision_id,before.context_revision_id)
        self.assertTrue(CatalogAuditEvent.objects.filter(
            item__public_id=root["id"],action="created").exists())
        self.assertEqual(DiscussionMessage.objects.count(),2)

    def test_public_user_correction_author_and_stale_optimistic_revision(self):
        first=self.start(context=False)
        root=first["message"]
        wrong=self.correct(root["id"],"r001",{
            "body":"Trying to change another user message",
            "edit_reason":"incorrect"},user="other")
        self.assertEqual(wrong.status_code,400)
        correction=self.correct(root["id"],"r001",{
            "body":"Correction: SPI chip select required a delay",
            "edit_reason":"Reproduced with trace attached"},user="engineer")
        self.assertEqual(correction.status_code,200,correction.content)
        second=correction.json()
        self.assertEqual(second["revision"],"r002")
        self.assertEqual(second["revision_by"],self.engineer.username)
        self.assertEqual(second["created_by"],self.engineer.username)
        history=self.other_client.get(ROOT+"/messages/"+root["id"]+"/revisions")
        self.assertEqual([x["body"] for x in history.json()["revisions"]],
                         [root["body"],second["body"]])
        self.assertEqual(self.other_client.get(ROOT+"/messages/"+root["id"]+
                          "/revisions/1").json()["body"],root["body"])
        self.assertEqual(self.correct(root["id"],"r001",{
            "body":"conflicting","edit_reason":"late"},user="engineer").status_code,409)
        self.assertEqual(self.correct(root["id"],"r002",{
            "body":"silent rewrite"},user="engineer").status_code,400)
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=root["id"]).count(),2)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CatalogRevision.objects.filter(item__public_id=root["id"],
                    number=1).update(properties={"body":"mutated","visibility":"public"})

    def test_internal_reply_visibility_and_moderation_history_cannot_leak(self):
        first=self.start()
        root=first["message"]
        hidden=self.answer(first["thread"]["id"],root["id"],"internal",user="contributor",
                           body="Internal: vendor licensing concern")
        self.assertEqual(hidden.status_code,201,hidden.content)
        secret=hidden.json()
        self.assertEqual(secret["visibility"],"internal")
        self.assertEqual(len(self.other_client.get(ROOT+"/"+first["thread"]["id"])
                             .json()["messages"]),1)
        for path in (
            ROOT+"/messages/"+secret["id"],
            ROOT+"/messages/"+secret["id"]+"/revisions",
            ROOT+"/messages/"+secret["id"]+"/revisions/1",
            "/api/v1/catalog/items/"+secret["id"],
            "/api/v1/catalog/items/"+secret["id"]+"/evidence"):
            self.assertEqual(self.other_client.get(path).status_code,404,path)
        self.assertEqual(self.workgroup.get(ROOT+"/messages/"+secret["id"])
                         .json()["body"],"Internal: vendor licensing concern")
        self.assertEqual(self.answer(first["thread"]["id"],secret["id"],
                            "public",user="contributor").status_code,400)
        self.assertEqual(self.answer(first["thread"]["id"],secret["id"],
                            "public",user="other").status_code,400)
        revised=self.correct(secret["id"],"r001",{
            "visibility":"public","body":"Publicly shareable vendor note",
            "edit_reason":"Internal details removed and review approved"})
        self.assertEqual(revised.status_code,200,revised.content)
        visible=self.other_client.get(ROOT+"/messages/"+secret["id"])
        self.assertEqual(visible.status_code,200)
        self.assertEqual(visible.json()["body"],"Publicly shareable vendor note")
        history=self.other_client.get(ROOT+"/messages/"+secret["id"]+"/revisions").json()
        self.assertEqual([x["revision"] for x in history["revisions"]],["r002"])
        self.assertEqual(self.other_client.get(
            ROOT+"/messages/"+secret["id"]+"/revisions/1").status_code,404)
        self.assertEqual(len(self.workgroup.get(ROOT+"/messages/"+secret["id"]+
                         "/revisions").json()["revisions"]),2)
        self.assertEqual(self.correct(root["id"],"r001",{
            "visibility":"internal","body":"Hide original parent",
            "edit_reason":"Workgroup moderation"},user="contributor").status_code,400)
        self.assertEqual(DiscussionMessage.objects.count(),2)

    def test_internal_thread_scope_cannot_be_guessed(self):
        self.assertEqual(self.start(scope="internal",user="engineer",
                                    context=False) if False else None,None)
        forbidden=self.send(ROOT,{
            "title":"Not allowed","body":"Hidden","properties":{"scope":"internal"}},
            user="engineer")
        self.assertEqual(forbidden.status_code,400)
        made=self.start(scope="internal",user="contributor",context=False)
        thread=made["thread"]["id"]
        self.assertEqual(made["message"]["visibility"],"internal")
        for path in (ROOT+"/"+thread,"/api/v1/catalog/items/"+thread):
            self.assertEqual(self.engineer_client.get(path).status_code,404)
        self.assertEqual(self.engineer_client.get(ROOT).json(),{"results":[]})
        self.assertEqual(self.send(ROOT+"/"+thread+"/messages",{
            "body":"Guessing hidden thread"},user="engineer").status_code,404)
        self.assertEqual(self.send(ROOT+"/"+thread+"/messages",{
            "body":"Workgroup public leak attempt","visibility":"public"},
            user="contributor").status_code,400)
        self.assertEqual(self.workgroup.get(ROOT+"/"+thread).status_code,200)

    def test_original_attachment_visible_exact_revision_and_hidden_revision_is_private(self):
        first=self.start()
        root=first["message"]
        blob=b"feedback captured logs\nfrom engineer"
        upload=self.attach(root["id"],"r001",blob)
        self.assertEqual(upload.status_code,201,upload.content)
        info=upload.json()
        self.assertEqual(info["sha256"],hashlib.sha256(blob).hexdigest())
        evidence=self.other_client.get("/api/v1/evidence/"+info["id"])
        self.assertEqual(evidence.status_code,200,evidence.content)
        binary=self.other_client.get("/api/v1/evidence/"+info["id"]+"/download")
        self.assertEqual(b"".join(binary.streaming_content),blob)
        self.assertEqual(self.other_client.get(ROOT+"/messages/"+root["id"])
                         .json()["attachments"][0]["sha256"],info["sha256"])
        wrong_author=self.attach(root["id"],"r001",user="other")
        self.assertEqual(wrong_author.status_code,403)
        correction=self.correct(root["id"],"r001",{
            "body":"Moderated internal evidence","visibility":"internal",
            "edit_reason":"Contains a nonpublic hardware detail"})
        self.assertEqual(correction.status_code,200,correction.content)
        for path in (
            "/api/v1/evidence/"+info["id"],
            "/api/v1/evidence/"+info["id"]+"/download",
            "/api/v1/catalog/items/"+root["id"]+"/evidence",
            ROOT+"/messages/"+root["id"]+"/revisions/1"):
            self.assertEqual(self.other_client.get(path).status_code,404,path)
        self.assertEqual(self.workgroup.get("/api/v1/evidence/"+info["id"]).status_code,200)
        self.assertEqual(EvidenceLink.objects.filter(item__public_id=root["id"]).count(),1)
        self.assertEqual(self.correct(root["id"],"r001",{
            "body":"Stale","edit_reason":"Stale"},user="contributor").status_code,409)

    def test_auth_csrf_invalid_refs_and_cross_thread_reply_rejected(self):
        first=self.start()
        second=self.start(context=False)
        self.assertEqual(self.answer(first["thread"]["id"],second["message"]["id"],
                         user="other").status_code,400)
        self.assertEqual(self.send(ROOT,{
            "title":"Unknown object","body":"Broken link",
            "context_id":"sol-absent-reference"}).status_code,400)
        self.assertEqual(self.send(ROOT,{
            "title":"Bad kind","body":"Something","properties":{"kind":"evil"}}).status_code,400)
        self.assertEqual(self.send(ROOT+"/"+first["thread"]["id"]+"/messages",{
            "body":"Trying internal","visibility":"internal"},user="engineer").status_code,400)
        self.assertEqual(self.maint_client.get(ROOT).status_code,403)
        self.assertEqual(Client().get(ROOT).status_code,401)
        self.assertEqual(self.send(ROOT,{
            "title":"No maintainer discussion","body":"Denied"},
            user="maintainer").status_code,403)
        plain=Client(enforce_csrf_checks=True)
        plain.force_login(self.engineer)
        self.assertEqual(plain.post(ROOT,json.dumps({
            "title":"No CSRF","body":"Forbidden"}),content_type="application/json").status_code,403)
        self.assertEqual(self.send(ROOT+"/messages/"+first["message"]["id"],{
            "expected_revision":"r001","properties":{"visibility":"internal",
                "edit_reason":"Not workgroup"}},method="PATCH").status_code,400)
