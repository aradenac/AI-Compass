"""FUT-07 foundation: deterministic, fail-closed composition of pinned setup modules.

This resolver is deliberately storage-agnostic. Callers MUST load immutable
module revisions by exact ID before rendering; it never fetches external URLs.
"""
from collections.abc import Mapping

# A resolver is not a certification of documentation or installation success.


class SetupCompositionError(ValueError):
    pass



def validate_recipe(recipe):
    """Validate bounded pinned recipe declarations before persisting them."""
    if not isinstance(recipe, Mapping):
        raise SetupCompositionError("recipe must be an object")
    if set(recipe) - {"modules", "required", "applies_to", "required_groups"}:
        raise SetupCompositionError("Unknown recipe fields")
    modules = recipe.get("modules", [])
    required = recipe.get("required", [])
    if not isinstance(modules, list) or len(modules) > 128:
        raise SetupCompositionError("modules must be a bounded list")
    if not isinstance(required, list) or len(required) > 64 or not all(
        isinstance(x, str) and 0 < len(x) <= 160 for x in required
    ):
        raise SetupCompositionError("required must contain configuration keys")
    overall = recipe.get("applies_to", {})
    if not isinstance(overall, Mapping) or len(overall)>64:
        raise SetupCompositionError("Invalid recipe applicability")
    for field in overall:
        if not isinstance(field, str) or not field:
            raise SetupCompositionError("Invalid recipe selector key")
    groups = recipe.get("required_groups", [])
    if not isinstance(groups, list) or len(groups)>64 or not all(
        isinstance(x, str) and 0 < len(x)<=120 for x in groups
    ) or len(groups)!=len(set(groups)):
        raise SetupCompositionError("Invalid required groups")
    keys = set()
    for module in modules:
        if not isinstance(module, Mapping) or set(module) - {
            "id", "revision", "requires", "applies_to", "group"
        }:
            raise SetupCompositionError("Invalid module declaration")
        group = module.get("group")
        if group is not None and (not isinstance(group, str) or not group or len(group)>120):
            raise SetupCompositionError("Invalid variant group")
        mid, rev = module.get("id"), module.get("revision")
        if not isinstance(mid, str) or not mid.startswith("gui-"):
            raise SetupCompositionError("Module must have a guide ID")
        if not isinstance(rev, str) or not (
            4 <= len(rev) <= 10 and rev.startswith("r") and rev[1:].isdigit()
        ):
            raise SetupCompositionError("Module must pin an exact revision")
        key = (mid, rev)
        if key in keys:
            raise SetupCompositionError("Duplicate module declaration")
        keys.add(key)
        selector = module.get("applies_to", {})
        if not isinstance(selector, Mapping) or len(selector) > 64:
            raise SetupCompositionError("Invalid applicability")
        dependencies = module.get("requires", [])
        if not isinstance(dependencies, list) or len(dependencies) > 128:
            raise SetupCompositionError("Invalid dependencies")
        for dep in dependencies:
            if not isinstance(dep, Mapping) or set(dep) != {"id", "revision"}:
                raise SetupCompositionError("Dependency must pin ID and revision")
            if not isinstance(dep["id"], str) or not dep["id"].startswith("gui-"):
                raise SetupCompositionError("Invalid dependency ID")
            if not isinstance(dep["revision"], str) or not (
                4 <= len(dep["revision"]) <= 10 and dep["revision"].startswith("r")
                and dep["revision"][1:].isdigit()
            ):
                raise SetupCompositionError("Invalid dependency revision")
    return recipe


def _matches(selector, environment):
    """A declared selector matches only explicitly equal configuration fields."""
    if not isinstance(selector, Mapping):
        raise SetupCompositionError("applicability must be an object")
    return all(key in environment and environment[key] == value
               for key, value in selector.items())


def compose(recipe, revisions, configuration):
    """Return ordered pinned sections and precise non-publishable readiness.

    recipe: {"modules": [{"id": "gui-...", "revision": "r001",
              "requires": [...], "applies_to": {...}}], "required": [...]}
    revisions: mapping of (public_id, revision) to immutable guide snapshots
    configuration: exact setup attributes, including version and OS when relevant
    """
    if not isinstance(recipe, Mapping) or not isinstance(revisions, Mapping):
        raise SetupCompositionError("Invalid recipe or revision store")
    if not isinstance(configuration, Mapping):
        raise SetupCompositionError("Exact configuration must be an object")
    validate_recipe(recipe)
    if not _matches(recipe.get("applies_to", {}), configuration):
        return {"ready": False, "sections": [],
                "missing": [{"kind": "recipe_inapplicable"}]}
    entries = recipe.get("modules", [])
    if not isinstance(entries, list):
        raise SetupCompositionError("modules must be a list")
    missing, sections, seen, active = [], [], set(), set()
    matched_groups = {}
    lookup = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise SetupCompositionError("module entry must be an object")
        key = (entry.get("id"), entry.get("revision"))
        if not all(isinstance(v, str) and v for v in key):
            raise SetupCompositionError("Every module must pin ID and revision")
        if key in lookup and lookup[key] != entry:
            raise SetupCompositionError("Conflicting declarations for pinned module")
        lookup[key] = entry

    def visit(key, *, required_dependency=False):
        if key in active:
            raise SetupCompositionError("Cyclic module dependency")
        if key in seen:
            return
        entry = lookup.get(key)
        if entry is None:
            missing.append({"kind": "dependency", "module": list(key)})
            return
        if not _matches(entry.get("applies_to", {}), configuration):
            # Unselected alternative variants are expected; ungrouped required
            # modules must instead report precise incompatibility.
            if required_dependency or not entry.get("group"):
                missing.append({"kind": "inapplicable", "module": list(key)})
            return
        group = entry.get("group")
        if group:
            prior = matched_groups.get(group)
            if prior is not None and prior != key:
                missing.append({"kind": "ambiguous_variant", "group": group})
                return
            matched_groups[group] = key
        active.add(key)
        requirements = entry.get("requires", [])
        if not isinstance(requirements, list):
            raise SetupCompositionError("requires must be a list")
        for dep in requirements:
            if not isinstance(dep, Mapping):
                raise SetupCompositionError("dependency must pin ID and revision")
            ident = (dep.get("id"), dep.get("revision"))
            if not all(isinstance(v, str) and v for v in ident):
                raise SetupCompositionError("dependency missing ID or revision")
            visit(ident, required_dependency=True)
        active.remove(key)
        snapshot = revisions.get(key)
        if not isinstance(snapshot, Mapping):
            missing.append({"kind": "revision_not_found", "module": list(key)})
            return
        props = snapshot.get("properties", {})
        if not isinstance(props, Mapping) or not any(
            isinstance(props.get(k), str) and props[k].strip() for k in ("text", "url")
        ):
            missing.append({"kind": "empty_module", "module": list(key)})
            return
        seen.add(key)
        sections.append({"id": key[0], "revision": key[1],
                         "name": snapshot.get("name", key[0]),
                         "text": props.get("text"), "url": props.get("url")})

    for entry in entries:
        visit((entry["id"], entry["revision"]))
    for group in recipe.get("required_groups", []):
        if group not in matched_groups:
            missing.append({"kind": "missing_variant", "group": group})
    required = recipe.get("required", [])
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        raise SetupCompositionError("required must be a list of configuration keys")
    for key in required:
        if key not in configuration or configuration[key] in (None, ""):
            missing.append({"kind": "configuration", "field": key})
    return {"ready": not missing and bool(sections),
            "sections": sections, "missing": missing or (
                [] if sections else [{"kind": "no_modules"}])}
