import csv
import io

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from keyword_research.models import Keyword
from projects.forms import KeywordImportForm
from django.core.paginator import Paginator
from django.db.models import Q
from projects.models import Project
from geo.models import Country, Language

def _normalize_kw(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def keyword_import(request):
    if request.method == "POST":
        form = KeywordImportForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.cleaned_data["project"]

            country = form.cleaned_data.get("country")
            city = (form.cleaned_data.get("city") or "").strip()
            language = form.cleaned_data.get("language")
            device = (form.cleaned_data.get("device") or "").strip().lower()

            created = 0
            skipped = 0
            seen = set()

            # 1) From textarea
            raw_text = form.cleaned_data.get("keywords_text") or ""
            lines = [l for l in raw_text.splitlines() if l.strip()]

            # 2) From CSV (optional)
            csv_file = form.cleaned_data.get("csv_file")
            if csv_file:
                content = csv_file.read().decode("utf-8", errors="ignore")
                reader = csv.DictReader(io.StringIO(content))
                # Expect a column named 'keyword' (case-insensitive)
                for row in reader:
                    k = row.get("keyword") or row.get("Keyword") or row.get("KW") or ""
                    if k.strip():
                        lines.append(k)

            # Normalize and dedupe within request
            normalized = []
            for kw in lines:
                k = _normalize_kw(kw)
                if not k:
                    continue
                if k in seen:
                    continue
                seen.add(k)
                normalized.append(k)

            # Insert with DB-level dedupe (UniqueConstraint)
            for k in normalized:
                try:
                    with transaction.atomic():
                        Keyword.objects.create(
                            project=project,
                            keyword=k,
                            country=country,
                            city=city,
                            language=language,
                            device=device,
                        )
                    created += 1
                except IntegrityError:
                    skipped += 1

            messages.success(
                request,
                f"Import complete. Created: {created}. Skipped (duplicates): {skipped}.",
            )
            return redirect("keyword_import")
    else:
        form = KeywordImportForm()


    return render(request, "projects/keyword_import.html", {"form": form})


def keyword_list(request):
    project_id = request.GET.get("project") or ""
    status = request.GET.get("status") or ""
    q = (request.GET.get("q") or "").strip()
    country_id = request.GET.get("country") or ""
    language_id = request.GET.get("language") or ""

    qs = Keyword.objects.select_related("project", "project__client", "country", "language")

    if project_id:
        qs = qs.filter(project_id=project_id)

    if status:
        qs = qs.filter(status=status)

    if country_id:
        qs = qs.filter(country_id=country_id)

    if language_id:
        qs = qs.filter(language_id=language_id)

    if q:
        qs = qs.filter(
            Q(keyword__icontains=q) |
            Q(target_url__icontains=q) |
            Q(project__name__icontains=q) |
            Q(project__domain__icontains=q)
        )

    qs = qs.order_by("-updated_at")

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "projects": Project.objects.select_related("client").order_by("client__name", "name"),
        "countries": Country.objects.order_by("name"),
        "languages": Language.objects.order_by("name"),
        "status_choices": Keyword.Status.choices,
        "filters": {
            "project": project_id,
            "status": status,
            "q": q,
            "country": country_id,
            "language": language_id,
        },
    }
    return render(request, "projects/keyword_list.html", context)
