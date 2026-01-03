from __future__ import annotations

from datetime import timedelta
from typing import Optional, Tuple

from django.utils import timezone
from django.conf import settings

from core.services.cache_keys import serp_cache_key
from integrations.serp.types import SerpRequest, SerpParsed

from serp.models import SerpRun

from serp.services.dataforseo_provider import DataForSEOProvider
from serp.services.serpapi_provider import SerpApiProvider

from projects.models import Project  # si prefieres type hints

DEFAULT_TTL_SECONDS = getattr(settings, "CACHE_TTL_SERP_SECONDS", 86400)


def choose_provider(req: SerpRequest) -> str:
    return "serpapi"


def _get_cached_run(cache_key: str) -> Optional[SerpRun]:
    now = timezone.now()
    return (
        SerpRun.objects.filter(cache_key=cache_key, status="done")
        .filter(cache_expires_at__gt=now)
        .order_by("-id")
        .first()
    )






def fetch_serp(project, req: SerpRequest):
    """
    Retorna: (parsed, serp_run, from_cache)
    """
    provider = choose_provider(req)
    cache_key = serp_cache_key(req, provider)

    cached = _get_cached_run(cache_key)
    if cached and cached.raw:
        raw = cached.raw
        if provider == "dataforseo":
            parsed = DataForSEOProvider().parse_top10(raw)
        else:
            parsed = SerpApiProvider.parse_raw(raw)
        return parsed, cached, True

    expires_at = timezone.now() + timedelta(seconds=DEFAULT_TTL_SECONDS)

    run = SerpRun.objects.create(
        project=project,              # <-- CLAVE
        provider=provider,
        run_type="rank_tracking",
        status="running",
        cache_key=cache_key,
        cache_expires_at=expires_at,
    )

    try:
        if provider == "dataforseo":
            raise RuntimeError("DataForSEO provider selected but fetch path not wired to request yet.")
        parsed = SerpApiProvider().fetch_parsed(req)

        run.raw = parsed.raw
        run.status = "done"
        run.response_status = 200
        run.cost_units = 0
        run.save(update_fields=["raw", "status", "response_status", "cost_units"])
        return parsed, run, False

    except Exception as e:
        run.status = "failed"
        run.response_status = 500
        run.raw = {"error": str(e)}
        run.save(update_fields=["raw", "status", "response_status"])
        raise

