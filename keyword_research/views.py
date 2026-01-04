from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from projects.models import Project
from keyword_research.services.google_ads_keywords import fetch_keyword_overview_ads


@require_POST
def fetch_overview_ads(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)
    keyword = (request.POST.get("keyword") or "").strip()

    if not keyword:
        messages.error(request, "Falta keyword.")
        return redirect(f"/seo/projects/{project.id}/keywords/overview/")

    run = fetch_keyword_overview_ads(project, keyword, use_cache=True)

    if run.status == "success":
        messages.success(request, f"OK: Run {run.id}")
        return redirect(f"/seo/projects/{project.id}/keywords/overview/?q={keyword}&run_id={run.id}")

    messages.error(request, f"FAIL: {run.error_message}")
    return redirect(f"/seo/projects/{project.id}/keywords/overview/?q={keyword}&run_id={run.id}")
