"""PLAT-15: role-gated measured Run closure and read-only original evidence APIs."""
import json

from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .auth_views import capability, json_no_store
from .evidence_store import EvidenceError
from .models import BenchmarkRun, BenchmarkSession, CompositeBenchmarkRun, CatalogItem, MeasuredSolution
from .run_services import close, serialize
from .composite_run_services import close as close_composite, serialize as serialize_composite
from .session_services import InvalidSession, SessionAccessDenied, SessionConflict


def _body(request):
    if len(request.body)>512*1024:
        raise InvalidSession("Run close request exceeds 512 KiB")
    try:
        data=json.loads(request.body)
    except (UnicodeDecodeError,ValueError) as exc:
        raise InvalidSession("Expected JSON payload") from exc
    if not isinstance(data,dict):
        raise InvalidSession("Expected a JSON object")
    return data


def _read_run(public_id):
    if not public_id.startswith("run-"):raise Http404("Not a run identifier")
    return get_object_or_404(BenchmarkRun.objects.select_related(
        "solution__item__current_revision","solution_revision","session",
        "closing_checkpoint","recorded_by"),public_id=public_id)


@require_POST
@csrf_protect
@capability("business_write")
@never_cache
def close_session(request,public_id):
    try:
        payload=_body(request)
        expected=payload.pop("expected_revision",None)
        session=BenchmarkSession.objects.filter(public_id=public_id).values("selected_participants").first()
        if session is None:
            raise InvalidSession("Unknown Server session")
        composite=len(session["selected_participants"])>=2
        service=close_composite if composite else close
        run=service(actor=request.user,public_id=public_id,
                    expected_revision=expected,data=payload)
        response=json_no_store(
            serialize_composite(run) if composite else serialize(run),201)
        response["Location"]="/api/v1/runs/"+run.public_id
        return response
    except SessionAccessDenied as exc:
        return json_no_store({"error":"permission_denied","detail":str(exc)},403)
    except SessionConflict as exc:
        return json_no_store({"error":"revision_conflict","detail":str(exc)},409)
    except EvidenceError as exc:
        return json_no_store({"error":"evidence_unavailable","detail":str(exc)},409)
    except (InvalidSession,ValueError,OverflowError) as exc:
        return json_no_store({"error":"invalid_run","detail":str(exc)},400)


@require_GET
@capability("business_read")
@never_cache
def list_runs(request):
    if set(request.GET)-{"campaign_id","solution_id","kind"}:
        return json_no_store({"error":"invalid_filter"},400)
    kind=request.GET.get("kind")
    if kind not in (None,"individual","composite"):
        return json_no_store({"error":"invalid_kind"},400)
    campaign=request.GET.get("campaign_id")
    solution=request.GET.get("solution_id")
    if campaign:
        if not campaign.startswith("cmp-") or not CatalogItem.objects.filter(
                public_id=campaign,type_slug="campaign").exists():
            return json_no_store({"error":"invalid_campaign"},400)
    if solution and not solution.startswith("sol-"):
        return json_no_store({"error":"invalid_solution"},400)
    if solution and kind=="composite":
        return json_no_store({"error":"composite_runs_have_no_individual_solution"},400)
    entries=[]
    if kind in (None,"individual"):
        individual=BenchmarkRun.objects.select_related(
            "solution__item__current_revision","solution_revision","session",
            "closing_checkpoint","recorded_by"
        ).order_by("-created_at","-id")
        if campaign:
            individual=individual.filter(
                session__campaign_snapshot__revision__item__public_id=campaign)
        if solution:
            individual=individual.filter(solution__item__public_id=solution)
        entries.extend(serialize(row,include_raw=False) for row in individual[:501])
    if kind in (None,"composite") and not solution:
        composite=CompositeBenchmarkRun.objects.select_related(
            "session","framework","framework_revision","closing_checkpoint","recorded_by"
        ).order_by("-created_at","-id")
        if campaign:
            composite=composite.filter(
                session__campaign_snapshot__revision__item__public_id=campaign)
        entries.extend(serialize_composite(row,include_raw=False) for row in composite[:501])
    if len(entries)>500:return json_no_store({"error":"too_many_runs"},422)
    entries.sort(key=lambda row:(row["created_at"],row["id"]),reverse=True)
    return json_no_store({"results":entries})


@require_GET
@capability("business_read")
@never_cache
def get_run(request,public_id):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    individual=BenchmarkRun.objects.select_related(
        "solution__item__current_revision","solution_revision","session",
        "closing_checkpoint","recorded_by").filter(public_id=public_id).first()
    if individual is not None:
        return json_no_store(serialize(individual))
    if not public_id.startswith("run-"):raise Http404("Not a Run identifier")
    composite=get_object_or_404(CompositeBenchmarkRun.objects.select_related(
        "session","framework","framework_revision","closing_checkpoint","recorded_by"),
        public_id=public_id)
    return json_no_store(serialize_composite(composite))


@require_GET
@capability("business_read")
@never_cache
def solutions(request):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    rows=list(MeasuredSolution.objects.select_related(
        "item__current_revision").order_by("item__public_id")[:501])
    if len(rows)>500:return json_no_store({"error":"too_many_solutions"},422)
    return json_no_store({"results":[{
        "id":row.item.public_id,"revision_id":str(row.item.current_revision_id),
        "fingerprint":row.fingerprint,"lifecycle":row.item.current_revision.properties["lifecycle"],
        "first_measured":True,"run_count":row.runs.count(),
    } for row in rows]})


@require_GET
@capability("business_read")
@never_cache
def solution(request,public_id):
    if request.GET:return json_no_store({"error":"invalid_filter"},400)
    if not public_id.startswith("sol-"):raise Http404("Not a solution identifier")
    row=get_object_or_404(MeasuredSolution.objects.select_related(
        "item__current_revision"),item__public_id=public_id)
    rev=row.item.current_revision
    return json_no_store({
        "id":row.item.public_id,"revision":f"r{rev.number:03d}",
        "revision_id":str(rev.pk),"fingerprint":row.fingerprint,
        "lifecycle":rev.properties["lifecycle"],"configuration":rev.properties["setup"],
        "run_ids":list(row.runs.order_by("created_at","id").values_list("public_id",flat=True)),
        "recommended":False,
    })
