"""FUT-07 revision-pinned rendering and authorization regression tests."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from .identity import ensure_roles
from .setup_guide_services import create, revise

URL = "/api/v1/guides/render"


class RenderRecipeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_roles()
        cls.editor = get_user_model().objects.create_user(
            "recipe-editor", password="long-test-password-2026")
        cls.editor.groups.add(Group.objects.get(name="contributor"))
        cls.maint = get_user_model().objects.create_user(
            "recipe-maint", password="long-test-password-2026")
        cls.maint.groups.add(Group.objects.get(name="data-maintainer"))

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.editor)
        module = create(actor=self.editor, name="Install Cline",
                        properties={"text": "Install version one"})
        self.module = module.public_id
        recipe = create(actor=self.editor, name="Full setup",
                        properties={"text": "Overview", "recipe": {
                            "required": ["os", "harness"],
                            "modules": [{"id": self.module, "revision": "r001",
                                         "applies_to": {"os": "ubuntu"}}]}})
        self.recipe = recipe.public_id

    def render(self, **overrides):
        data = {"guide_id": self.recipe, "revision": "r001",
                "configuration": {"os": "ubuntu", "harness": "cline"}}
        data.update(overrides)
        return self.client.post(URL, data=json.dumps(data),
                                content_type="application/json")

    def test_exact_revision_and_history_stays_pinned(self):
        first = self.render()
        self.assertEqual(first.status_code, 200, first.content)
        self.assertTrue(first.json()["ready"])
        self.assertEqual(first.json()["sections"][0]["text"], "Install version one")
        revise(actor=self.editor, public_id=self.module,
               expected_revision="r001", properties={"text": "Install version two"})
        after = self.render()
        self.assertEqual(first.json(), after.json())

    def test_missing_os_is_incomplete(self):
        result = self.render(configuration={"harness": "cline"})
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["ready"])

    def test_invalid_and_missing_revisions(self):
        self.assertEqual(self.render(revision="latest").status_code, 400)
        self.assertEqual(self.render(revision="r999").status_code, 404)
        self.assertEqual(self.render(guide_id="mod-invalid").status_code, 400)

    def test_maintenance_only_denied(self):
        self.client.force_login(self.maint)
        self.assertEqual(self.render().status_code, 403)

    def test_recipe_retirement_creates_new_revision_and_preserves_original(self):
        original=self.client.get("/api/v1/guides/"+self.recipe).json()
        self.assertIn("recipe", original["properties"])
        response=self.client.patch("/api/v1/guides/"+self.recipe,
            data=json.dumps({"expected_revision":"r001",
                             "properties":{"recipe":None}}),
            content_type="application/json")
        self.assertEqual(response.status_code,200,response.content)
        self.assertNotIn("recipe",response.json()["guide"]["properties"])
        self.assertEqual(response.json()["guide"]["revision"],"r002")
        old=self.client.get("/api/v1/guides/"+self.recipe+"/revisions/1")
        self.assertEqual(old.status_code,200,old.content)
        self.assertIn("recipe",old.json()["properties"])
        historical=self.render(revision="r001")
        self.assertEqual(historical.status_code,200,historical.content)
        self.assertTrue(historical.json()["ready"])

