# seo/views.py
import csv
import hashlib
import io
import os
import json

from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.apps import apps
from django.http import Http404
from django.urls import reverse

from projects.models import Project
from integrations.models import IntegrationStatus
from core.models import Run, RunArtifact
from keyword_research.models import KeywordMetric

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch




@login_required
def keyword_metrics(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    # elegimos el run más reciente con métricas (overview/magic/csv import)
    kinds = [
        "keyword_research.ads.keyword_overview",
        "keyword_research.mock.keyword_overview",
        "keyword_research.ads.keyword_magic",
        "keyword_research.mock.keyword_magic",
        "keyword_research.ads.keyword_planner_csv_import",
    ]

    run_id = (request.GET.get("run_id") or "").strip()
    run = None
    if run_id:
        run = Run.objects.filter(id=run_id, entity_object_id=project.id).first()

    if not run:
        run = Run.objects.filter(entity_object_id=project.id, kind__in=kinds, status=Run.Status.SUCCESS).order_by("-created_at").first()

    metrics_qs = KeywordMetric.objects.filter(project=project, run=run) if run else KeywordMetric.objects.none()

    total_keywords = metrics_qs.count()
    total_volume = sum([m.avg_monthly_searches or 0 for m in metrics_qs.only("avg_monthly_searches")])
    avg_cpc = None
    cpcs = [m.cpc_micros for m in metrics_qs.only("cpc_micros") if m.cpc_micros]
    if cpcs:
        avg_cpc = (sum(cpcs) / len(cpcs)) / 1_000_000

    top10 = list(metrics_qs.order_by("-avg_monthly_searches", "keyword")[:10])
    chart_labels = [m.keyword for m in top10]
    chart_values = [m.avg_monthly_searches or 0 for m in top10]

    recent_runs = Run.objects.filter(entity_object_id=project.id, kind__in=kinds).order_by("-created_at")[:20]
    recent_runs_rows = [(r.id, f"{r.created_at:%Y-%m-%d %H:%M} | {r.status} | {r.kind}") for r in recent_runs]

    ctx = {
        "title": "Keyword Metrics",
        "subTitle": project.name,
        "breadcrumbs": [
            {"label": "SEO", "url": reverse("seo:dashboard")},
            {"label": "Projects", "url": reverse("seo:projects_list")},
            {"label": "Keyword Metrics"},
        ],
        "project": project,
        "run": run,
        "total_keywords": total_keywords,
        "total_volume": total_volume,
        "avg_cpc": avg_cpc,
        "metrics": metrics_qs.order_by("-avg_monthly_searches", "keyword")[:500],
        "recent_runs_rows": recent_runs_rows,
        "chart_labels_json": json.dumps(chart_labels, ensure_ascii=False),
        "chart_values_json": json.dumps(chart_values, ensure_ascii=False),
    }
    return render(request, "seo/keyword_metrics.html", ctx)


@login_required
def dashboard(request):
    ctx = {"title":"Dashboard","subTitle":"","breadcrumbs":[{"label":"SEO"},{"label":"Dashboard"}]}

    return render(request, "seo/dashboard.html", {"title": "Dashboard", "subTitle": ""})


def _get_model(app_label: str, model_name: str):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _mock_allowed() -> bool:
    return bool(settings.DEBUG) and os.environ.get("SEOSUITE_ALLOW_MOCK_ADS", "0") == "1"

def _integration_is_ok(status_obj) -> bool:
    """
    Determina si una IntegrationStatus está OK sin asumir un esquema fijo.
    Soporta campos comunes: ok/is_ok/is_connected/status/state/enabled.
    Nunca rompe si el modelo cambia.
    """
    if not status_obj:
        return False

    # bool fields comunes
    for attr in ("ok", "is_ok", "is_connected", "connected", "enabled"):
        if hasattr(status_obj, attr):
            try:
                return bool(getattr(status_obj, attr))
            except Exception:
                pass

    # campos tipo string con estados
    for attr in ("status", "state"):
        if hasattr(status_obj, attr):
            try:
                val = (getattr(status_obj, attr) or "").strip().upper()
                if val in ("OK", "PASS", "SUCCESS", "CONNECTED", "ACTIVE", "ENABLED", "VALID"):
                    return True
            except Exception:
                pass

    return False


def _write_artifact(*, run: Run, filename: str, artifact_type: str, content_bytes: bytes) -> RunArtifact:
    """
    Guarda un archivo en disco (local, trazable) + crea RunArtifact.
    artifact_type debe matchear choices (csv/pdf/json/text/other).
    """
    base_dir = Path(settings.BASE_DIR) / "artifacts" / str(run.id)
    base_dir.mkdir(parents=True, exist_ok=True)

    path = base_dir / filename
    path.write_bytes(content_bytes)

    sha = hashlib.sha256(content_bytes).hexdigest()

    return RunArtifact.objects.create(
        run=run,
        name=filename,
        artifact_type=artifact_type,
        storage_path=str(path),
        sha256=sha,
        size_bytes=len(content_bytes),
    )

from django.urls import reverse

@login_required
def projects_list(request):
    ProjectModel = _get_model("projects", "Project")
    if not ProjectModel:
        return render(request, "seo/projects_list.html", {
            "title": "Projects",
            "subTitle": "",
            "breadcrumbs": [{"label": "SEO", "url": reverse("seo:dashboard")}, {"label": "Projects"}],
            "projects": [],
            "model_missing": True
        })
    ctx = {"title":"Projects","subTitle":"","breadcrumbs":[{"label":"SEO","url":reverse("seo:dashboard")},{"label":"Projects"}],}

    projects = ProjectModel.objects.all().order_by("-id")[:200]
    return render(request, "seo/projects_list.html", {
        "title": "Projects",
        "subTitle": "",
        "breadcrumbs": [{"label": "SEO", "url": reverse("seo:dashboard")}, {"label": "Projects"}],
        "projects": projects,
        "model_missing": False
    })



@login_required
def project_setup(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    statuses_qs = IntegrationStatus.objects.filter(project=project)
    statuses = {s.provider: s for s in statuses_qs}

    providers = ["gsc", "ga4", "ads"]
    provider_rows = [(prov, statuses.get(prov)) for prov in providers]

    checklist = [
        # ... tu checklist ...
    ]

    ctx = {
        "title": "Setup",
        "subTitle": project.name,
        "breadcrumbs": [
            {"label": "SEO", "url": reverse("seo:dashboard")},
            {"label": "Projects", "url": reverse("seo:projects_list")},
            {"label": "Setup"},
        ],
        "project": project,
        "providers": providers,
        "provider_rows": provider_rows,
        "checklist": checklist,
        "mock_ads_enabled": _mock_allowed(),
        # opcional: ocultar breadcrumb global si querés estilo profile
        # "hide_breadcrumb": True,
    }
    return render(request, "seo/project_setup.html", ctx)


def keyword_overview(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    keyword = (request.GET.get("q") or "").strip()
    run_id = (request.GET.get("run_id") or "").strip()

    overview_kinds = [
        "keyword_research.ads.keyword_overview",
        "keyword_research.mock.keyword_overview",
        "keyword_research.ads.keyword_planner_csv_import",
    ]

    # ✅ SIEMPRE definidos
    recent_runs = (
        Run.objects.filter(entity_object_id=project.id, kind__in=overview_kinds)
        .order_by("-created_at")[:20]
    )
    selected_run = None
    artifacts = RunArtifact.objects.none()
    runs = Run.objects.none()
    metrics = KeywordMetric.objects.none()

    # 1) Resolver selected_run
    if run_id:
        selected_run = Run.objects.filter(id=run_id, entity_object_id=project.id).first()

    # 2) Lista de runs “por keyword” (panel histórico por query)
    if keyword:
        base_qs = (
            Run.objects.filter(
                entity_object_id=project.id,
                kind__in=overview_kinds,
                inputs__keyword=keyword,
            )
            .order_by("-created_at")
        )
        runs = base_qs[:20]

        if not selected_run:
            selected_run = base_qs.filter(status=Run.Status.SUCCESS).first() or base_qs.first()

    # 3) Fallback: si no hay keyword, usa el más reciente del historial
    if not selected_run and recent_runs:
        selected_run = recent_runs[0]

    # 4) Artifacts + métricas del run seleccionado
    if selected_run:
        artifacts = RunArtifact.objects.filter(run=selected_run).order_by("-created_at")
        metrics = KeywordMetric.objects.filter(project=project, run=selected_run).order_by("keyword")

    selected_run_admin_url = None
    if selected_run:
        selected_run_admin_url = f"/admin/core/run/{selected_run.id}/change/"

    def _run_label(r: Run) -> str:
        inp = r.inputs or {}
        q = inp.get("keyword") or inp.get("seed") or ""
        created = (r.outputs or {}).get("created_metrics")
        created_txt = f" | metrics:{created}" if created is not None else ""
        q_txt = f" | q:{q}" if q else ""
        return f"{r.created_at:%Y-%m-%d %H:%M} | {r.status} | {r.kind}{q_txt}{created_txt}"

    recent_runs_rows = [(r.id, _run_label(r)) for r in recent_runs]

    # ---- UI stats (tipo Semrush) desde metrics del selected_run ----
    overview = {
        "volume": None,
        "cpc": None,  # en USD aprox si tienes micros
        "competition": None,
        "source": None,
        "confidence": None,
    }

    ideas_variations = []
    ideas_questions = []

    if selected_run and metrics.exists():
        # Tomamos la keyword principal si existe en el snapshot, si no usamos la primera
        main = metrics.filter(keyword__iexact=(keyword or "")).first() or metrics.first()

        if main:
            overview["volume"] = main.avg_monthly_searches
            # CPC micros -> USD aproximado (si tu moneda no es USD aún, lo dejamos “aprox”)
            overview["cpc"] = (main.cpc_micros / 1_000_000) if main.cpc_micros else None
            overview["competition"] = main.competition_level
            overview["source"] = main.source
            overview["confidence"] = main.source_confidence

        # Ideas: heurística barata y trazable
        q_words = ("how", "what", "why", "when", "where", "who", "cuánto", "cuanto", "qué", "que", "como", "cómo")
        for m in metrics.order_by("-avg_monthly_searches", "keyword")[:300]:
            m.cpc = (m.cpc_micros / 1_000_000) if m.cpc_micros else None
            kw = (m.keyword or "").lower()
            if any(w in kw.split() for w in q_words) or kw.startswith(("how ", "what ", "why ", "cuando ", "que ", "qué ", "como ", "cómo ")):
                ideas_questions.append(m)
            else:
                ideas_variations.append(m)

        # límites de UI
        ideas_variations = ideas_variations[:50]
        ideas_questions = ideas_questions[:50]


    ctx = {
        "project": project,
        "keyword": keyword,
        "runs": runs,                 # runs filtrados por keyword (si aplica)
        "recent_runs": recent_runs,   # últimos 20 runs (dropdown)
        "selected_run": selected_run,
        "artifacts": artifacts,
        "metrics": metrics,
        "mock_ads_enabled": _mock_allowed(),
        "recent_runs_rows": recent_runs_rows,
        "selected_run_admin_url": selected_run_admin_url,
        "overview": overview,
        "ideas_variations": ideas_variations,
        "ideas_questions": ideas_questions,


    }
    return render(request, "seo/keyword_overview.html", ctx)

@login_required
def keyword_magic(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    # Filtros UI (seguros aunque no existan en template)
    q = (request.GET.get("q") or "").strip()
    seed = q
    run_id = (request.GET.get("run_id") or "").strip()

    min_volume = (request.GET.get("min_volume") or "").strip()
    competition = (request.GET.get("competition") or "").strip()
    include = (request.GET.get("include") or "").strip()
    exclude = (request.GET.get("exclude") or "").strip()

    magic_kinds = [
        "keyword_research.ads.keyword_magic",
        "keyword_research.mock.keyword_magic",
        "keyword_research.ads.keyword_planner_csv_import",
    ]

    recent_runs = (
        Run.objects.filter(entity_object_id=project.id, kind__in=magic_kinds)
        .order_by("-created_at")[:20]
    )

    selected_run = None
    artifacts_qs = RunArtifact.objects.none()
    runs = Run.objects.none()
    metrics_qs = KeywordMetric.objects.none()

    # 1) selected_run por run_id
    if run_id:
        selected_run = Run.objects.filter(id=run_id, entity_object_id=project.id).first()

    # 2) runs por seed
    if seed:
        base_qs = (
            Run.objects.filter(
                entity_object_id=project.id,
                kind__in=magic_kinds,
                inputs__seed=seed,
            )
            .order_by("-created_at")
        )
        runs = base_qs[:20]
        if not selected_run:
            selected_run = base_qs.filter(status=Run.Status.SUCCESS).first() or base_qs.first()

    # 3) fallback: último run
    if not selected_run and recent_runs:
        selected_run = recent_runs[0]

    selected_run_admin_url = None
    if selected_run:
        selected_run_admin_url = f"/admin/core/run/{selected_run.id}/change/"
        artifacts_qs = RunArtifact.objects.filter(run=selected_run).order_by("-created_at")

        metrics_qs = (
            KeywordMetric.objects.filter(project=project, run=selected_run)
            .order_by("-avg_monthly_searches", "keyword")
        )

        # filtros baratos (solo DB)
        if min_volume.isdigit():
            metrics_qs = metrics_qs.filter(avg_monthly_searches__gte=int(min_volume))

        if competition:
            metrics_qs = metrics_qs.filter(competition_level__iexact=competition)

        if include:
            metrics_qs = metrics_qs.filter(keyword__icontains=include)

        if exclude:
            metrics_qs = metrics_qs.exclude(keyword__icontains=exclude)

        metrics_qs = metrics_qs[:200]

    # Dropdown labels (si lo usás en templates)
    def _run_label(r: Run) -> str:
        inp = r.inputs or {}
        qq = inp.get("seed") or inp.get("keyword") or ""
        created = (r.outputs or {}).get("created_metrics")
        created_txt = f" | metrics:{created}" if created is not None else ""
        q_txt = f" | q:{qq}" if qq else ""
        return f"{r.created_at:%Y-%m-%d %H:%M} | {r.status} | {r.kind}{q_txt}{created_txt}"

    recent_runs_rows = [(r.id, _run_label(r)) for r in recent_runs]

    # Gate Ads (sin romper)
    ads_status = IntegrationStatus.objects.filter(project=project, provider="ads").first()
    ads_can_fetch = _integration_is_ok(ads_status)

    # ---- Tabs: Broad / Questions / Related (solo heurística) ----
    metrics_list = list(metrics_qs)  # una sola query, luego clasificamos en memoria

    ideas_questions = []
    ideas_related = []
    ideas_broad = []

    q_words = (
        "how", "what", "why", "when", "where", "who",
        "cuanto", "cuánto", "que", "qué", "como", "cómo"
    )
    seed_l = (seed or "").lower()

    for m in metrics_list:
        kw = (m.keyword or "").lower()

        # Questions
        if any(w in kw.split() for w in q_words) or kw.startswith(
            ("how ", "what ", "why ", "when ", "where ", "who ",
             "cuanto ", "cuánto ", "que ", "qué ", "como ", "cómo ")
        ):
            ideas_questions.append(m)
            continue

        # Related (contiene el seed)
        if seed_l and seed_l in kw:
            ideas_related.append(m)
            continue

        # Broad (resto)
        ideas_broad.append(m)

    ideas_questions = ideas_questions[:50]
    ideas_related = ideas_related[:50]
    ideas_broad = ideas_broad[:50]

    # rows para el template "analytics" (si lo usás)
    rows = []
    for m in metrics_list:
        rows.append({
            "keyword": m.keyword,
            "avg_monthly_searches": m.avg_monthly_searches,
            "cpc": (m.cpc_micros / 1_000_000) if getattr(m, "cpc_micros", None) else None,
            "competition_level": m.competition_level,
            "source": m.source,
        })

    # artifacts para template (download_url safe)
    artifacts = []
    for a in artifacts_qs:
        artifacts.append({
            "name": a.name,
            "download_url": getattr(a, "download_url", None) or f"/admin/core/runartifact/{a.id}/change/",
        })

    return render(
        request,
        "seo/keyword_magic.html",
        {
            "title": "Keyword Magic",
            "subTitle": project.name,
            "project": project,

            # template analytics
            "rows": rows,
            "q": q,
            "min_volume": min_volume,
            "competition": competition,
            "include": include,
            "exclude": exclude,
            "run": selected_run,
            "recent_runs": recent_runs,
            "artifacts": artifacts,
            "ads_can_fetch": ads_can_fetch,
            "has_export_csv": True,

            # compat
            "seed": seed,
            "keyword": seed,
            "runs": runs,
            "selected_run": selected_run,
            "metrics": metrics_list,
            "mock_ads_enabled": _mock_allowed(),
            "recent_runs_rows": recent_runs_rows,
            "selected_run_admin_url": selected_run_admin_url,

            # tabs
            "ideas_broad": ideas_broad,
            "ideas_questions": ideas_questions,
            "ideas_related": ideas_related,
        },
    )




@login_required
def keyword_overview_export_pdf(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    run_id = (request.GET.get("run_id") or "").strip()
    keyword = (request.GET.get("q") or "").strip()

    run = None
    if run_id:
        run = Run.objects.filter(id=run_id).first()
    elif keyword:
        run = (
            Run.objects.filter(
                entity_object_id=project.id,
                kind__in=["keyword_research.ads.keyword_overview", "keyword_research.mock.keyword_overview"],
                inputs__keyword=keyword,
                status=Run.Status.SUCCESS,
            )
            .order_by("-created_at")
            .first()
        )

    if not run:
        return HttpResponse("Missing run_id (or q) or no successful run found.", status=400, content_type="text/plain")

    metrics = KeywordMetric.objects.filter(project=project, run=run).order_by("keyword")
    rows = list(metrics)[:50]  # MVP

    # Generar PDF a bytes
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER
    x = 0.8 * inch
    y = height - 0.8 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Keyword Overview")
    y -= 0.25 * inch

    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Project: {project.name} (ID {project.id})")
    y -= 0.18 * inch
    c.drawString(x, y, f"Run: {run.id} | Provider: {run.provider} | Kind: {run.kind}")
    y -= 0.18 * inch

    kw = (run.inputs or {}).get("keyword") or keyword or ""
    c.drawString(x, y, f"Keyword: {kw}")
    y -= 0.18 * inch
    c.drawString(x, y, f"Generated: {timezone.now().isoformat(timespec='seconds')}")
    y -= 0.35 * inch

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "Keyword")
    c.drawString(x + 3.2 * inch, y, "Avg monthly")
    c.drawString(x + 4.5 * inch, y, "CPC micros")
    c.drawString(x + 5.8 * inch, y, "Competition")
    y -= 0.15 * inch

    c.setFont("Helvetica", 9)
    if not rows:
        c.drawString(x, y, "No metrics available for this run.")
    else:
        for m in rows:
            if y < 1.0 * inch:
                c.showPage()
                y = height - 0.9 * inch
                c.setFont("Helvetica", 9)

            c.drawString(x, y, (m.keyword or "")[:45])
            c.drawRightString(x + 4.1 * inch, y, str(m.avg_monthly_searches if m.avg_monthly_searches is not None else ""))
            c.drawRightString(x + 5.4 * inch, y, str(m.cpc_micros if m.cpc_micros is not None else ""))
            c.drawString(x + 5.8 * inch, y, str(m.competition_level or ""))
            y -= 0.14 * inch

    c.setFont("Helvetica-Oblique", 8)
    y -= 0.1 * inch
    c.drawString(x, y, "Note: This report is based on stored snapshots (Run + KeywordMetric).")
    c.save()

    pdf_bytes = buf.getvalue()
    filename = f"keyword_overview_{project.id}_{str(run.id)[:8]}.pdf"

    _write_artifact(run=run, filename=filename, artifact_type=RunArtifact.ArtifactType.PDF, content_bytes=pdf_bytes)

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

@login_required
def keyword_overview_export_csv(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    run_id = (request.GET.get("run_id") or "").strip()
    keyword = (request.GET.get("q") or "").strip()

    run = None
    if run_id:
        run = Run.objects.filter(id=run_id).first()
    elif keyword:
        run = (
            Run.objects.filter(
                entity_object_id=project.id,
                kind__in=["keyword_research.ads.keyword_overview", "keyword_research.mock.keyword_overview"],
                inputs__keyword=keyword,
                status=Run.Status.SUCCESS,
            )
            .order_by("-created_at")
            .first()
        )

    if not run:
        return HttpResponse("Missing run_id (or q) or no successful run found.", status=400, content_type="text/plain")

    qs = KeywordMetric.objects.filter(project=project, run=run).order_by("keyword")

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "keyword",
        "avg_monthly_searches",
        "cpc_micros",
        "competition_level",
        "locale",
        "language",
        "geo",
        "source",
        "source_confidence",
        "retrieved_at",
        "run_id",
    ])
    for m in qs:
        w.writerow([
            m.keyword,
            m.avg_monthly_searches,
            m.cpc_micros,
            m.competition_level,
            m.locale,
            m.language,
            m.geo,
            m.source,
            m.source_confidence,
            m.retrieved_at.isoformat() if m.retrieved_at else "",
            str(run.id),
        ])

    csv_bytes = buf.getvalue().encode("utf-8")
    filename = f"keyword_overview_{project.id}_{str(run.id)[:8]}.csv"

    _write_artifact(run=run, filename=filename, artifact_type=RunArtifact.ArtifactType.CSV, content_bytes=csv_bytes)

    resp = HttpResponse(csv_bytes, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

@login_required
def keyword_magic_export_csv(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    run_id = (request.GET.get("run_id") or "").strip()
    seed = (request.GET.get("q") or "").strip()

    run = None
    if run_id:
        run = Run.objects.filter(id=run_id).first()
    elif seed:
        run = (
            Run.objects.filter(
                entity_object_id=project.id,
                kind__in=["keyword_research.ads.keyword_magic", "keyword_research.mock.keyword_magic"],
                inputs__seed=seed,
                status=Run.Status.SUCCESS,
            )
            .order_by("-created_at")
            .first()
        )

    if not run:
        return HttpResponse("Missing run_id (or q) or no successful run found.", status=400, content_type="text/plain")

    qs = KeywordMetric.objects.filter(project=project, run=run).order_by("-avg_monthly_searches", "keyword")

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "keyword",
        "avg_monthly_searches",
        "cpc_micros",
        "competition_level",
        "locale",
        "language",
        "geo",
        "source",
        "source_confidence",
        "retrieved_at",
        "run_id",
    ])
    for m in qs:
        w.writerow([
            m.keyword,
            m.avg_monthly_searches,
            m.cpc_micros,
            m.competition_level,
            m.locale,
            m.language,
            m.geo,
            m.source,
            m.source_confidence,
            m.retrieved_at.isoformat() if m.retrieved_at else "",
            str(run.id),
        ])

    csv_bytes = buf.getvalue().encode("utf-8")
    filename = f"keyword_magic_{project.id}_{str(run.id)[:8]}.csv"

    _write_artifact(run=run, filename=filename, artifact_type=RunArtifact.ArtifactType.CSV, content_bytes=csv_bytes)

    resp = HttpResponse(csv_bytes, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

from django.urls import reverse

@login_required
def runs_list(request):
    runs = Run.objects.all().order_by("-created_at")[:500]
    ctx = {"title":"Runs","subTitle":"Trazabilidad de ejecuciones","breadcrumbs":[{"label":"SEO","url":reverse("seo:dashboard")},{"label":"Runs"}],}

    return render(
        request,
        "seo/runs_list.html",
        {
            "title": "Runs",
            "subTitle": "Trazabilidad de ejecuciones",
            "breadcrumbs": [
                {"label": "SEO", "url": reverse("seo:dashboard")},
                {"label": "Runs"},
            ],
            "runs": runs,
        },
    )

import json
from django.http import Http404

@login_required
def run_detail(request, run_id):
    run = Run.objects.filter(id=run_id).first()
    if not run:
        raise Http404("Run not found")

    # ProviderResponse suele estar en core.models.ProviderResponse
    ProviderResponse = apps.get_model("core", "ProviderResponse")
    responses = ProviderResponse.objects.filter(run=run).order_by("-received_at", "-id")

    artifacts = RunArtifact.objects.filter(run=run).order_by("-created_at")

    def _pretty(obj):
        if obj is None:
            return ""
        try:
            return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
        except Exception:
            return str(obj)

    ctx = {
        "title": "Run",
        "subTitle": f"{run.provider} · {run.status}",
        "breadcrumbs": [
            {"label": "SEO", "url": reverse("seo:dashboard")},
            {"label": "Runs", "url": reverse("seo:runs_list")},
            {"label": "Run detail"},
        ],
        "run": run,
        "responses": responses,
        "artifacts": artifacts,
        "inputs_pretty": _pretty(run.inputs),
        "outputs_pretty": _pretty(run.outputs),
    }
    return render(request, "seo/run_detail.html", ctx)
