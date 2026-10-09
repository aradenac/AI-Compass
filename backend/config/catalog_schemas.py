"""Validate instance payloads against immutable schema definitions from PostgreSQL."""
from jsonschema import Draft202012Validator


class InvalidModel(ValueError):
    pass


def validate_model(display_name, properties, schema):
    if not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 160:
        raise InvalidModel("name must be a nonempty string of at most 160 characters")
    if not isinstance(properties, dict):
        raise InvalidModel("properties must be a JSON object")
    # The registry schema captures known property semantics while allowing
    # new/unknown keys; these must be preserved unmodified across revisions.
    validator = Draft202012Validator(schema)
    failures = sorted(validator.iter_errors(properties), key=lambda error: str(error.path))
    if failures:
        first = failures[0]
        field = ".".join(str(x) for x in first.path) or "properties"
        raise InvalidModel(f"{field}: {first.message}")
    return display_name.strip()
