"""PLAT-21: bounded read-side projection with separate observed and theoretical axes.

No dynamic scoring, no average-by-task, no implicit assignment of collaborative
Framework results to individual Solutions. Exactly one row per source observation.
"""
from django.db.models import QuerySet

from .forecast_services import accessible as forecasts
from .models import (BenchmarkRun,CompositeBenchmarkRun,CatalogItem,TaskNode,MeasuredSolution)

FIELDS=("quality_score","information_utility_score","cost_eur",
        "tokens_total","human_total_minutes","interaction_agent_minutes")


class InvalidExplorer(ValueError):
    pass


def _filters(parameters):
    permitted={"view","task_id","solution_id","campaign_id","kind","scope"}
    if set(parameters)-permitted:raise InvalidExplorer("Unsupported explorer filter")
    view=parameters.get("view","task")
    kind=parameters.get("kind","all")
    if view not in ("task","solution"):
        raise InvalidExplorer("view must be task or solution")
    if kind not in ("all","individual","composite","theoretical"):
        raise InvalidExplorer("Unsupported evidence kind")
    task=parameters.get("task_id")
    if task and (not task.startswith("tsk-") or
                 not TaskNode.objects.filter(item__public_id=task).exists()):
        raise InvalidExplorer("Unknown real Server Task")
    solution=parameters.get("solution_id")
    if solution and (not solution.startswith("sol-") or
                     not MeasuredSolution.objects.filter(item__public_id=solution).exists()):
        raise InvalidExplorer("Unknown measured AI Solution")
    campaign=parameters.get("campaign_id")
    if campaign and (not campaign.startswith("cmp-") or
                     not CatalogItem.objects.filter(type_slug="campaign",public_id=campaign).exists()):
        raise InvalidExplorer("Unknown campaign")
    if solution and kind=="composite":
        raise InvalidExplorer("Composite workflows are not individual AI Solutions")
    if solution and kind=="theoretical":
        raise InvalidExplorer("Forecasts have no measured Solution ID")
    scope=parameters.get("scope","published")
    if scope not in ("published","private"):
        raise InvalidExplorer("scope must be published or private")
    return view,kind,task,solution,campaign,scope


def _observation(run,kind):
    session=run.session
    task=session.case_pin.test_case.task.item.public_id
    ident=run.solution.item.public_id if kind=="individual" else run.framework.public_id
    candidate=("solution:"+ident if kind=="individual" else "framework:"+ident)
    metrics={key:run.metrics.get(key) for key in FIELDS}
    return {
        "id":run.public_id,"evidence_class":"measured","kind":kind,
        "task_id":task,"test_case_id":session.case_pin.test_case.item.public_id,
        "test_case_revision_id":str(session.case_pin.revision_id),
        "campaign_id":session.campaign_snapshot.revision.item.public_id,
        "campaign_revision_id":str(session.campaign_snapshot_id),
        "candidate":candidate,
        "solution_id":ident if kind=="individual" else None,
        "framework_id":ident if kind=="composite" else None,
        "outcome":run.outcome,"metrics":metrics,
        "missing_fields":[k for k,v in metrics.items() if v is None],
        "experimental_method_id":str(session.method_definition_id),
        "experimental_method_version":session.method_definition.version,
        "created_at":run.created_at.isoformat(),
        "detail":"/api/v1/runs/"+run.public_id,
    }


def _run_query(kind,task,solution,campaign,scope):
    queryset=(BenchmarkRun.objects if kind=="individual" else CompositeBenchmarkRun.objects)
    queryset=queryset.select_related(
        "session__case_pin__test_case__task__item",
        "session__case_pin__test_case__item",
        "session__campaign_snapshot__revision__item",
        "session__method_definition",
        "solution__item" if kind=="individual" else "framework"
    )
    if scope=="published":
        from .publication_services import effective_ids
        queryset=queryset.filter(public_id__in=effective_ids(campaign,kind))
    if task:queryset=queryset.filter(
        session__case_pin__test_case__task__item__public_id=task)
    if campaign:queryset=queryset.filter(
        session__campaign_snapshot__revision__item__public_id=campaign)
    if solution and kind=="individual":
        queryset=queryset.filter(solution__item__public_id=solution)
    return queryset.order_by("-created_at","-id")[:501]


def _forecast(row):
    p=row["properties"]
    metrics={key:None for key in FIELDS}
    predicted=p.get("predicted_metrics",{})
    # Different nomenclature and provenance: deliberately NO score aliasing into
    # observed fields. UI shows a separate projected metric object.
    return {
        "id":row["id"],"evidence_class":"theoretical","kind":"forecast",
        "task_id":row["task_id"],"test_case_id":None,"campaign_id":None,
        "candidate":"forecast:"+row["id"],"solution_id":None,"framework_id":None,
        "status":row["status"],"metrics":metrics,"predicted_metrics":predicted,
        "missing_fields":list(FIELDS),"uncertainty":p.get("uncertainty",""),
        "confidence":p.get("confidence","unknown"),"name":row["name"],
        "forecast_revision":row["revision"],"forecast_revision_id":row["revision_id"],
        "created_at":row["created_at"],"detail":"/api/v1/forecasts/"+row["id"],
    }


def _matrix(rows,view):
    first="task_id" if view=="task" else "candidate"
    second="candidate" if view=="task" else "task_id"
    cells={}
    for entry in rows:
        key=(entry[first],entry[second])
        cells.setdefault(key,[]).append(entry["id"])
    groups={}
    for (x,y),ids in sorted(cells.items()):
        groups.setdefault(x,[]).append({"key":y,"observation_ids":ids,
                                        "observations":len(ids)})
    return [{"key":key,"columns":columns} for key,columns in sorted(groups.items())]


def explore(actor,parameters):
    if "scope" not in parameters and (
            actor.has_perm("auth.business_write") or
            actor.has_perm("auth.publication_review")):
        parameters = {**parameters, "scope": "private"}
    view,kind,task,solution,campaign,scope=_filters(parameters)
    if scope=="private" and not (actor.has_perm("auth.business_write") or
                                 actor.has_perm("auth.publication_review")):
        raise InvalidExplorer("Private experimental evidence requires workgroup privileges")
    rows=[]
    for k in ("individual","composite"):
        if kind not in ("all",k) or (k=="composite" and solution):continue
        source=list(_run_query(k,task,solution,campaign,scope))
        if len(source)>500:raise InvalidExplorer("Too many results; narrow your filters")
        rows.extend(_observation(run,k) for run in source)
    if kind in ("all","theoretical") and solution is None and campaign is None:
        predictions=forecasts(actor,task_id=task)
        if len(predictions)>500:raise InvalidExplorer("Too many forecasts; filter by task")
        rows.extend(_forecast(r) for r in predictions if r["status"] in
                    ("staged","reviewed","published"))
    if len(rows)>500:raise InvalidExplorer("Too many observations; narrow your filters")
    rows.sort(key=lambda x:(x["created_at"],x["id"]),reverse=True)
    return {"scope":scope,"view":view,"row_axis":"task" if view=="task" else "candidate",
            "column_axis":"candidate" if view=="task" else "task",
            "matrix":_matrix(rows,view),
            "results":rows,"counts":{
                "individual_runs":sum(x["kind"]=="individual" for x in rows),
                "composite_workflows":sum(x["kind"]=="composite" for x in rows),
                "theoretical_forecasts":sum(x["kind"]=="forecast" for x in rows),
            },
            "scoring_policy":"No forecast-to-measured mixing or implicit aggregation"}
