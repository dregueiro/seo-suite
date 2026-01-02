from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from core.models import SerpRun, SerpResult


def serp_runs(request):
    qs = SerpRun.objects.select_related("project", "project__client").order_by("-created_at")
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "core/serp_runs.html", {"page_obj": page_obj})


def serp_run_detail(request, run_id: int):
    run = get_object_or_404(SerpRun.objects.select_related("project", "project__client"), id=run_id)

    results_qs = (
        SerpResult.objects.filter(serp_run=run)
        .select_related("keyword")
        .order_by("keyword_id", "position")
    )

    paginator = Paginator(results_qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "core/serp_run_detail.html", {"run": run, "page_obj": page_obj})
