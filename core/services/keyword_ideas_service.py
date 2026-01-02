from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.models import KeywordIdea, KeywordIdeaRun
from core.services.google_ads_keyword_planner_provider import GoogleAdsKeywordPlannerProvider
from core.services.keyword_planner_provider import DataForSEOKeywordPlannerProvider
from core.services.dataforseo_labs_provider import DataForSEOLabsProvider


def _today_range():
    now = timezone.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timezone.timedelta(days=1)
    return start, end


class KeywordIdeasService:
    """
    Ahorro máximo:
    - Cache por (project, seed, location_code, language_code)
    - Rate limit: 2 seeds NUEVOS / día / proyecto (solo la primera vez)
    - Flujo:
        1) Google Ads (si está configurado + project.customer_id)
        2) DataForSEO Keywords Data keywords_for_keywords (cobra aunque venga vacío)
        3) (Opcional) DataForSEO Labs keyword_suggestions SOLO si use_fallback=True (costo extra)
    - Dedupe: no re-guardar keywords ya guardadas en el proyecto
    """

    def __init__(self):
        self.google = GoogleAdsKeywordPlannerProvider()
        self.dataforseo = DataForSEOKeywordPlannerProvider()
        self.labs = DataForSEOLabsProvider()

    def get_or_create_run(
        self,
        *,
        project,
        seed_keyword: str,
        location_code: int,
        language_code: str,
        top_n: int = 15,
        use_fallback: bool = False,
    ) -> KeywordIdeaRun:
        seed = (seed_keyword or "").strip().lower()
        lang = (language_code or "en").strip().lower()
        loc = int(location_code or 2840)
        top_n = int(top_n or 15)

        if not seed:
            raise ValueError("seed_keyword es requerido")

        # 1) CACHE
        cached = (
            KeywordIdeaRun.objects.filter(
                project=project,
                seed_keyword=seed,
                location_code=loc,
                language_code=lang,
            )
            .order_by("-id")
            .first()
        )
        if cached:
            if cached.ideas.count() > 0:
                cached.from_cache = True  # solo para UI
                return cached
            if not use_fallback:
                cached.from_cache = True
                return cached

        # 2) RATE LIMIT solo si es primera vez (no existe cached para ese seed/loc/lang)
        is_first_time_seed = cached is None
        if is_first_time_seed:
            start, end = _today_range()
            new_today = KeywordIdeaRun.objects.filter(
                project=project,
                is_new_seed=True,
                created_at__gte=start,
                created_at__lt=end,
            ).count()
            if new_today >= 2:
                raise RuntimeError("Límite: este proyecto solo puede hacer 2 búsquedas NUEVAS por día.")

        provider_used = None
        error_msg = ""
        raw_bundle = {}
        ideas_payload = []

        # 3.1 Google Ads
        customer_id = (getattr(project, "google_ads_customer_id", "") or "").strip()
        if customer_id and self.google.is_configured():
            try:
                g = self.google.generate_keyword_ideas(
                    customer_id=customer_id,
                    seed_keyword=seed,
                    location_code=loc,
                    language_code=lang,
                    top_n=top_n,
                )
                raw_bundle["google_ads"] = g.get("raw") or g
                ideas_payload = g.get("ideas") or []
                if ideas_payload:
                    provider_used = KeywordIdeaRun.Provider.GOOGLE_ADS
                else:
                    error_msg = "Google Ads no devolvió ideas para este seed (puede pasar con keywords muy nicho)."
            except Exception as e:
                error_msg = f"Google Ads failed: {e}"

        # 3.2 DataForSEO Keywords Data
        if not ideas_payload:
            k = self.dataforseo.keywords_for_keywords_live(
                seed_keyword=seed,
                location_code=loc,
                language_code=lang,
                top_n=top_n,
            )
            raw_bundle["dataforseo_keywords_for_keywords"] = k.get("raw") or k
            ideas_payload = k.get("ideas") or []
            provider_used = KeywordIdeaRun.Provider.DATAFORSEO

            if not ideas_payload:
                error_msg = (
                    (error_msg + " | " if error_msg else "")
                    + "DataForSEO (Keywords For Keywords) devolvió 0 ideas para este seed en ese país/idioma."
                )

        # 3.3 Fallback DataForSEO Labs (solo si el usuario lo pide)
        if use_fallback and not ideas_payload:
            l = self.labs.keyword_suggestions_live(
                seed_keyword=seed,
                location_code=loc,
                language_code=lang,
                limit=top_n,
            )
            raw_bundle["dataforseo_labs_keyword_suggestions"] = l.get("raw") or l
            ideas_payload = l.get("ideas") or []
            provider_used = KeywordIdeaRun.Provider.DATAFORSEO_LABS

            if not ideas_payload:
                error_msg = (
                    (error_msg + " | " if error_msg else "")
                    + "Fallback (DataForSEO Labs) también devolvió 0 ideas."
                )

        ideas_payload = ideas_payload or []

        # 4) DEDUPE en TODO el proyecto
        incoming_keywords = [
            (i.get("keyword") or "").strip().lower()
            for i in ideas_payload
            if (i.get("keyword") or "").strip()
        ]
        existing = set(
            KeywordIdea.objects.filter(run__project=project, keyword__in=incoming_keywords)
            .values_list("keyword", flat=True)
        )

        filtered = []
        for i in ideas_payload:
            kw = (i.get("keyword") or "").strip().lower()
            if not kw:
                continue
            if kw in existing:
                continue
            filtered.append(i)

        # 5) Guardar run + ideas
        with transaction.atomic():
            run = KeywordIdeaRun.objects.create(
                project=project,
                seed_keyword=seed,
                location_code=loc,
                language_code=lang,
                provider_used=provider_used or KeywordIdeaRun.Provider.DATAFORSEO,
                from_cache=False,
                is_new_seed=bool(is_first_time_seed),
                error=error_msg,
                raw=raw_bundle,
            )

            KeywordIdea.objects.bulk_create(
                [
                    KeywordIdea(
                        run=run,
                        keyword=(r.get("keyword") or "").strip().lower(),
                        search_volume=int(r.get("search_volume") or 0),
                        competition_index=r.get("competition_index"),
                        low_top_of_page_bid=r.get("low_top_of_page_bid"),
                        high_top_of_page_bid=r.get("high_top_of_page_bid"),
                        cpc=r.get("cpc"),
                        raw=r.get("raw"),
                    )
                    for r in filtered[:top_n]
                ],
                ignore_conflicts=True,
            )

        return run
