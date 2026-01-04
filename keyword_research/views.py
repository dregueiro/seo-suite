import os
import json
from datetime import timedelta
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from projects.models import Project
from keyword_research.services.google_ads_keywords import fetch_keyword_overview_ads



from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from core.models import Run, ProviderResponse
from keyword_research.models import KeywordMetric
from keyword_research.services import mock_keyword_planner

MOCK_PROVIDER = "internal"
KIND_OVERVIEW_MOCK = "keyword_research.mock.keyword_overview"
KIND_MAGIC_MOCK = "keyword_research.mock.keyword_magic"

def _mock_allowed() -> bool:
    return bool(settings.DEBUG) and os.environ.get("SEOSUITE_ALLOW_MOCK_ADS", "0") == "1"

@require_POST
def fetch_overview_mock(request, project_id: int):
    if not _mock_allowed():
        messages.error(request, "Mock deshabilitado.")
        return redirect(f"/seo/projects/{project_id}/keywords/overview/")

    project = get_object_or_404(Project, id=project_id)
    keyword = (request.POST.get("keyword") or "").strip()
    if not keyword:
        messages.error(request, "Falta keyword.")
        return redirect(f"/seo/projects/{project.id}/keywords/overview/")

    ct = ContentType.objects.get(app_label="projects", model="project")
    run = Run.objects.create(
        provider=MOCK_PROVIDER,
        kind=KIND_OVERVIEW_MOCK,
        status="running",
        inputs={"project_id": project.id, "keyword": keyword},
        input_hash="mock:" + keyword.lower(),
        entity_content_type=ct,
        entity_object_id=project.id,
        started_at=timezone.now(),
    )

    try:
        m = mock_keyword_planner.overview(keyword)

        ProviderResponse.objects.create(
            run=run,
            provider=MOCK_PROVIDER,
            endpoint="mock_keyword_planner.overview",
            http_status=200,
            request_body=json.dumps({"keyword": keyword}),
            response_body=json.dumps(m.__dict__),
        )

        KeywordMetric.objects.filter(project=project, run=run).delete()
        KeywordMetric.objects.create(
            project=project,
            run=run,
            keyword=m.keyword,
            locale=f"{getattr(project,'country_code','')}-{getattr(project,'language_code','')}",
            language=getattr(project, "language_code", "") or "",
            geo=getattr(project, "country_code", "") or "",
            avg_monthly_searches=m.avg_monthly_searches,
            cpc_micros=m.cpc_micros,
            competition_level=m.competition_level,
            source="internal_mock",
            source_confidence=0.1,
            retrieved_at=timezone.now(),
            run_id=run.id,
        )

        run.status = "success"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
        messages.success(request, f"MOCK OK: {run.id}")
    except Exception as e:
        run.status = "failed"
        run.error_message = "Error mock overview"
        run.error_details = json.dumps({"error": str(e)}, ensure_ascii=False)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "error_details", "finished_at"])
        messages.error(request, "MOCK FAIL")

    return redirect(f"/seo/projects/{project.id}/keywords/overview/?q={keyword}&run_id={run.id}")

@require_POST
def fetch_magic_mock(request, project_id: int):
    if not _mock_allowed():
        messages.error(request, "Mock deshabilitado.")
        return redirect(f"/seo/projects/{project_id}/keywords/magic/")

    project = get_object_or_404(Project, id=project_id)
    seed = (request.POST.get("seed") or "").strip()
    if not seed:
        messages.error(request, "Falta seed.")
        return redirect(f"/seo/projects/{project.id}/keywords/magic/")

    limit = int(request.POST.get("limit") or "50")

    ct = ContentType.objects.get(app_label="projects", model="project")
    run = Run.objects.create(
        provider=MOCK_PROVIDER,
        kind=KIND_MAGIC_MOCK,
        status="running",
        inputs={"project_id": project.id, "seed": seed, "limit": limit},
        input_hash=f"mock:{seed.lower()}:{limit}",
        entity_content_type=ct,
        entity_object_id=project.id,
        started_at=timezone.now(),
    )

    try:
        items = mock_keyword_planner.ideas(seed, limit=limit)

        ProviderResponse.objects.create(
            run=run,
            provider=MOCK_PROVIDER,
            endpoint="mock_keyword_planner.ideas",
            http_status=200,
            request_body=json.dumps({"seed": seed, "limit": limit}),
            response_body=json.dumps([it.__dict__ for it in items])[:200000],
        )

        KeywordMetric.objects.filter(project=project, run=run).delete()
        for it in items:
            KeywordMetric.objects.create(
                project=project,
                run=run,
                keyword=it.keyword,
                locale=f"{getattr(project,'country_code','')}-{getattr(project,'language_code','')}",
                language=getattr(project, "language_code", "") or "",
                geo=getattr(project, "country_code", "") or "",
                avg_monthly_searches=it.avg_monthly_searches,
                cpc_micros=it.cpc_micros,
                competition_level=it.competition_level,
                source="internal_mock",
                source_confidence=0.1,
                retrieved_at=timezone.now(),
                run_id=run.id,
            )

        run.status = "success"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
        messages.success(request, f"MOCK OK: {run.id}")
    except Exception as e:
        run.status = "failed"
        run.error_message = "Error mock magic"
        run.error_details = json.dumps({"error": str(e)}, ensure_ascii=False)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "error_details", "finished_at"])
        messages.error(request, "MOCK FAIL")

    return redirect(f"/seo/projects/{project.id}/keywords/magic/?q={seed}&run_id={run.id}")


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
