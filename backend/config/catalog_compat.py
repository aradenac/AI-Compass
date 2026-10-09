"""Read-only, type-agnostic compatibility classification; never rewrites JSONB."""
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


# Explicit metadata-only projections: no defaults, renaming, conversion or DB write.
# A missing adapter always stays "outdated"; the registry does not invent one.
SAFE_READ_ADAPTERS = {("model", 1, 2): lambda properties: dict(properties)}
SUPPORTED_MODEL_VERSIONS = frozenset({1, 2})
READABLE_STATES = frozenset({"current", "outdated", "migration_available"})


def _schema_errors(schema, properties):
    try:
        validator = Draft202012Validator(schema)
        validator.check_schema(schema)
        return sorted(validator.iter_errors(properties), key=lambda err: (str(err.path), err.message))
    except (SchemaError, TypeError, ValueError) as exc:
        return [str(exc)]


def _field_path(error):
    if isinstance(error, str):
        return "schema"
    return ".".join(str(segment) for segment in error.absolute_path) or "properties"


def classify(type_slug, schema_type, source_version, properties, versions):
    """All statuses are derived from registry + original fields, without mutation.

    versions: mapping[int, JSON Schema] resolved from ObjectTypeVersion for the type.
    The caller also checks schema_type to reject mismatched revision/type FKs.
    """
    base = {
        "status": "unsupported", "read_only": True,
        "source_schema_version": source_version,
        "current_schema_version": (max(set(versions).intersection(SUPPORTED_MODEL_VERSIONS))
                                   if type_slug == "model" and set(versions).intersection(SUPPORTED_MODEL_VERSIONS)
                                   else max(versions) if versions else None),
        "unknown_fields": [], "missing_fields": [], "null_fields": [],
        "incompatible_fields": [], "reason": None,
    }
    if schema_type != type_slug:
        base["reason"] = "Revision references a schema for a different object type"
        return base
    if type_slug == "model" and source_version not in SUPPORTED_MODEL_VERSIONS:
        base["reason"] = "Model schema version is not supported by this application"
        return base
    source_schema = versions.get(source_version)
    if not isinstance(source_schema, dict):
        base["reason"] = "Original schema definition is not available"
        return base
    if not isinstance(properties, dict):
        base["status"] = "invalid"
        base["reason"] = "Original properties are not a JSON object"
        return base
    known = source_schema.get("properties", {})
    if not isinstance(known, dict):
        base["status"] = "invalid"
        base["reason"] = "Registered property definitions are malformed"
        return base
    base["unknown_fields"] = sorted(key for key in properties if key not in known)
    base["missing_fields"] = sorted(key for key in known if key not in properties)
    base["null_fields"] = sorted(key for key, value in properties.items() if value is None)
    source_errors = _schema_errors(source_schema, properties)
    if source_errors:
        base["status"] = "invalid"
        base["incompatible_fields"] = sorted({_field_path(error) for error in source_errors})
        base["reason"] = "Original data does not conform to its pinned schema"
        return base
    newest = base["current_schema_version"]
    if source_version == newest:
        base.update(status="current", read_only=False)
        return base
    if source_version > newest:
        base["reason"] = "Future schema version cannot be interpreted"
        return base
    adapter = SAFE_READ_ADAPTERS.get((type_slug, source_version, newest))
    if adapter is None:
        base.update(status="outdated", read_only=False, reason="No registered compatibility projection")
        return base
    projected = adapter(properties)
    if not isinstance(projected, dict):
        base.update(status="needs_review", reason="Compatibility projection is not an object")
        return base
    projection_errors = _schema_errors(versions[newest], projected)
    if projection_errors:
        base.update(
            status="needs_review", read_only=True,
            incompatible_fields=sorted({_field_path(error) for error in projection_errors}),
            reason="Some original properties are incompatible with the current schema; manual review required",
        )
    else:
        base.update(
            status="migration_available", read_only=False,
            reason="A non-mutating compatibility projection is available; no upgrade is performed",
        )
    return base


def registry_for_types(type_slugs):
    """Use batched registry lookup; supports future registered types without new API code."""
    from .models import ObjectTypeVersion
    result = {type_slug: {} for type_slug in type_slugs}
    for version in ObjectTypeVersion.objects.filter(type_slug__in=type_slugs):
        result.setdefault(version.type_slug, {})[version.version] = version.json_schema
    return result


def compatibility_for_revision(item, revision, registry=None):
    if revision is None:
        return classify(item.type_slug, None, None, None, {})
    all_versions = registry if registry is not None else registry_for_types([item.type_slug])[item.type_slug]
    return classify(
        item.type_slug, revision.schema_version.type_slug,
        revision.schema_version.version, revision.properties, all_versions,
    )
