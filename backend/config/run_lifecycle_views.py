"""Authenticated, CSRF-protected Run correction/withdrawal, private history."""
from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .auth_views import capability, json_no_store
from .catalog_views import read_payload
from .catalog_services import RevisionConflict
from . import run_lifecycle_services as svc


@require_GET
@capability("business_read")
@never_cache
def history(request, public_id):
    if request.GET:
        return json_no_store({"error":"invalid_filter"},400)
    if not (request.user.has_perm("auth.business_write") or
            request.user.has_perm("auth.publication_review")):
        raise Http404("Historical private Run evidence restricted")
    run=svc.lookup(public_id)
    if run is None:
        raise Http404("Unknown Run")
    return json_no_store({"id":public_id,"current":svc.state(run),
                          "revisions":svc.history(run)})


@require_POST
@csrf_protect
@capability("publication_review")
@never_cache
def action(request, public_id, action):
    if svc.lookup(public_id) is None:
        raise Http404("Unknown Run")
    if action not in ("corrected","withdrawn"):
        return json_no_store({"error":"invalid_action"},400)
    try:
        data=read_payload(request)
        permitted={"expected_revision","reason"}
        if action=="corrected":
            permitted|={"metrics_patch","observations","outcome"}
        if set(data)-permitted or not isinstance(data.get("expected_revision"),str):
            raise svc.InvalidAmendment("Unsupported fields or absent expected_revision")
        amendment=svc.change(
            actor=request.user,identifier=public_id,action=action,
            expected_revision=data["expected_revision"],reason=data.get("reason"),
            metrics_patch=data.get("metrics_patch"),observations=data.get("observations"),
            outcome=data.get("outcome"))
        run=svc.lookup(public_id)
        return json_no_store({"id":public_id,"current":svc.state(run),
                              "amendment_id":str(amendment.pk)},201)
    except RevisionConflict as exc:
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    except (svc.InvalidAmendment,ValueError,TypeError) as exc:
        return json_no_store({"error":"invalid_run_amendment","detail":str(exc)},400)
