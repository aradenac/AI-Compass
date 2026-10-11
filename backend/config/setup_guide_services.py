"""PLAT-11: independently reusable Setup Guides; never imported from Demo.

Current guide revisions are read/edited using the same immutable CatalogItem
and CatalogRevision engine as Models. A URL is metadata only: NEVER fetched.
"""
from urllib.parse import urlsplit

from django.db import transaction

from .activity_services import record_catalog_event
from .catalog_compat import compatibility_for_revision
from .catalog_schemas import validate_model, InvalidModel
from .catalog_services import (create_component, catalog_schema_for,
                               RevisionConflict, SchemaWriteBlocked)
from .models import CatalogItem, CatalogRevision

TYPE="setup_guide"
MAX_FIELDS=frozenset({"text","url","description","publication"})


def _validate(properties, schema):
    if not isinstance(properties,dict):
        raise InvalidModel("properties must be a JSON object")
    result=dict(properties)
    # Empty text or URL is not a resource; allow clearing an old optional
    # field without storing a broken link. Unknown JSON fields round-trip.
    for key in ("text","url"):
        if result.get(key) == "":
            result.pop(key)
    if not any(isinstance(result.get(k),str) and result[k].strip()
               for k in ("text","url")):
        raise InvalidModel("Guide requires procedure text, an HTTP(S) URL, or both")
    if "text" in result and (
            not isinstance(result["text"],str) or not result["text"].strip()
    ):
        raise InvalidModel("Guide text must not be whitespace-only")
    if "url" in result:
        url=result["url"]
        if not isinstance(url,str) or any(c.isspace() or ord(c)<32 for c in url):
            raise InvalidModel("Guide URL cannot contain whitespace or control characters")
        try:
            parts=urlsplit(url)
            port=parts.port
        except (TypeError,ValueError) as exc:
            raise InvalidModel("Malformed guide URL") from exc
        if (parts.scheme not in ("http","https") or not parts.hostname or
                parts.username is not None or parts.password is not None or
                port == 0 or url.startswith(("http:///","https:///"))):
            raise InvalidModel("Guide URL must be absolute HTTP(S) without embedded credentials")
    if "recipe" in result:
        from .setup_composition import SetupCompositionError, validate_recipe
        try:
            validate_recipe(result["recipe"])
        except SetupCompositionError as exc:
            raise InvalidModel(str(exc)) from exc
    return result


def create(*,actor,name,properties):
    schema=catalog_schema_for(TYPE)
    if schema is None:
        raise InvalidModel("Registered Setup Guide schema is unavailable")
    props=_validate(properties,schema)
    validate_model(name,props,schema.json_schema)
    return create_component(type_slug=TYPE,actor=actor,name=name,properties=props)


def revise(*,actor,public_id,expected_revision,name=None,properties=None):
    with transaction.atomic():
        item=CatalogItem.objects.select_for_update(of=("self",)).select_related(
            "current_revision__schema_version").get(public_id=public_id,type_slug=TYPE)
        old=item.current_revision
        if old is None or expected_revision!=f"r{old.number:03d}":
            raise RevisionConflict("Guide changed; reload before saving")
        state=compatibility_for_revision(item,old)
        if state["read_only"] or old.schema_version.version!=1:
            raise SchemaWriteBlocked(state)
        props=dict(old.properties)
        if properties is not None:
            if not isinstance(properties,dict):
                raise InvalidModel("properties must be a JSON object")
            props.update(properties)
        props=_validate(props,old.schema_version.json_schema)
        display=validate_model(name if name is not None else old.display_name,
                               props,old.schema_version.json_schema)
        if props==old.properties and display==old.display_name:
            return item,False
        rev=CatalogRevision.objects.create(
            item=item,number=old.number+1,schema_version=old.schema_version,
            display_name=display,properties=props,created_by=actor)
        item.current_revision=rev
        item.save(update_fields=["current_revision"])
        record_catalog_event(item=item,revision=rev,actor=actor,action="revised")
        return item,True
