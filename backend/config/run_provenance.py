"""FUT-09: non-destructive version references for original Run setup.

Documentary completeness is NOT a Run completion gate. FUT-10 controls
publication eligibility separately; the original recorded evidence remains.
"""
from .setup_recipe_services import from_session
from .setup_composition import SetupCompositionError


def snapshot(session):
    """Source IDs/versions only; never copy credentials or large guide prose."""
    try:
        guide=from_session(session)
        seen=set()
        pins=[]
        for entry in guide.get("sections", []):
            pair=(entry.get("id"),entry.get("revision"))
            if not all(isinstance(x,str) and x for x in pair) or pair in seen:
                continue
            seen.add(pair)
            pins.append({"id":pair[0],"revision":pair[1]})
        return {"guide":guide.get("recipe"),"module_pins":pins,
                "documentation_coverage":bool(guide.get("ready")),
                "missing_coverage":guide.get("missing",[]),
                "configuration":guide.get("configuration",{}),
                "deviations":guide.get("deviations",{})}
    except SetupCompositionError as exc:
        return {"guide":({"id":session.guide.public_id,
                          "revision":"r%03d" % session.guide_revision.number}
                         if session.guide_id else None),
                "module_pins":[],"documentation_coverage":False,
                "missing_coverage":[{"kind":"composition_unresolved",
                                     "detail":str(exc)}],
                "configuration":{},"deviations":{}}
