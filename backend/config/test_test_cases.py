"""PLAT-10: durable Server Test Cases, concurrent forks, immutable revisions and role boundaries."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, close_old_connections, connections, transaction
from django.test import Client, TestCase, TransactionTestCase

from .catalog_compat import compatibility_for_revision
from .identity import ensure_roles
from .models import (CatalogItem, CatalogRevision, CatalogAuditEvent,
                     ObjectTypeVersion, TestCase as TestCaseRow)
from .task_services import create_task, update_task
from .test_case_services import create, fork, revise

URL="/api/v1/test-cases"


class TestCaseApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User=get_user_model()
        cls.user=User.objects.create_user(username="tc-editor",password="password-long-safe-2026")
        cls.user.groups.add(Group.objects.get(name="contributor"))
        cls.reader=User.objects.create_user(username="tc-reader",password="password-long-safe-2026")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maintainer=User.objects.create_user(username="tc-maintainer",password="password-long-safe-2026")
        cls.maintainer.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.user,name="Develop Ethernet driver",
                             properties={"future_task_field":{"do_not_touch":None}})

    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.token=self.client.cookies["csrftoken"].value
        self.client.force_login(self.user)

    def submit(self,path,payload,method="POST",csrf=True):
        func=self.client.post if method=="POST" else self.client.patch
        return func(path,data=json.dumps(payload),content_type="application/json",
                    **({"HTTP_X_CSRFTOKEN":self.token} if csrf else {}))

    def new(self):
        response=self.submit(URL,{"task_id":self.task.item.public_id,
            "name":"TC1 Basic driver",
            "properties":{"objective":"Implement SPI driver","inputs":"Repository commit A",
              "constraints":"Zephyr 4","expected_outputs":"Driver and tests",
              "dod":"Build and integration tests pass","vendor_extension":{"nullable":None}}})
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def test_new_edit_history_and_source_task_moving(self):
        self.assertEqual(self.client.get(URL).json()["results"],[])
        created=self.new()
        self.assertTrue(created["id"].startswith("tcs-"))
        self.assertEqual(created["case_version"],"1.0")
        self.assertIsNone(created["fork_parent_id"])
        self.assertEqual(created["revision"],"r001")
        original_id=created["revision_id"]
        self.assertEqual(created["task_revision_at_creation"],str(self.task.item.current_revision_id))
        self.assertEqual(self.client.get(URL+"?task_id="+self.task.item.public_id).json()["results"][0]["id"],created["id"])
        updated=self.submit(URL+"/"+created["id"],{"expected_revision":"r001",
            "name":"TC1 Error handling",
            "properties":{"objective":"Add fault injection","unknown_roundtrip":{"nested":[None,1]}}},method="PATCH")
        self.assertEqual(updated.status_code,200,updated.content)
        self.assertEqual(updated.json()["revision"],"r002")
        self.assertEqual(updated.json()["properties"]["vendor_extension"],{"nullable":None})
        self.assertEqual(self.client.get(URL+"/"+created["id"]+"/revisions/1").json()["name"],"TC1 Basic driver")
        history=self.client.get(URL+"/"+created["id"]+"/revisions").json()["revisions"]
        self.assertEqual([r["revision"] for r in history],["r001","r002"])
        self.assertEqual(history[0]["revision_id"],original_id)
        self.assertEqual(history[0]["properties"]["objective"],"Implement SPI driver")
        self.assertEqual(self.submit(URL+"/"+created["id"],{"expected_revision":"r001",
            "name":"Lost update"},method="PATCH").status_code,409)
        _,modified=update_task(public_id=self.task.item.public_id,actor=self.user,
                               expected_revision="r001",name="Renamed SPI/Ethernet driver")
        self.assertTrue(modified)
        # Reparent the task too: Test Cases must follow permanent FK identity,
        # not mutable taxonomy ancestry or labels.
        new_parent=create_task(actor=self.user,name="Embedded software domain")
        _, moved=update_task(public_id=self.task.item.public_id,actor=self.user,
                             expected_revision="r002",
                             parent_id_marker=new_parent.item.public_id)
        self.assertTrue(moved)
        loaded=Client();loaded.force_login(self.reader)
        from_disk=loaded.get(URL+"/"+created["id"]).json()
        self.assertEqual(from_disk["task_id"],self.task.item.public_id)
        self.assertEqual(from_disk["task_revision_at_creation"],created["task_revision_at_creation"])
        self.assertEqual(from_disk["revision"],"r002")
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=created["id"]).count(),2)

    def test_fork_children_and_grandchild_do_not_modify_parent(self):
        original=self.new()
        source=original["revision_id"]
        props={"inputs":"Alternate driver requirements"}
        first=self.submit(URL+"/"+original["id"]+"/fork",
                          {"expected_parent_revision":"r001","properties":props})
        second=self.submit(URL+"/"+original["id"]+"/fork",
                           {"expected_parent_revision":"r001",
                            "name":"TC2 Alternate setup"})
        self.assertEqual(first.status_code,201,first.content)
        self.assertEqual(second.status_code,201,second.content)
        a,b=first.json(),second.json()
        self.assertEqual((a["case_version"],b["case_version"]),("1.0.1","1.0.2"))
        self.assertNotEqual(a["id"],b["id"])
        self.assertEqual(a["fork_parent_id"],original["id"])
        self.assertEqual(a["fork_source_revision_id"],source)
        self.assertEqual(a["properties"]["vendor_extension"],{"nullable":None})
        self.assertEqual(a["task_id"],original["task_id"])
        grandchild=self.submit(URL+"/"+a["id"]+"/fork",{"expected_parent_revision":"r001"})
        self.assertEqual(grandchild.status_code,201,grandchild.content)
        self.assertEqual(grandchild.json()["case_version"],"1.0.1.1")
        self.assertEqual(grandchild.json()["fork_parent_id"],a["id"])
        self.assertEqual(self.client.get(URL+"/"+original["id"]).json()["revision"],"r001")
        self.assertEqual(CatalogRevision.objects.filter(item__public_id=original["id"]).count(),1)
        self.assertEqual(CatalogAuditEvent.objects.filter(action="forked").count(),3)

    def test_fork_snapshot_stays_at_exact_parent_revision_and_validates_stale_etag(self):
        initial=self.new()
        stale=self.submit(URL+"/"+initial["id"],{"expected_revision":"r001",
                      "properties":{"dod":"New acceptance criteria"}},method="PATCH")
        self.assertEqual(stale.status_code,200)
        refused=self.submit(URL+"/"+initial["id"]+"/fork",{"expected_parent_revision":"r001"})
        self.assertEqual(refused.status_code,409)
        child=self.submit(URL+"/"+initial["id"]+"/fork",{"expected_parent_revision":"r002"})
        self.assertEqual(child.status_code,201)
        self.assertEqual(child.json()["fork_source_revision_id"],stale.json()["revision_id"])
        self.assertEqual(child.json()["properties"]["dod"],"New acceptance criteria")

    def test_csrf_permissions_invalid_linkage_and_immutable_lineage(self):
        self.assertEqual(self.submit(URL,{"task_id":self.task.item.public_id,
             "name":"T","properties":{"objective":"Do","dod":"Done"}},csrf=False).status_code,403)
        self.assertEqual(self.submit(URL,{"task_id":"tsk-unknown-task-id",
             "name":"T","properties":{"objective":"Do","dod":"Done"}}).status_code,400)
        self.assertEqual(self.submit(URL,{"task_id":self.task.item.public_id,
             "name":"T","properties":{"objective":"Do"}}).status_code,400)
        self.assertEqual(self.submit(URL,{"task_id":self.task.item.public_id,
             "name":"T","properties":{"objective":"Do","dod":"Done"},
             "fork_parent_id":"tcs-fake"}).status_code,400)
        created=self.new()
        row=TestCaseRow.objects.get(item__public_id=created["id"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TestCaseRow.objects.filter(pk=row.pk).update(case_version="123.0")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TestCaseRow.objects.filter(pk=row.pk).delete()
        reader=Client();reader.force_login(self.reader)
        self.assertEqual(reader.get(URL).status_code,200)
        self.assertEqual(reader.post(URL,data="{}",content_type="application/json").status_code,403)
        maint=Client();maint.force_login(self.maintainer)
        self.assertEqual(maint.get(URL).status_code,403)
        self.assertEqual(maint.get(URL+"/"+created["id"]).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(URL).status_code,401)

    def test_case_can_reference_shared_evidence_upload_endpoint(self):
        import tempfile
        from pathlib import Path
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        created=self.new()
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(EVIDENCE_STORE_ROOT=Path(temp)):
                payload={"file":SimpleUploadedFile("prompt.txt",b"Original challenge prompt",content_type="text/plain"),
                        "revision":"r001","source":"manual:bench","provenance":json.dumps({"test_case_input":True})}
                response=self.client.post("/api/v1/catalog/items/"+created["id"]+"/evidence/upload",
                                          data=payload,HTTP_X_CSRFTOKEN=self.token)
                self.assertEqual(response.status_code,201,response.content)
                refs=self.client.get("/api/v1/catalog/items/"+created["id"]+"/evidence").json()["results"]
                self.assertEqual(len(refs),1)
                self.assertEqual(refs[0]["revision"],"r001")


class ConcurrentForkTests(TransactionTestCase):
    reset_sequences=False

    def test_two_simultaneous_forks_allocate_unique_versions(self):
        ensure_roles()
        actor=get_user_model().objects.create_user(
            username="tc-thread-creator",password="password-long-safe-2026")
        task=create_task(actor=actor,name="Driver concurrency task")
        parent=create(actor=actor,task_id=task.item.public_id,name="Original TC",
                      properties={"objective":"Driver","dod":"Unit tested"})
        barrier=Barrier(2)
        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                child=fork(actor=actor,parent_id=parent.item.public_id,
                           expected_parent_revision="r001")
                return child.item.public_id,child.case_version
            finally:
                # ThreadPool workers may keep idle test DB connections alive.
                # Force-close them before Django drops the disposable database.
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures=[executor.submit(worker) for _ in range(2)]
            out=[f.result(timeout=35) for f in futures]
        self.assertEqual({version for _,version in out},{"1.0.1","1.0.2"})
        self.assertEqual(len({ident for ident,_ in out}),2)
        parent.item.refresh_from_db()
        self.assertEqual(parent.item.current_revision.number,1)
        self.assertEqual(TestCaseRow.objects.filter(fork_parent=parent).count(),2)
