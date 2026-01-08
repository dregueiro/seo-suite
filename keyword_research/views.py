# keyword_research/views.py
import os
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required

from projects.models import Project
from core.models import Run, ProviderResponse
from keyword_research.models import KeywordMetric
from keyword_research.services import mock_keyword_planner
from keyword_research.services.google_ads_keywords import fetch_keyword_overview_ads
from keyword_research.services.keyword_planner_csv import import_keyword_planner_csv


def _mock_allowed() -> bool:
    return str(os.environ.get("SEOSUITE_ALLOW_MOCK_ADS", "")).strip() in ("1", "true", "True", "yes", "YES")


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

    provider = Run.Provider.ADS
    kind = "keyword_research.mock.keyword_overview"
    inputs = {"project_id": project.id, "keyword": keyword}

    ct = ContentType.objects.get_for_model(Project)
    run = Run.objects.create(
        provider=str(provider),
        kind=kind,
        status="running",
        inputs=inputs,
        outputs={},
        input_hash=json.dumps(inputs, sort_keys=True),
        entity_content_type=ct,
        entity_object_id=project.id,
        started_at=timezone.now(),
    )

    try:
        data = mock_keyword_planner.keyword_overview(keyword, country_code=project.country_code, language_code=project.language_code)

        ProviderResponse.objects.create(
            run=run,
            provider=str(provider),
            endpoint="mock.keyword_overview",
            http_status=200,
            request_body=json.dumps(inputs, ensure_ascii=False)[:200000],
            response_body=json.dumps(data, ensure_ascii=False)[:200000],
        )

        KeywordMetric.objects.create(
            project=project,
            run=run,
            keyword=keyword,
            locale=f"{project.country_code}-{project.language_code}",
            language=project.language_code,
            geo=f"country:{project.country_code}",
            avg_monthly_searches=data.get("avg_monthly_searches"),
            cpc_micros=data.get("cpc_micros"),
            competition_level=data.get("competition_level", ""),
            source="mock",
            source_confidence=0.6,
            retrieved_at=timezone.now(),
        )

        run.status = "success"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])

        messages.success(request, f"MOCK OK: {run.id}")

    except Exception as e:
        run.status = "failed"
        run.error_message = "Error mock overview"
        run.error_details = json.dumps({"error": str(e)}, ensure_ascii=False)[:200000]
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

    provider = Run.Provider.ADS
    kind = "keyword_research.mock.keyword_magic"
    inputs = {"project_id": project.id, "seed": seed}

    ct = ContentType.objects.get_for_model(Project)
    run = Run.objects.create(
        provider=str(provider),
        kind=kind,
        status="running",
        inputs=inputs,
        outputs={},
        input_hash=json.dumps(inputs, sort_keys=True),
        entity_content_type=ct,
        entity_object_id=project.id,
        started_at=timezone.now(),
    )

    try:
        data = mock_keyword_planner.keyword_magic(seed, country_code=project.country_code, language_code=project.language_code, limit=50)

        ProviderResponse.objects.create(
            run=run,
            provider=str(provider),
            endpoint="mock.keyword_magic",
            http_status=200,
            request_body=json.dumps(inputs, ensure_ascii=False)[:200000],
            response_body=json.dumps(data, ensure_ascii=False)[:200000],
        )

        created = 0
        for row in data.get("results", []):
            KeywordMetric.objects.create(
                project=project,
                run=run,
                keyword=row.get("keyword", ""),
                locale=f"{project.country_code}-{project.language_code}",
                language=project.language_code,
                geo=f"country:{project.country_code}",
                avg_monthly_searches=row.get("avg_monthly_searches"),
                cpc_micros=row.get("cpc_micros"),
                competition_level=row.get("competition_level", ""),
                source="mock",
                source_confidence=0.6,
                retrieved_at=timezone.now(),
            )
            created += 1

        run.status = "success"
        run.outputs = {"created_metrics": created}
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "outputs", "finished_at"])

        messages.success(request, f"MOCK MAGIC OK: {run.id}")

    except Exception as e:
        run.status = "failed"
        run.error_message = "Error mock magic"
        run.error_details = json.dumps({"error": str(e)}, ensure_ascii=False)[:200000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "error_details", "finished_at"])
        messages.error(request, "MOCK MAGIC FAIL")

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


@require_POST
def fetch_magic_ads(request, project_id: int):
    """
    STUB mientras Ads está PENDING (developer token no aprobado).
    Crea un Run FAILED trazable y vuelve a la UI.
    """
    project = get_object_or_404(Project, id=project_id)

    seed = (request.POST.get("seed") or "").strip()
    if not seed:
        messages.error(request, "Falta seed.")
        return redirect(f"/seo/projects/{project.id}/keywords/magic/")

    provider = Run.Provider.ADS
    kind = "keyword_research.ads.keyword_magic"
    inputs = {"project_id": project.id, "seed": seed}

    ct = ContentType.objects.get_for_model(Project)
    run = Run.objects.create(
        provider=str(provider),
        kind=kind,
        status="failed",
        inputs=inputs,
        outputs={},
        input_hash=json.dumps(inputs, sort_keys=True),
        entity_content_type=ct,
        entity_object_id=project.id,
        started_at=timezone.now(),
        finished_at=timezone.now(),
        error_message="Ads Magic PENDING (token no aprobado)",
        error_details={"status": "PENDING"},
        cost_micros=0,
    )

    ProviderResponse.objects.create(
        run=run,
        provider=str(provider),
        endpoint="google_ads.keyword_magic",
        http_status=403,
        request_body=json.dumps(inputs, ensure_ascii=False)[:200000],
        response_body=json.dumps(
            {"error": "DEVELOPER_TOKEN_NOT_APPROVED", "status": "PENDING"},
            ensure_ascii=False,
        )[:200000],
    )

    messages.error(request, "Ads Magic: PENDING (token no aprobado). Usa Mock por ahora.")
    return redirect(f"/seo/projects/{project.id}/keywords/magic/?q={seed}&run_id={run.id}")


@require_POST
def import_planner_csv(request, project_id: int):
    """
    Importa CSV de Keyword Planner (UI) y lo mapea a KeywordMetric.
    redirect_to: overview | magic
    """
    project = get_object_or_404(Project, id=project_id)

    f = request.FILES.get("csv_file")
    keyword = (request.POST.get("keyword") or "").strip()
    seed = (request.POST.get("seed") or "").strip()

    redirect_to = (request.POST.get("redirect_to") or "overview").strip().lower()
    if redirect_to not in ("overview", "magic"):
        redirect_to = "overview"

    # ✅ Base correcta (tu URLConf tiene prefijo seo/)
    base = f"/seo/projects/{project.id}/keywords/{redirect_to}/"

    if not f:
        messages.error(request, "Falta archivo CSV.")
        return redirect(base)

    if f.size and f.size > 10 * 1024 * 1024:
        messages.error(request, "CSV demasiado grande (max 10MB).")
        return redirect(base)

    csv_bytes = f.read()
    filename = f.name or "keyword_planner.csv"

    run = import_keyword_planner_csv(
        project,
        csv_bytes,
        keyword=keyword,
        seed=seed,
        filename=filename,
        use_cache=True,
    )

    if run.status == "success":
        created = (run.outputs or {}).get("created_metrics")
        messages.success(request, f"Import CSV OK: Run {run.id} (metrics: {created})")
    else:
        messages.error(request, f"Import CSV FAIL: {run.error_message}")

    q = keyword or seed or ""
    if q:
        return redirect(f"{base}?q={q}&run_id={run.id}")
    return redirect(f"{base}?run_id={run.id}")


@require_POST
@staff_member_required
def delete_run_keyword_metrics(request, project_id: int, run_id):
    """
    Borra KeywordMetric asociadas a un Run (UI button).
    Staff-only para no exponer borrados a usuarios finales.
    """
    project = get_object_or_404(Project, id=project_id)

    redirect_to = (request.POST.get("redirect_to") or "overview").strip().lower()
    if redirect_to not in ("overview", "magic"):
        redirect_to = "overview"

    q = (request.POST.get("q") or "").strip()
    base = f"/seo/projects/{project.id}/keywords/{redirect_to}/"

    run = Run.objects.filter(id=run_id, entity_object_id=project.id).first()
    if not run:
        messages.error(request, "Run no encontrado para este proyecto.")
        if q:
            return redirect(f"{base}?q={q}")
        return redirect(base)

    qs = KeywordMetric.objects.filter(project=project, run=run)
    count = qs.count()
    qs.delete()

    messages.success(request, f"OK: borradas {count} métricas del Run {run.id}")

    # volvemos a la misma pantalla, manteniendo run_id para que se vea el panel del run
    if q:
        return redirect(f"{base}?q={q}&run_id={run.id}")
    return redirect(f"{base}?run_id={run.id}")
