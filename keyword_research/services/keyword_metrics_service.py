from __future__ import annotations

import time
from datetime import timedelta
from typing import Iterable, List, Tuple

from django.db import transaction
from django.utils import timezone

from keyword_research.models import Keyword, KeywordMetricsRun, KeywordMetricSnapshot
from keyword_research.services.keyword_metrics_provider import DataForSEOKeywordMetricsProvider


def usd_to_cost_units(cost_usd: float) -> int:
    # 1 unit = 0.001 USD
    try:
        return int(round(float(cost_usd) * 1000))
    except Exception:
        return 0


def extract_status_and_cost(raw: dict) -> Tuple[int, int]:
    if not isinstance(raw, dict):
        return 0, 0

    status = int(raw.get("status_code") or 0)
    cost_units = 0

    tasks = raw.get("tasks")
    if isinstance(tasks, list) and tasks:
        t0 = tasks[0] or {}
        if not status:
            status = int(t0.get("status_code") or 0)
        cost_units += usd_to_cost_units(t0.get("cost") or 0.0)

    return status, cost_units


class KeywordMetricsService:
    TTL_HOURS = 24
    CHUNK_SIZE = 1000
    SLEEP_SECONDS = 6  # MVP: evita rate-limit si hay múltiples chunks

    def __init__(self) -> None:
        self.provider = DataForSEOKeywordMetricsProvider()

    def _cache_key(self, *, project_id: int, location_code: int, language_code: str, count: int) -> str:
        import hashlib

        base = f"p={project_id}|loc={location_code}|lang={language_code}|count={count}"
        h = hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]
        return f"kw_metrics:{h}"

    def enrich(
        self,
        *,
        project,
        keywords: Iterable[Keyword],
        location_code: int,
        language_code: str,
        provider: str = "dataforseo",
    ) -> KeywordMetricsRun:
        now = timezone.now()

        kw_list = [k.keyword.strip().lower() for k in keywords if k.keyword]
        kw_list = list(dict.fromkeys(kw_list))  # dedupe

        cache_key = self._cache_key(
            project_id=project.id,
            location_code=int(location_code),
            language_code=(language_code or "en").strip().lower(),
            count=len(kw_list),
        )

        cached = (
            KeywordMetricsRun.objects.filter(
                project=project,
                provider=provider,
                cache_key=cache_key,
                cache_expires_at__gt=now,
                status=KeywordMetricsRun.Status.COMPLETED,
            )
            .order_by("-id")
            .first()
        )
        if cached:
            return cached

        run = KeywordMetricsRun.objects.create(
            project=project,
            provider=provider,
            status=KeywordMetricsRun.Status.RUNNING,
            location_code=int(location_code),
            language_code=(language_code or "en").strip().lower(),
            requested_at=now,
            cache_key=cache_key,
            cache_expires_at=now + timedelta(hours=self.TTL_HOURS),
            keywords_count=len(kw_list),
            response_status=0,
            cost_units=0,
            raw_json={"chunks": []},
        )

        total_cost_units = 0
        response_status = 0

        try:
            # map keyword text -> Keyword model
            by_kw = {k.keyword.strip().lower(): k for k in Keyword.objects.filter(project=project)}

            for i in range(0, len(kw_list), self.CHUNK_SIZE):
                chunk = kw_list[i : i + self.CHUNK_SIZE]
                out = self.provider.search_volume_live(
                    keywords=chunk,
                    location_code=int(location_code),
                    language_code=(language_code or "en").strip().lower(),
                )

                raw = out.get("raw") or {}
                run.raw_json["chunks"].append(raw)

                st, cu = extract_status_and_cost(raw)
                response_status = response_status or st
                total_cost_units += cu

                rows = out.get("rows") or []
                self._bulk_snapshots(run=run, by_kw=by_kw, rows=rows)

                if i + self.CHUNK_SIZE < len(kw_list):
                    time.sleep(self.SLEEP_SECONDS)

            run.status = KeywordMetricsRun.Status.COMPLETED
            run.completed_at = timezone.now()
            run.response_status = int(response_status or 0)
            run.cost_units = int(total_cost_units or 0)
            run.save(update_fields=["status", "completed_at", "response_status", "cost_units", "raw_json"])
            return run

        except Exception as e:
            run.status = KeywordMetricsRun.Status.FAILED
            run.completed_at = timezone.now()
            run.raw_json = {"error": str(e), **(run.raw_json or {})}
            run.save(update_fields=["status", "completed_at", "raw_json"])
            return run

    @transaction.atomic
    def _bulk_snapshots(self, *, run: KeywordMetricsRun, by_kw: dict, rows: List) -> None:
        objs: List[KeywordMetricSnapshot] = []
        for r in rows:
            kw_txt = getattr(r, "keyword", "") if not isinstance(r, dict) else (r.get("keyword") or "")
            kw_txt = (kw_txt or "").strip().lower()
            kw_obj = by_kw.get(kw_txt)
            if not kw_obj:
                continue

            # r puede ser dataclass o dict
            def _get(name, default=None):
                if isinstance(r, dict):
                    return r.get(name, default)
                return getattr(r, name, default)

            objs.append(
                KeywordMetricSnapshot(
                    run=run,
                    keyword=kw_obj,
                    search_volume=_get("search_volume"),
                    competition=_get("competition") or "",
                    competition_index=_get("competition_index"),
                    cpc=_get("cpc"),
                    low_top_of_page_bid=_get("low_top_of_page_bid"),
                    high_top_of_page_bid=_get("high_top_of_page_bid"),
                    monthly_searches=_get("monthly_searches"),
                    raw=_get("raw"),
                )
            )

        KeywordMetricSnapshot.objects.bulk_create(objs, ignore_conflicts=True)
