"""FUT-08: immutable Task/configuration scoped planning and measured evidence separation."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from .catalog_services import create_component, revise_component
from .identity import ensure_roles
from .task_services import create_task
from .test_case_services import create as create_case
from .models import CampaignSnapshot, BenchmarkSession, SessionSolutionPin

BASE="/api/v1/campaigns"


class EvaluationMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        User=get_user_model()
        cls.writer=User.objects.create_user("matrix-writer",password="test")
        cls.writer.groups.add(Group.objects.get(name="contributor"))
        cls.reader=User.objects.create_user("matrix-reader",password="test")
        cls.reader.groups.add(Group.objects.get(name="user"))
        cls.maint=User.objects.create_user("matrix-maint",password="test")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))
        cls.task=create_task(actor=cls.writer,name="Driver integration")
        cls.task2=create_task(actor=cls.writer,name="Requirements refactoring")
        cls.cases=[create_case(actor=cls.writer,task_id=cls.task.item.public_id,
                              name="Driver test "+str(i),
                              properties={"objective":"Build driver","dod":"Tests pass"})
                   for i in (1,2)]
        cls.case2=create_case(actor=cls.writer,task_id=cls.task2.item.public_id,
                              name="Requirements test",properties={
                                  "objective":"Review requirements","dod":"Diff accepted"})
        cls.components={kind:create_component(type_slug=kind,actor=cls.writer,
                              name=kind+" chosen",properties={})
                        for kind in ("model","provider","harness")}

    def setUp(self):
        self.client=Client(enforce_csrf_checks=True)
        self.client.get("/api/v1/auth/csrf")
        self.csrf=self.client.cookies["csrftoken"].value
        self.client.force_login(self.writer)
        self.camp=self.call(BASE,{"name":"Matrix campaign","objective":"Compare candidates",
            "mode":"task_centred","task_id":self.task.item.public_id,
            "test_case_ids":[x.item.public_id for x in self.cases]})
        self.assertEqual(self.camp.status_code,201,self.camp.content)
        self.camp=self.camp.json()
        self.path=BASE+"/"+self.camp["id"]

    def call(self,path,body,method="POST",csrf=True):
        handler={"POST":self.client.post,"PATCH":self.client.patch}[method]
        return handler(path,json.dumps(body),content_type="application/json",
                       **({"HTTP_X_CSRFTOKEN":self.csrf} if csrf else {}))

    def matrix(self):
        response=self.client.get(self.path+"/matrix")
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def operation(self,payload,expected=None):
        response=self.call(self.path+"/matrix/edit",{
            "expected_revision":expected or self.camp["revision"],
            "operation":payload},"PATCH")
        if response.status_code==200:self.camp=response.json()["campaign"]
        return response

    def add(self,task=None,tests=None,label="Setup",components=None):
        return self.operation({"action":"add_configuration",
            "task_id":(task or self.task).item.public_id,
            "label":label,
            "component_ids":components or {k:v.public_id for k,v in self.components.items()},
            "test_case_ids":tests or [x.item.public_id for x in self.cases]})

    def test_six_default_selected_cells_and_distinct_coverage(self):
        for i in range(3):
            result=self.add(label="Setup "+str(i))
            self.assertEqual(result.status_code,200,result.content)
        matrix=self.matrix()
        self.assertEqual(matrix["summary"]["candidates"],6)
        self.assertEqual(matrix["summary"]["pending"],6)
        self.assertEqual(matrix["summary"]["measured_runs"],0)
        self.assertEqual(matrix["summary"]["experiment_coverage"]["evaluated"],0)
        self.assertTrue(all(x["status"]=="pending" for x in matrix["cells"]))
        self.assertEqual(len(set(x["id"] for x in matrix["cells"])),6)
        self.assertEqual(matrix["revision"],"r004")

    def test_deselection_waiver_reason_reinstatement_and_history(self):
        self.add()
        first=self.matrix()["cells"][0]["id"]
        second=self.matrix()["cells"][1]["id"]
        not_selected=self.operation({"action":"decide","evaluation_id":first,
                                     "decision":"not_selected"})
        self.assertEqual(not_selected.status_code,200,not_selected.content)
        reject=self.operation({"action":"decide","evaluation_id":first,
                               "decision":"waived","reason":"Not promising"})
        self.assertEqual(reject.status_code,400)
        missing=self.operation({"action":"decide","evaluation_id":second,
                                "decision":"waived"})
        self.assertEqual(missing.status_code,400)
        waived=self.operation({"action":"decide","evaluation_id":second,
                               "decision":"waived","reason":"Risk outweighs benefit"})
        self.assertEqual(waived.status_code,200,waived.content)
        matrix=self.matrix()
        self.assertEqual(matrix["summary"]["not_selected"],1)
        self.assertEqual(matrix["summary"]["waived"],1)
        self.assertEqual(matrix["summary"]["evaluated"],0)
        self.assertTrue(matrix["summary"]["full_plan_complete"])
        self.assertEqual(next(x for x in matrix["cells"] if x["id"]==second)
                         ["waiver"]["actor"],self.writer.username)
        revived=self.operation({"action":"decide","evaluation_id":second,
                                "decision":"selected"})
        self.assertEqual(revived.status_code,200,revived.content)
        self.assertEqual(self.matrix()["summary"]["pending"],1)
        old=self.client.get(self.path+"/matrix?revision=r003")
        self.assertEqual(old.status_code,200)
        self.assertEqual(next(x for x in old.json()["cells"] if x["id"]==second)
                         ["decision"],"selected")
        hist=self.client.get(self.path+"/matrix?revision=r004")
        self.assertEqual(next(x for x in hist.json()["cells"] if x["id"]==second)
                         ["decision"],"waived")

    def test_two_tasks_no_global_cartesian_and_reopen(self):
        self.add(label="Driver")
        result=self.add(task=self.task2,tests=[self.case2.item.public_id],
                        label="Requirements")
        self.assertEqual(result.status_code,200,result.content)
        matrix=self.matrix()
        self.assertEqual(matrix["summary"]["candidates"],3)
        self.assertEqual({x["task_id"] for x in matrix["configurations"]},
                         {self.task.item.public_id,self.task2.item.public_id})
        self.assertEqual(len(self.camp["test_case_ids"]),3)
        self.assertEqual(len({x["configuration_id"] for x in matrix["cells"]}),2)
        original=self.camp["revision"]
        self.assertEqual(self.call(self.path+"/actions/start",
            {"expected_revision":original}).status_code,200)
        self.camp=self.client.get(self.path).json()
        blocked=self.call(self.path+"/actions/close",{
            "expected_revision":self.camp["revision"]})
        self.assertEqual(blocked.status_code,409,blocked.content)
        closed=self.call(self.path+"/actions/close",{
            "expected_revision":self.camp["revision"],"partial_review":True})
        self.assertEqual(closed.status_code,200,closed.content)
        self.assertEqual(closed.json()["campaign"]["properties"]["review_scope"],"partial")
        self.camp=closed.json()["campaign"]
        reopened=self.call(self.path+"/actions/reopen",{
            "expected_revision":self.camp["revision"]})
        self.assertEqual(reopened.status_code,200,reopened.content)
        self.camp=reopened.json()["campaign"]
        self.assertEqual(self.matrix()["summary"]["candidates"],3)
        self.assertEqual(self.client.get(self.path+"/matrix?revision="+original)
                         .json()["summary"]["candidates"],3)

    def test_add_cases_proposes_to_same_task_peers_without_rewriting_decisions(self):
        first=self.add(tests=[self.cases[0].item.public_id],label="A")
        self.assertEqual(first.status_code,200,first.content)
        self.add(tests=[self.cases[0].item.public_id],label="B")
        cfg=self.matrix()["configurations"][0]["id"]
        res=self.operation({"action":"add_cases","configuration_id":cfg,
                            "test_case_ids":[self.cases[1].item.public_id]})
        self.assertEqual(res.status_code,200,res.content)
        self.assertEqual(self.matrix()["summary"]["candidates"],4)

    def test_exact_session_pin_stale_revision_csrf_and_permissions(self):
        self.add()
        cell=self.matrix()["cells"][0]
        other=self.matrix()["cells"][1]
        stale=self.operation({"action":"decide","evaluation_id":cell["id"],
                              "decision":"not_selected"},"r001")
        self.assertEqual(stale.status_code,409)
        self.assertEqual(self.operation({"action":"decide","evaluation_id":cell["id"],
            "decision":"waived","reason":"Stop"}).status_code,200)
        self.assertEqual(self.operation({"action":"decide","evaluation_id":cell["id"],
            "decision":"waived","reason":"Stop"}).status_code,400)
        started=self.call(self.path+"/actions/start",{"expected_revision":self.camp["revision"]})
        self.assertEqual(started.status_code,200,started.content)
        self.camp=started.json()["campaign"]
        ses_path=self.path+"/sessions"
        forbidden=self.call(ses_path,{"test_case_id":cell["test_case_id"],
            "evaluation_id":cell["id"],"component_ids":{
                k:v.public_id for k,v in self.components.items()}})
        self.assertEqual(forbidden.status_code,400)
        # Later catalog revision must not replace the planned technical revisions.
        item=self.components["model"]
        revise_component(type_slug="model",item=item,actor=self.writer,
                         expected_revision="r001",properties={"extra":"new"})
        cfg=next(x for x in self.matrix()["configurations"]
                 if x["id"]==other["configuration_id"])
        session=self.call(ses_path,{"test_case_id":other["test_case_id"],
            "evaluation_id":other["id"],"component_ids":cfg["component_ids"]})
        self.assertEqual(session.status_code,201,session.content)
        self.assertEqual(session.json()["evaluation_id"],other["id"])
        self.assertEqual(self.matrix()["summary"]["in_progress"],1)
        original_revision=cfg["component_revision_ids"]["model"]
        pin=SessionSolutionPin.objects.get(session__public_id=session.json()["id"])
        self.assertEqual(str(pin.model_revision_id),original_revision)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(self.path+"/matrix").status_code,200)
        self.assertEqual(self.operation({"action":"decide","evaluation_id":other["id"],
                         "decision":"not_selected"}).status_code,403)
        self.client.force_login(self.maint)
        self.assertEqual(self.client.get(self.path+"/matrix").status_code,403)
        self.client.force_login(self.writer)
        self.assertEqual(self.call(self.path+"/matrix/edit",{
           "expected_revision":self.camp["revision"],
           "operation":{"action":"decide","evaluation_id":other["id"],
                         "decision":"not_selected"}},"PATCH",csrf=False).status_code,403)

    def test_untrusted_plan_and_wrong_task_rejected(self):
        self.assertEqual(self.call(self.path,{"expected_revision":"r001",
             "properties":{"matrix_plan":{"cells":[]}}},"PATCH").status_code,400)
        wrong=self.add(task=self.task2,tests=[self.cases[0].item.public_id])
        self.assertEqual(wrong.status_code,400)
        self.assertEqual(self.matrix()["configured"],False)
    def test_failed_dod_closed_run_counts_as_evaluated_and_repeatable(self):
        self.add(tests=[self.cases[0].item.public_id])
        cell=self.matrix()["cells"][0]
        started=self.call(self.path+"/actions/start",{
            "expected_revision":self.camp["revision"]})
        self.assertEqual(started.status_code,200,started.content)
        self.camp=started.json()["campaign"]
        cfg=self.matrix()["configurations"][0]
        session=self.call(self.path+"/sessions",{
            "test_case_id":cell["test_case_id"],
            "evaluation_id":cell["id"],"component_ids":cfg["component_ids"]})
        self.assertEqual(session.status_code,201,session.content)
        ident=session.json()["id"]
        interaction=self.call("/api/v1/sessions/"+ident+"/interactions",{
            "expected_revision":"r001","type":"human_prompt",
            "content":"Implement driver and run tests","human_minutes":3})
        self.assertEqual(interaction.status_code,200,interaction.content)
        closed=self.call("/api/v1/sessions/"+ident+"/close",{
            "expected_revision":"r002","outcome":"failed",
            "quality_score":20,"quality_evaluation":"Tests fail",
            "information_utility_score":35,"information_utility_evaluation":"Partial",
            "tokens_count":None,"tokens_multiplier":1,
            "cost_mode":"unknown","cost_eur":None,
            "human_review_minutes":3,"human_correction_minutes":2,
            "produced_outputs":"Driver build logs and compiler errors"})
        self.assertEqual(closed.status_code,201,closed.content)
        self.assertEqual(closed.json()["outcome"],"failed")
        counted=self.matrix()
        self.assertEqual(counted["summary"]["evaluated"],1)
        self.assertEqual(counted["summary"]["pending"],0)
        self.assertEqual(counted["summary"]["measured_runs"],1)
        self.assertEqual(counted["cells"][0]["runs"][0]["outcome"],"failed")
        repeated=self.call(self.path+"/sessions",{
            "test_case_id":cell["test_case_id"],
            "evaluation_id":cell["id"],"component_ids":cfg["component_ids"]})
        self.assertEqual(repeated.status_code,201,repeated.content)
        self.assertEqual(self.matrix()["summary"]["measured_runs"],1)
        self.assertEqual(self.matrix()["summary"]["evaluated"],1)
    def test_framework_group_is_a_composite_matrix_column_not_fake_individual(self):
        framework=create_component(type_slug="framework",actor=self.writer,
                                   name="Collaborative workflow",properties={})
        fresh=self.call(BASE,{"name":"Framework Matrix","objective":"Test collaborating agents",
            "mode":"task_centred","task_id":self.task.item.public_id,
            "test_case_ids":[self.cases[0].item.public_id],
            "framework_id":framework.public_id,
            "participants":[{"label":"Builder","role":"Implementation",
                "configuration_version":"1",
                "component_ids":{k:v.public_id for k,v in self.components.items()},
                "settings":{"review":None}},{
                "label":"Reviewer","role":"Quality",
                "configuration_version":"1",
                "component_ids":{k:v.public_id for k,v in self.components.items()},
                "settings":{"verification":True}}]})
        self.assertEqual(fresh.status_code,201,fresh.content)
        self.camp=fresh.json();self.path=BASE+"/"+self.camp["id"]
        participants=[x["id"] for x in self.camp["participants"]]
        saved=self.operation({"action":"add_configuration","kind":"framework",
            "task_id":self.task.item.public_id,"label":"Builder → Reviewer",
            "participant_ids":participants,
            "test_case_ids":[self.cases[0].item.public_id]})
        self.assertEqual(saved.status_code,200,saved.content)
        cfg=self.matrix()["configurations"][0]
        self.assertEqual(cfg["kind"],"framework")
        self.assertEqual(len(cfg["participant_snapshots"]),2)
        start=self.call(self.path+"/actions/start",
            {"expected_revision":self.camp["revision"]})
        self.assertEqual(start.status_code,200,start.content)
        self.camp=start.json()["campaign"]
        cell=self.matrix()["cells"][0]
        refused=self.call(self.path+"/sessions",{
            "test_case_id":cell["test_case_id"],"evaluation_id":cell["id"],
            "selected_participant_ids":[participants[0]]})
        self.assertEqual(refused.status_code,400)
        accepted=self.call(self.path+"/sessions",{
            "test_case_id":cell["test_case_id"],"evaluation_id":cell["id"],
            "selected_participant_ids":participants})
        self.assertEqual(accepted.status_code,201,accepted.content)
        self.assertIsNone(accepted.json()["individual_setup"])
        self.assertEqual(accepted.json()["selected_participant_ids"],participants)
        self.assertEqual(self.matrix()["summary"]["in_progress"],1)
