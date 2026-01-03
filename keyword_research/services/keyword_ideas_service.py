from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from keyword_research.models import KeywordIdea, KeywordIdeaRun, KeywordSeed
from keyword_research.services.google_ads_keyword_planner_provider import GoogleAdsKeywordPlannerProvider
from keyword_research.services.keyword_planner_provider import DataForSEOKeywordPlannerProvider
from keyword_research.services.dataforseo_labs_provider import DataForSEOLabsProvider


def _today_range() -> Tuple[timezone.datetime, timezone.datetime]:
    now = timezone.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _usd_to_cost_units(cost_usd: float) -> int:
    """
    Unidades internas: 1 = 0.001 USD (milli-dollar).
    """
    try:
        return int(round(float(cost_usd) * 1000))
    except Exception:
        return 0


def _extract_status_and_cost(raw: Any) -> Tuple[int, int]:
    """
    Intenta extraer status_code y cost (USD) desde respuestas típicas de DataForSEO.
    Devuelve: (response_status, cost_units)
    """
    if not isinstance(raw, dict):
        return 0, 0

    # DataForSEO suele tener status_code en raíz o tasks[0].status_code
    status = int(raw.get("status_code") or 0)

    cost_units = 0
    tasks = raw.get("tasks")
    if isinstance(tasks, list) and tasks:
        t0 = tasks[0] or {}
        if not status:
            status = int(t0.get("status_code") or 0)
        # cost en USD
        cost_usd = t0.get("cost") or 0.0
        cost_units += _usd_to_cost_units(cost_usd)

    return status, cost_units


class KeywordIdeasService:
    """
    Ahorro máximo:
    - Cache 24h por cache_key (project + seed + location_code + language_code + top_n + provider + fallback_flag)
    - Rate limit: 2 seeds NUEVOS / día / proyecto (solo la primera vez histórica para ese seed+loc+lang)
    - Flujo:
        1) Google Ads (si está configurado + project.customer_id)
        2) DataForSEO Keywords Data keywords_for_keywords (cobra aunque venga vacío)
        3) (Opcional) DataForSEO Labs keyword_suggestions SOLO si use_fallback=True (costo extra)
    - Dedupe: no re-guardar keywords ya guardadas en el proyecto (a nivel KeywordIdea del proyecto)
    """

    TTL_HOURS = 24

    def __init__(self) -> None:
        self.google = GoogleAdsKeywordPlannerProvider()
        self.dataforseo = DataForSEOKeywordPlannerProvider()
        self.labs = DataForSEOLabsProvider()

    def _cache_key(
        self,
        *,
        project_id: int,
        seed: str,
        location_code: int,
        language_code: str,
        top_n: int,
        provider_hint: str,
        use_fallback: bool,
    ) -> str:
        # clave simple y trazable (máx 120 en modelo)
        # provider_hint es “auto” al inicio; luego se guarda provider real en run.provider
        base = f"p={project_id}|seed={seed}|loc={location_code}|lang={language_code}|top={top_n}|prov={provider_hint}|fb={int(use_fallback)}"
        # acotamos longitud con hash simple
        import hashlib

        h = hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]
        return f"kw_ideas:{h}"

    def _get_cached_run(self, *, project, cache_key: str, use_fallback: bool) -> Optional[KeywordIdeaRun]:
        now = timezone.now()
        cached = (
            KeywordIdeaRun.objects.filter(
                project=project,
                cache_key=cache_key,
                cache_expires_at__gt=now,
                status=KeywordIdeaRun.Status.COMPLETED,
            )
            .order_by("-id")
            .first()
        )
        if not cached:
            return None

        # Si tiene ideas, siempre sirve. Si no tiene ideas, sirve solo si NO pidieron fallback.
        if cached.ideas.exists():
            cached.from_cache = True
            return cached

        if not use_fallback:
            cached.from_cache = True
            return cached

        # use_fallback=True y cached está vacío => seguimos y hacemos llamada fresca
        return None

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

        # --- seed_ref (persistente, opcional) ---
        seed_ref = KeywordSeed.objects.filter(project=project, kind=KeywordSeed.Kind.KEYWORD, seed=seed).first()
        if not seed_ref:
            # lo mínimo: solo persistimos el seed; geo/device quedan defaults/null (MVP)
            seed_ref = KeywordSeed.objects.create(project=project, kind=KeywordSeed.Kind.KEYWORD, seed=seed)

        # --- cache key (MVP: provider_hint="auto") ---
        cache_key = self._cache_key(
            project_id=project.id,
            seed=seed,
            location_code=loc,
            language_code=lang,
            top_n=top_n,
            provider_hint="auto",
            use_fallback=use_fallback,
        )

        # 1) CACHE REAL (TTL 24h)
        cached = self._get_cached_run(project=project, cache_key=cache_key, use_fallback=use_fallback)
        if cached:
            return cached

        # 2) RATE LIMIT (solo si es primera vez histórica para seed+loc+lang)
        has_ever_run = KeywordIdeaRun.objects.filter(
            project=project,
            seed_keyword=seed,
            location_code=loc,
            language_code=lang,
        ).exists()

        is_first_time_seed = not has_ever_run
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

        # 3) Crear run RUNNING antes de llamar a proveedores (tiene trazabilidad incluso si falla)
        now = timezone.now()
        run = KeywordIdeaRun.objects.create(
            project=project,
            seed_ref=seed_ref,
            seed_keyword=seed,
            location_code=loc,
            language_code=lang,
            provider=KeywordIdeaRun.Provider.DATAFORSEO,  # default; luego lo corregimos
            status=KeywordIdeaRun.Status.RUNNING,
            requested_at=now,
            cache_key=cache_key,
            cache_expires_at=now + timedelta(hours=self.TTL_HOURS),
            from_cache=False,
            is_new_seed=bool(is_first_time_seed),
            error="",
            raw={},
            response_status=0,
            cost_units=0,
        )

        provider = None
        error_msg = ""
        raw_bundle: Dict[str, Any] = {}
        ideas_payload = []

        try:
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
                    raw_bundle["google_ads"] = g.get("raw") if isinstance(g, dict) else g
                    ideas_payload = (g.get("ideas") or []) if isinstance(g, dict) else []
                    if ideas_payload:
                        provider = KeywordIdeaRun.Provider.GOOGLE_ADS
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
                raw_bundle["dataforseo_keywords_for_keywords"] = k.get("raw") if isinstance(k, dict) else k
                ideas_payload = (k.get("ideas") or []) if isinstance(k, dict) else []
                provider = KeywordIdeaRun.Provider.DATAFORSEO

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
                raw_bundle["dataforseo_labs_keyword_suggestions"] = l.get("raw") if isinstance(l, dict) else l
                ideas_payload = (l.get("ideas") or []) if isinstance(l, dict) else []
                provider = KeywordIdeaRun.Provider.DATAFORSEO_LABS

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

            # 5) Persistir ideas + finalizar run
            with transaction.atomic():
                # bulk ideas
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

                # trazabilidad: response_status + cost_units (DataForSEO)
                response_status = 0
                cost_units = 0
                for _, blob in raw_bundle.items():
                    st, cu = _extract_status_and_cost(blob)
                    response_status = response_status or st
                    cost_units += cu

                run.provider = provider or KeywordIdeaRun.Provider.DATAFORSEO
                run.status = KeywordIdeaRun.Status.COMPLETED
                run.completed_at = timezone.now()
                run.error = error_msg
                run.raw = raw_bundle
                run.response_status = int(response_status or 0)
                run.cost_units = int(cost_units or 0)
                run.save(
                    update_fields=[
                        "provider",
                        "status",
                        "completed_at",
                        "error",
                        "raw",
                        "response_status",
                        "cost_units",
                    ]
                )

            return run

        except Exception as e:
            # falla dura: persistimos run FAILED con raw_bundle parcial
            run.provider = provider or KeywordIdeaRun.Provider.DATAFORSEO
            run.status = KeywordIdeaRun.Status.FAILED
            run.completed_at = timezone.now()
            run.error = (error_msg + " | " if error_msg else "") + f"Exception: {e}"
            run.raw = raw_bundle
            run.save(update_fields=["provider", "status", "completed_at", "error", "raw"])
            return run
