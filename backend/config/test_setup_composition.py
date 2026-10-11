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


if __name__ == "__main__":
    unittest.main()
