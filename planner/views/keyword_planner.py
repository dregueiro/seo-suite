from __future__ import annotations

from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from planner.forms import KeywordPlannerForm
from projects.models import Project
from planner.services.keyword_ideas_service import KeywordIdeasService


@require_http_methods(["GET", "POST"])
def keyword_planner_view(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    # Defaults desde el proyecto (solo GET/primera carga)
    initial = {}
    if project.country_id:
        initial["country"] = project.country_id
    if project.language_id:
        initial["language"] = project.language_id

    form = KeywordPlannerForm(request.POST or None, initial=initial)

    run = None
    ideas = []
    error = ""

    if request.method == "POST" and form.is_valid():
        seed = form.cleaned_data["seed_keyword"]
        country = form.cleaned_data["country"]
        language = form.cleaned_data["language"]
        top_n = form.cleaned_data.get("top_n") or 15
        use_fallback = bool(form.cleaned_data.get("use_fallback"))

        try:
            svc = KeywordIdeasService()
            run = svc.get_or_create_run(
                project=project,
                seed_keyword=seed,
                location_code=int(country.dataforseo_location_code),
                language_code=language.code,
                top_n=int(top_n),
                use_fallback=use_fallback,
            )
            ideas = list(run.ideas.order_by("-search_volume"))
        except Exception as e:
            error = str(e)

    return render(
        request,
        "core/keyword_planner.html",
        {"project": project, "form": form, "run": run, "ideas": ideas, "error": error},
    )
