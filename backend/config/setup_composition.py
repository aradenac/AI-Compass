"""FUT-07 foundation: deterministic, fail-closed composition of pinned setup modules.

This resolver is deliberately storage-agnostic. Callers MUST load immutable
module revisions by exact ID before rendering; it never fetches external URLs.
"""
from collections.abc import Mapping


class SetupCompositionError(ValueError):
    pass


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
    entries = recipe.get("modules", [])
    if not isinstance(entries, list):
        raise SetupCompositionError("modules must be a list")
    missing, sections, seen, active = [], [], set(), set()
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

    def visit(key):
        if key in active:
            raise SetupCompositionError("Cyclic module dependency")
        if key in seen:
            return
        entry = lookup.get(key)
        if entry is None:
            missing.append({"kind": "dependency", "module": list(key)})
            return
        if not _matches(entry.get("applies_to", {}), configuration):
            missing.append({"kind": "inapplicable", "module": list(key)})
            return
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
            visit(ident)
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
    required = recipe.get("required", [])
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        raise SetupCompositionError("required must be a list of configuration keys")
    for key in required:
        if key not in configuration or configuration[key] in (None, ""):
            missing.append({"kind": "configuration", "field": key})
    return {"ready": not missing and bool(sections),
            "sections": sections, "missing": missing or (
                [] if sections else [{"kind": "no_modules"}])}
