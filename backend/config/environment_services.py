"""FUT-06: deliberately coarse Windows/Linux compatibility, separate from entitlement.

The projection accepts historical source revisions verbatim and never pretends
unknown metadata is either 'agnostic' or verified access. All group participants
share one environment under the initial policy; distributed execution is unknown.
"""
OS = ("windows", "linux")
DEPENDENT_TYPES = frozenset(("harness", "framework"))


class InvalidEnvironment(ValueError):
    pass


def validate_os(values, *, allow_missing=False):
    """Strictly typed, unique, nonempty normalized OS selection."""
    if values is None and allow_missing:
        return None
    if not isinstance(values, list) or not values or len(values) > 2:
        raise InvalidEnvironment("Choose Windows and/or Linux; an explicit empty OS set is invalid")
    if any(not isinstance(v, str) or v not in OS for v in values):
        raise InvalidEnvironment("Only windows and linux are supported")
    if len(set(values)) != len(values):
        raise InvalidEnvironment("Duplicate OS selection")
    return [v for v in OS if v in values]


def declared_os(properties):
    """Never convert missing, null, invalid, or [] legacy data into both OSs."""
    if not isinstance(properties, dict):
        return None
    try:
        return validate_os(properties.get("supported_os"))
    except InvalidEnvironment:
        return None


def validate_component_os(type_slug, properties):
    if type_slug not in DEPENDENT_TYPES:
        return
    if not isinstance(properties, dict):
        raise InvalidEnvironment("Catalog properties must be an object")
    declared = "supported_os" in properties
    # Historical draft/unknown metadata is explicitly incomplete and can still
    # be inspected; usable/published current records MUST make the assertion.
    usable = (properties.get("publication") == "published" or
              properties.get("status") in ("active", "usable", "supported", "enabled"))
    if declared or usable:
        validate_os(properties.get("supported_os"))
    # No implicit value for an older or unfinished draft.


def record_os(type_slug, properties):
    if type_slug not in DEPENDENT_TYPES:
        return {"status": "not_os_scoped", "supported_os": None}
    value = declared_os(properties)
    return {"status": "classified" if value else "unknown",
            "supported_os": value}


def compose(parts, available=None, *, topology="shared_os"):
    """Parts: exact pinned Harness/Framework {type,id,revision,properties}.

    Several participant Harnesses are intersected ONLY under same-machine
    (shared_os) topology; any distributed/unresolved topology stays unknown.
    A disjoint known pair remains unsupported even if a third part is unknown.
    """
    if topology != "shared_os":
        return {"status": "unknown_topology", "supported_os": None,
                "reason": "Distributed or unverified multi-machine OS topology is not classified"}
    if not isinstance(parts, list) or not parts:
        return {"status": "unknown", "supported_os": None,
                "reason": "No OS-dependent Harness or Framework selected"}
    intersection = set(OS)
    unknown = []
    sources = []
    for part in parts:
        if part["type"] not in DEPENDENT_TYPES:
            continue
        os_info = record_os(part["type"], part["properties"])
        sources.append(dict(type=part["type"], id=part["id"],
                            revision=part["revision"], **os_info))
        if os_info["supported_os"] is None:
            unknown.append(part["id"])
        else:
            intersection.intersection_update(os_info["supported_os"])
    if not sources:
        return {"status": "unknown", "supported_os": None,
                "reason": "No OS-dependent component in the configuration", "sources": []}
    if not intersection:
        return {"status": "unsupported_combination", "supported_os": [],
                "reason": "Harness/Framework common OS intersection is empty",
                "sources": sources}
    if unknown:
        return {"status": "unknown", "supported_os": None,
                "reason": "OS support not classified for " + ", ".join(unknown),
                "sources": sources}
    result = [v for v in OS if v in intersection]
    if available is None:
        return {"status": "unconfigured_user", "supported_os": result,
                "reason": "Set your Windows/Linux profile before prioritizing candidates",
                "sources": sources}
    profile = validate_os(available)
    matching = [v for v in result if v in profile]
    if matching:
        return {"status": "compatible", "supported_os": result, "matching_os": matching,
                "reason": "OS compatible only; entitlement and setup not verified",
                "sources": sources}
    return {"status": "other_os", "supported_os": result,
            "requires_os": result,
            "reason": "Interesting alternative requiring " + " or ".join(v.title() for v in result),
            "sources": sources}
