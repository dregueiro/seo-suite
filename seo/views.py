# seo/views.py
import csv
import io
import hashlib
from pathlib import Path

from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

from projects.models import Project
from integrations.models import IntegrationStatus
from core.models import Run, RunArtifact
from keyword_research.models import KeywordMetric

def artifact_mime(artifact_type: str) -> str:
    return {"csv":"text/csv", "pdf":"application/pdf", "json":"application/json", "text":"text/plain"}.get(artifact_type, "application/octet-stream")

def _write_artifact(run, filename: str, artifact_type: str, content_bytes: bytes) -> RunArtifact:
    base_dir = Path(settings.BASE_DIR) / "artifacts" / str(run.id)
    base_dir.mkdir(parents=True, exist_ok=True)

    path = base_dir / filename
    path.write_bytes(content_bytes)

    sha = hashlib.sha256(content_bytes).hexdigest()

    return RunArtifact.objects.create(
        run=run,
        name=filename,
        artifact_type=artifact_type,          # ej: "text/csv" o "application/pdf"
        storage_path=str(path),               # trazable (ruta local)
        sha256=sha,
        size_bytes=len(content_bytes),
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
                status="success",
            )
            .order_by("-created_at")
            .first()
        )

    if not run:
        return HttpResponse(
            "Missing run_id (or q) or no successful run found.",
            status=400,
            content_type="text/plain",
        )

    metrics = KeywordMetric.objects.filter(project=project, run=run).order_by("keyword")

    filename = f"keyword_overview_{project.id}_{str(run.id)[:8]}.pdf"

    # 1) Generar PDF en memoria
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
    rows = list(metrics)[:50]

    if not rows:
        c.drawString(x, y, "No metrics available for this run.")
    else:
        for m in rows:
            if y < 1.0 * inch:
                c.showPage()
                y = height - 0.9 * inch
                c.setFont("Helvetica", 9)

            c.drawString(x, y, (m.keyword or "")[:45])
            c.drawRightString(x + 4.1 * inch, y, str(m.avg_monthly_searches or ""))
            c.drawRightString(x + 5.4 * inch, y, str(m.cpc_micros or ""))
            c.drawString(x + 5.8 * inch, y, str(m.competition_level or ""))
            y -= 0.14 * inch

    c.setFont("Helvetica-Oblique", 8)
    y -= 0.1 * inch
    c.drawString(x, y, "Note: This report is based on stored snapshots (Run + KeywordMetric).")

    c.save()
    pdf_bytes = buf.getvalue()

    # 2) Guardar artifact
    _write_artifact(run, filename, RunArtifact.ArtifactType.PDF, pdf_bytes)


    # 3) Responder
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
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
                status="success",
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

    filename = f"keyword_magic_{project.id}_{str(run.id)[:8]}.csv"
    content = buf.getvalue().encode("utf-8")

    _write_artifact(run, filename, RunArtifact.ArtifactType.CSV, content)


    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp



def keyword_magic(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)
    seed = (request.GET.get("q") or "").strip()
    run_id = (request.GET.get("run_id") or "").strip()

    runs = Run.objects.none()
    selected_run = None
    metrics = KeywordMetric.objects.none()

    if seed:
        runs = Run.objects.filter(inputs__seed=seed).order_by("-created_at")[:20]

    if run_id:
        selected_run = Run.objects.filter(id=run_id).first()
    elif seed:
        selected_run = runs.filter(status="success").first()

    if selected_run:
        metrics = KeywordMetric.objects.filter(project=project, run=selected_run).order_by("-avg_monthly_searches")[:200]

    return render(request, "seo/keyword_magic.html", {
        "project": project,
        "seed": seed,
        "runs": runs,
        "selected_run": selected_run,
        "metrics": metrics,
    })


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
                provider__in=[Run.Provider.ADS, "internal"],
                kind__in=[
                    "keyword_research.ads.keyword_overview",
                    "keyword_research.mock.keyword_overview",
                ],
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

