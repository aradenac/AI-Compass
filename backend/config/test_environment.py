"""FUT-06: real Server OS profiles and pinned composite OS compatibility."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, transaction
from django.test import Client, TestCase

from .catalog_services import create_component, revise_component
from .catalog_schemas import InvalidModel
from .environment_services import compose, record_os, validate_component_os, InvalidEnvironment
from .identity import ensure_roles
from .models import UserEnvironmentRevision, CatalogRevision

P = "/api/v1/profile/environment"
C = "/api/v1/environment/compatibility"


class EnvironmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        u = get_user_model()
        cls.alice=u.objects.create_user("os-alice",password="test-not-a-real-secret")
        cls.alice.groups.add(Group.objects.get(name="contributor"))
        cls.bob=u.objects.create_user("os-bob",password="test-not-a-real-secret")
        cls.bob.groups.add(Group.objects.get(name="user"))
        cls.maint=u.objects.create_user("os-maint",password="test-not-a-real-secret")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.windows=create_component(type_slug="harness",actor=cls.alice,
            name="Windows tool",properties={"supported_os":["windows"],"status":"active"})
        cls.linux=create_component(type_slug="harness",actor=cls.alice,
            name="Linux tool",properties={"supported_os":["linux"],"status":"active"})
        cls.both=create_component(type_slug="harness",actor=cls.alice,
            name="Cross-platform tool",properties={"supported_os":["windows","linux"],
                                                   "publication":"published"})
        cls.framework=create_component(type_slug="framework",actor=cls.alice,
            name="Linux workflow",properties={"supported_os":["linux"],"status":"active"})
        cls.legacy=create_component(type_slug="framework",actor=cls.alice,
            name="Unclassified legacy draft",properties={"details":"No OS researched"})
        cls.model=create_component(type_slug="model",actor=cls.alice,
            name="Model without OS",properties={})
        cls.provider=create_component(type_slug="provider",actor=cls.alice,
            name="Provider without OS",properties={})

    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.token=self.client.cookies["csrftoken"].value
        self.client.force_login(self.alice)

    def send(self,url,payload,verb="PATCH",csrf=True):
        cb=self.client.patch if verb=="PATCH" else self.client.post
        return cb(url,data=json.dumps(payload),content_type="application/json",
                  **({"HTTP_X_CSRFTOKEN":self.token} if csrf else {}))

    def selection(self,*items):
        return {"components":[{
            "type":item.type_slug,"id":item.public_id,
            "revision_id":str(item.current_revision_id)
        } for item in items]}

    def test_self_service_without_user_agent_inference_or_role_grants(self):
        unknown=self.client.get(P,HTTP_USER_AGENT="Windows NT 10.0").json()
        self.assertIsNone(unknown["available_os"])
        self.assertFalse(unknown["configured"])
        self.assertEqual(unknown["entitlement_status"],"not_verified_by_os")
        self.assertIsNone(unknown["revision"])
        self.assertEqual(self.send(P,{"expected_revision":None,
                    "available_os":["windows"]},csrf=False).status_code,403)
        self.assertEqual(self.send(P,{"expected_revision":None,
                    "available_os":[]}).status_code,400)
        self.assertEqual(self.send(P,{"expected_revision":None,
                    "available_os":["macos"]}).status_code,400)
        self.assertEqual(self.send(P,{"expected_revision":None,
                    "available_os":["windows","windows"]}).status_code,400)
        self.assertEqual(UserEnvironmentRevision.objects.count(),0)
        first=self.send(P,{"expected_revision":None,
                   "available_os":["windows"]})
        self.assertEqual(first.status_code,200,first.content)
        self.assertEqual(first.json()["revision"],"r001")
        self.assertEqual(self.send(P,{"expected_revision":None,
                    "available_os":["linux"]}).status_code,409)
        second=self.send(P,{"expected_revision":"r001",
                   "available_os":["linux","windows"]})
        self.assertEqual(second.status_code,200,second.content)
        self.assertEqual(second.json()["available_os"],["windows","linux"])
        self.assertEqual(second.json()["revision"],"r002")
        same=self.send(P,{"expected_revision":"r002",
                   "available_os":["windows","linux"]})
        self.assertEqual(same.json()["revision"],"r002")
        third=self.send(P,{"expected_revision":"r002",
                   "available_os":["linux"]})
        self.assertEqual(third.json()["revision"],"r003")
        versions=self.client.get(P+"/revisions").json()["revisions"]
        self.assertEqual([v["available_os"] for v in versions],
                         [["windows"],["windows","linux"],["linux"]])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                UserEnvironmentRevision.objects.filter(user=self.alice,number=1).update(
                    available_os=["linux"])
        self.client.force_login(self.bob)
        self.assertIsNone(self.client.get(P).json()["available_os"])
        self.assertEqual(self.client.get(P+"/revisions").json()["revisions"],[])
        self.assertEqual(self.send(P,{"expected_revision":None,
                    "available_os":["windows"]}).status_code,200)
        self.assertEqual(UserEnvironmentRevision.objects.filter(user=self.bob).count(),1)
        self.assertFalse(self.bob.has_perm("auth.business_write"))
        self.client.force_login(self.maint)
        self.assertEqual(self.client.get(P).status_code,403)
        self.assertEqual(self.send(P,{"expected_revision":None,
                    "available_os":["linux"]}).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(P).status_code,401)

    def test_catalog_os_mandatory_for_usable_only_and_history_immutable(self):
        self.assertEqual(record_os("harness",self.both.current_revision.properties)["status"],
                         "classified")
        self.assertIsNone(record_os("framework",self.legacy.current_revision.properties)["supported_os"])
        self.assertEqual(record_os("model",{})["status"],"not_os_scoped")
        self.assertEqual(record_os("provider",{})["status"],"not_os_scoped")
        for props in ({"status":"active"},{"publication":"published"},
                      {"supported_os":[]},{"supported_os":["bsd"]},
                      {"supported_os":["windows","windows"]}):
            with self.assertRaises(InvalidEnvironment):
                validate_component_os("harness",props)
            with self.assertRaises(InvalidModel):
                create_component(type_slug="harness",actor=self.alice,
                                 name="Invalid published tool",properties=props)
        with self.assertRaises(InvalidModel):
            revise_component(item=self.legacy,type_slug="framework",actor=self.alice,
                 expected_revision="r001",properties={"status":"active"})
        updated=revise_component(item=self.legacy,type_slug="framework",actor=self.alice,
            expected_revision="r001",properties={"status":"active",
                                                    "supported_os":["linux"]})
        self.assertEqual(updated.current_revision.number,2)
        self.assertNotIn("supported_os",updated.revisions.get(number=1).properties)
        self.assertEqual(updated.revisions.get(number=2).properties["supported_os"],["linux"])
        self.assertEqual(self.client.get("/api/v1/catalog/framework/"+updated.public_id+
                                         "/revisions/1").json()["os_compatibility"]["status"],"unknown")
        data=self.client.get("/api/v1/catalog/harness").json()["results"]
        source=next(x for x in data if x["id"]==self.both.public_id)
        self.assertEqual(source["os_compatibility"]["supported_os"],["windows","linux"])
        self.assertEqual(source["revision_id"],str(self.both.current_revision_id))
        self.assertEqual(self.client.get(P).json()["entitlement_status"],"not_verified_by_os")

    def test_composed_intersection_unknown_disjoint_and_other_os(self):
        request=self.selection(self.both,self.framework)
        unknown=self.send(C,request,"POST")
        self.assertEqual(unknown.status_code,200,unknown.content)
        self.assertEqual(unknown.json()["status"],"unconfigured_user")
        self.assertEqual(unknown.json()["supported_os"],["linux"])
        self.send(P,{"expected_revision":None,"available_os":["windows"]})
        other=self.send(C,request,"POST").json()
        self.assertEqual(other["status"],"other_os")
        self.assertEqual(other["requires_os"],["linux"])
        self.assertEqual(other["individual_entitlement"],"not_verified")
        self.assertEqual(other["enterprise_accessibility"],"separate_catalog_metadata")
        self.assertEqual(other["setup_guide"],"not_verified")
        self.assertEqual(self.send(C,self.selection(self.windows,self.framework),
                                   "POST").json()["status"],"unsupported_combination")
        self.assertEqual(self.send(C,self.selection(self.legacy,self.both),
                                   "POST").json()["status"],"unknown")
        self.assertEqual(self.send(C,self.selection(self.windows),"POST").json()["status"],
                         "compatible")
        # All framework participants must share an OS; it is NOT enough for
        # just one participant Harness to be locally supported.
        self.assertEqual(self.send(C,self.selection(self.both,self.windows,self.framework),
                                   "POST").json()["status"],"unsupported_combination")
        selected=self.selection(self.both,self.framework)
        selected["topology"]="distributed_unknown"
        self.assertEqual(self.send(C,selected,"POST").json()["status"],"unknown_topology")
        bad=self.selection(self.both)
        bad["components"][0]["revision_id"]=str(self.framework.current_revision_id)
        self.assertEqual(self.send(C,bad,"POST").status_code,400)
        bad=self.selection(self.both)
        bad["components"][0]["type"]="provider"
        self.assertEqual(self.send(C,bad,"POST").status_code,400)
        invalid=self.selection(self.both)
        invalid["components"][0]["type"]=[]
        self.assertEqual(self.send(C,invalid,"POST").status_code,400)
        invalid=self.selection(self.both)
        invalid["components"][0]["revision_id"]="not-a-uuid"
        self.assertEqual(self.send(C,invalid,"POST").status_code,400)
        self.assertEqual(self.send(C,self.selection(self.both),"POST",csrf=False).status_code,403)
        self.client.force_login(self.maint)
        self.assertEqual(self.send(C,request,"POST").status_code,403)

    def test_prior_revision_remains_pinned_after_catalog_narrowing(self):
        self.send(P,{"expected_revision":None,"available_os":["windows"]})
        pinned=self.selection(self.both)
        self.assertEqual(self.send(C,pinned,"POST").json()["status"],"compatible")
        old_revision=self.both.current_revision_id
        revise_component(item=self.both,type_slug="harness",actor=self.alice,
           expected_revision="r001",properties={"status":"active",
                                                  "supported_os":["linux"]})
        self.both.refresh_from_db()
        self.assertEqual(self.send(C,pinned,"POST").json()["status"],"compatible")
        latest=self.selection(self.both)
        self.assertEqual(latest["components"][0]["revision_id"],
                         str(self.both.current_revision_id))
        self.assertNotEqual(old_revision,self.both.current_revision_id)
        self.assertEqual(self.send(C,latest,"POST").json()["status"],"other_os")
