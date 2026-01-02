from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.models import Project
from django.core.management import call_command


@require_POST
def run_serp_mock(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    top_n = int(request.POST.get("top", 10))
    limit = int(request.POST.get("limit", 25))

    try:
        call_command("run_serp", project=project.id, provider="mock", top=top_n, limit=limit)
        messages.success(request, f"SERP run started and completed (mock) for: {project.name}")
    except Exception as e:
        messages.error(request, f"SERP run failed: {e}")

    return redirect("serp_runs")

@require_POST
def run_serp_serpapi(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    top_n = int(request.POST.get("top", 10))
    limit = int(request.POST.get("limit", 25))

    try:
        call_command("run_serp", project=project.id, provider="serpapi", top=top_n, limit=limit)
        messages.success(request, f"SERP run completed (SerpAPI) for: {project.name}")
    except Exception as e:
        messages.error(request, f"SERP run failed: {e}")

    return redirect("serp_runs")
