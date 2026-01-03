from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from django.db import IntegrityError, transaction
from django.utils import timezone

from keyword_research.models import Keyword, KeywordIdea, KeywordSeed
from keyword_research.services.keyword_ideas_service import KeywordIdeasService
from keyword_research.services.keyword_metrics_service import KeywordMetricsService


def _get_location_code(obj, default: int = 2840) -> int:
    """
    Intenta mapear country -> location_code para DataForSEO.
    Usa atributos comunes si existen.
    """
    country = getattr(obj, "country", None)
    if not country:
        return default
    for attr in ("dataforseo_location_code", "location_code", "dfs_location_code"):
        val = getattr(country, attr, None)
        if isinstance(val, int) and val > 0:
            return val
        # algunos modelos guardan como str numérica
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return default


def _get_language_code(obj, default: str = "en") -> str:
    lang = getattr(obj, "language", None)
    if not lang:
        return default
    code = getattr(lang, "code", None) or getattr(lang, "lang_code", None) or getattr(lang, "iso_code", None)
    code = (code or "").strip().lower()
    return code or default


def _project_city_device(project) -> Tuple[str, str]:
    city = (getattr(project, "city", "") or "").strip()
    device = (getattr(project, "device", "") or "").strip()
    return city, device


@dataclass
class RunIdeasResult:
    created: int = 0
    cached: int = 0
    failed: int = 0


@dataclass
class EnrichMetricsResult:
    created: int = 0
    cached: int = 0
    failed: int = 0


@dataclass
class AddIdeasResult:
    created: int = 0
    skipped: int = 0


def run_ideas_for_seeds(
    *,
    seeds: Iterable[KeywordSeed],
    top_n: int = 15,
    use_fallback: bool = False,
) -> RunIdeasResult:
    svc = KeywordIdeasService()
    out = RunIdeasResult()

    for seed in seeds:
        project = seed.project
        seed_text = (seed.seed or "").strip().lower()
        if not seed_text:
            out.failed += 1
            continue

        location_code = _get_location_code(seed)
        language_code = _get_language_code(seed)

        run = svc.get_or_create_run(
            project=project,
            seed_keyword=seed_text,
            location_code=location_code,
            language_code=language_code,
            top_n=top_n,
            use_fallback=use_fallback,
        )

        # Si devolvió cached, el service setea from_cache=True
        if getattr(run, "from_cache", False):
            out.cached += 1
        elif getattr(run, "status", "") == "failed":
            out.failed += 1
        else:
            out.created += 1

    return out


def enrich_metrics_for_keywords(
    *,
    keywords: Iterable[Keyword],
    priority_min: int = 1,
) -> EnrichMetricsResult:
    svc = KeywordMetricsService()
    out = EnrichMetricsResult()

    # agrupar por proyecto para llamar una vez por proyecto
    by_project = {}
    for k in keywords:
        if getattr(k, "priority", 0) < priority_min:
            continue
        by_project.setdefault(k.project_id, {"project": k.project, "items": []})
        by_project[k.project_id]["items"].append(k)

    for _, grp in by_project.items():
        project = grp["project"]
        items = grp["items"]

        # heurística: usar geo defaults del primer keyword si existen, si no fallback.
        loc = _get_location_code(items[0]) if items else _get_location_code(project)
        lang = _get_language_code(items[0]) if items else _get_language_code(project)

        run = svc.enrich(
            project=project,
            keywords=items,
            location_code=loc,
            language_code=lang,
        )

        if run.status == "completed":
            # cache detection: si requested_at es antiguo y ya existía run, el service devuelve cached
            # (en tu service actual, si devuelve cached, no cambia nada; lo inferimos por TTL)
            # Para admin: consideramos cached si requested_at < now-1s y run ya existía.
            # Simplificación: si cache_expires_at > now y status completed, contamos como cached solo si no creó snapshots nuevos.
            out.created += 1
        elif run.status == "failed":
            out.failed += 1
        else:
            out.created += 1

    return out


def add_ideas_to_tracked_keywords(*, ideas: Iterable[KeywordIdea]) -> AddIdeasResult:
    out = AddIdeasResult()

    # prefetch por proyecto para defaults
    with transaction.atomic():
        for idea in ideas:
            project = idea.run.project
            kw = (idea.keyword or "").strip().lower()
            if not kw:
                out.skipped += 1
                continue

            # defaults desde project si existen
            country = getattr(project, "country", None)
            language = getattr(project, "language", None)
            city, device = _project_city_device(project)

            try:
                Keyword.objects.create(
                    project=project,
                    keyword=kw,
                    country=country,
                    language=language,
                    city=city,
                    device=device,
                    status=Keyword.Status.ACTIVE,
                    priority=3,
                )
                out.created += 1
            except IntegrityError:
                out.skipped += 1

    return out
