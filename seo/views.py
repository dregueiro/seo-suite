# seo/views.py
from django.shortcuts import get_object_or_404, render
from projects.models import Project
from integrations.models import IntegrationStatus

from django.contrib import messages
from core.models import Run
from keyword_research.models import KeywordMetric

# ... tu project_setup ya existente ...

def keyword_overview(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    keyword = (request.GET.get("q") or "").strip()
    run_id = (request.GET.get("run_id") or "").strip()

    selected_run = None
    metrics = KeywordMetric.objects.none()
    runs = Run.objects.none()

    if keyword:
        runs = (
            Run.objects.filter(
                provider=Run.Provider.ADS,
                kind="keyword_research.ads.keyword_overview",
                entity_object_id=project.id,
                entity_content_type__app_label="projects",
                entity_content_type__model="project",
                inputs__keyword=keyword,
            )
            .order_by("-created_at")[:20]
        )

    if run_id:
        selected_run = Run.objects.filter(id=run_id).first()
    elif keyword:
        selected_run = runs.filter(status=Run.Status.SUCCESS).first()

    if selected_run:
        metrics = KeywordMetric.objects.filter(project=project, run=selected_run).order_by("keyword")

    ctx = {
        "project": project,
        "keyword": keyword,
        "runs": runs,
        "selected_run": selected_run,
        "metrics": metrics,
    }
    return render(request, "seo/keyword_overview.html", ctx)


def project_setup(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    statuses_qs = IntegrationStatus.objects.filter(project=project)
    statuses = {s.provider: s for s in statuses_qs}

    checklist = [
        # ... igual que antes ...
    ]

    ctx = {
        "project": project,
        "statuses": statuses,
        "checklist": checklist,
        "providers": ["gsc", "ga4", "ads"],
    }
    return render(request, "seo/project_setup.html", ctx)
