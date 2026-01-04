# seo/views.py
import csv
import hashlib
import io
import os
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.utils import timezone

from projects.models import Project
from integrations.models import IntegrationStatus
from core.models import Run, RunArtifact
from keyword_research.models import KeywordMetric

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch


def _mock_allowed() -> bool:
    return bool(settings.DEBUG) and os.environ.get("SEOSUITE_ALLOW_MOCK_ADS", "0") == "1"


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
        "project": project,
        "providers": providers,
        "provider_rows": provider_rows,
        "checklist": checklist,
        "mock_ads_enabled": _mock_allowed(),
    }
    return render(request, "seo/project_setup.html", ctx)



def keyword_overview(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    keyword = (request.GET.get("q") or "").strip()
    run_id = (request.GET.get("run_id") or "").strip()

    selected_run = None
    metrics = KeywordMetric.objects.none()
    runs = Run.objects.none()

    if keyword:
        base_qs = Run.objects.filter(
            kind__in=["keyword_research.ads.keyword_overview", "keyword_research.mock.keyword_overview"],
            entity_object_id=project.id,
            inputs__keyword=keyword,
        ).order_by("-created_at")

        runs = base_qs[:20]

        if run_id:
            selected_run = Run.objects.filter(id=run_id).first()
        else:
            selected_run = base_qs.filter(status=Run.Status.SUCCESS).first()

    elif run_id:
        selected_run = Run.objects.filter(id=run_id).first()

    if selected_run:
        metrics = KeywordMetric.objects.filter(project=project, run=selected_run).order_by("keyword")

    ctx = {
        "project": project,
        "keyword": keyword,
        "runs": runs,
        "selected_run": selected_run,
        "metrics": metrics,
        "mock_ads_enabled": _mock_allowed(),
    }
    return render(request, "seo/keyword_overview.html", ctx)


def keyword_magic(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)

    seed = (request.GET.get("q") or "").strip()
    run_id = (request.GET.get("run_id") or "").strip()

    selected_run = None
    metrics = KeywordMetric.objects.none()
    runs = Run.objects.none()

    if seed:
        base_qs = Run.objects.filter(
            kind__in=["keyword_research.ads.keyword_magic", "keyword_research.mock.keyword_magic"],
            entity_object_id=project.id,
            inputs__seed=seed,
        ).order_by("-created_at")

        runs = base_qs[:20]

        if run_id:
            selected_run = Run.objects.filter(id=run_id).first()
        else:
            selected_run = base_qs.filter(status=Run.Status.SUCCESS).first()

    elif run_id:
        selected_run = Run.objects.filter(id=run_id).first()

    if selected_run:
        metrics = KeywordMetric.objects.filter(project=project, run=selected_run).order_by("-avg_monthly_searches", "keyword")[:200]

    return render(
        request,
        "seo/keyword_magic.html",
        {
            "project": project,
            "seed": seed,
            "runs": runs,
            "selected_run": selected_run,
            "metrics": metrics,
            "mock_ads_enabled": _mock_allowed(),
        },
    )


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
