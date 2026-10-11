"""Pure deterministic tests runnable without Django or a database."""
import unittest

from config.setup_composition import compose, SetupCompositionError


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.a = ("gui-install", "r001")
        self.b = ("gui-integrate", "r002")
        self.snapshots = {
            self.a: {"name": "Install", "properties": {"text": "Install"}},
            self.b: {"name": "Integrate", "properties": {"url": "https://example.test"}},
        }
        self.recipe = {"modules": [
            {"id": self.b[0], "revision": self.b[1],
             "requires": [{"id": self.a[0], "revision": self.a[1]}]},
            {"id": self.a[0], "revision": self.a[1]},
        ], "required": ["os", "model"]}

    def test_orders_dependencies_once(self):
        result = compose(self.recipe, self.snapshots, {"os": "linux", "model": "m1"})
        self.assertTrue(result["ready"])
        self.assertEqual([s["id"] for s in result["sections"]],
                         ["gui-install", "gui-integrate"])

    def test_missing_revision_fails_closed(self):
        result = compose(self.recipe, {self.b: self.snapshots[self.b]},
                         {"os": "linux", "model": "m1"})
        self.assertFalse(result["ready"])
        self.assertIn("revision_not_found", [x["kind"] for x in result["missing"]])

    def test_wrong_environment_not_silently_accepted(self):
        self.recipe["modules"][0]["applies_to"] = {"os": "windows"}
        result = compose(self.recipe, self.snapshots, {"os": "linux", "model": "m1"})
        self.assertFalse(result["ready"])
        self.assertIn("inapplicable", [x["kind"] for x in result["missing"]])

    def test_unfilled_configuration_rejected(self):
        result = compose(self.recipe, self.snapshots, {"os": "linux"})
        self.assertFalse(result["ready"])
        self.assertIn({"kind": "configuration", "field": "model"}, result["missing"])

    def test_cycle_rejected(self):
        self.recipe["modules"][1]["requires"] = [
            {"id": self.b[0], "revision": self.b[1]}]
        with self.assertRaisesRegex(SetupCompositionError, "Cyclic"):
            compose(self.recipe, self.snapshots, {"os": "linux", "model": "m1"})

    def test_pin_preserves_old_snapshot(self):
        before = compose(self.recipe, self.snapshots, {"os": "linux", "model": "m1"})
        other = dict(self.snapshots)
        other[("gui-install", "r002")] = {
            "name": "Updated", "properties": {"text": "Changed"}}
        after = compose(self.recipe, other, {"os": "linux", "model": "m1"})
        self.assertEqual(before, after)


    def test_environment_variants_are_explicit_and_exclusive(self):
        recipe={"required":["os"],"required_groups":["installation"],"modules":[
            {"id":self.a[0],"revision":self.a[1],"group":"installation",
             "applies_to":{"os":"linux"}},
            {"id":self.b[0],"revision":self.b[1],"group":"installation",
             "applies_to":{"os":"windows"}}]}
        result=compose(recipe,self.snapshots,{"os":"linux"})
        self.assertEqual([s["id"] for s in result["sections"]],[self.a[0]])
        self.assertTrue(result["ready"])
        none=compose(recipe,self.snapshots,{"os":"darwin"})
        self.assertFalse(none["ready"])
        self.assertIn({"kind":"missing_variant","group":"installation"},none["missing"])

    def test_overlapping_variants_never_silently_choose(self):
        recipe={"required_groups":["installation"],"modules":[
            {"id":self.a[0],"revision":self.a[1],"group":"installation"},
            {"id":self.b[0],"revision":self.b[1],"group":"installation"}]}
        result=compose(recipe,self.snapshots,{})
        self.assertFalse(result["ready"])
        self.assertIn({"kind":"ambiguous_variant","group":"installation"},result["missing"])

    def test_recipe_identity_mismatch_stops_resolution(self):
        recipe={"applies_to":{"model":"model-a"},"modules":[
            {"id":self.a[0],"revision":self.a[1]}]}
        result=compose(recipe,self.snapshots,{"model":"model-b"})
        self.assertEqual(result["missing"],[{"kind":"recipe_inapplicable"}])
        self.assertEqual(result["sections"],[])

    def test_invalid_graph_and_malformed_unpinned_dependencies(self):
        for spec in ({"modules":[{"id":self.a[0],"revision":"latest"}]},
                     {"modules":[{"id":self.a[0],"revision":"r001",
                                   "requires":[{"id":self.b[0]}]}]},
                     {"modules":[{"id":self.a[0],"revision":"r001",
                                   "group":[]}]}):
            with self.subTest(spec=spec):
                with self.assertRaises(SetupCompositionError):
                    compose(spec,self.snapshots,{})


    def test_dependency_cannot_silently_select_an_incompatible_variant(self):
        spec={"required_groups":["installation"],"modules":[
            {"id":self.a[0],"revision":self.a[1],"group":"installation",
             "applies_to":{"os":"windows"}},
            {"id":self.b[0],"revision":self.b[1],"requires":[
                {"id":self.a[0],"revision":self.a[1]}]}]}
        result=compose(spec,self.snapshots,{"os":"linux"})
        self.assertFalse(result["ready"])
        self.assertIn("inapplicable",[m["kind"] for m in result["missing"]])


if __name__ == "__main__":
    unittest.main()
