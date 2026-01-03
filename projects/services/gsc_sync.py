from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from core.services.cache_keys import gsc_cache_key
from integrations.gsc.client import GscClient, GscQueryRequest
from projects.models import Project, GscRow, GscSyncRun


DEFAULT_DIMENSIONS = ["query", "page", "country", "device"]


@dataclass(frozen=True)
class SyncResult:
    run: GscSyncRun
    served_from_cache: bool


def _parse_yyyy_mm_dd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _daterange(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur = cur + timedelta(days=1)


class GscSyncService:
    TTL_HOURS = 24
    ROW_LIMIT = 25000

    def __init__(self) -> None:
        self.client = GscClient()

    def sync_project(
        self,
        *,
        project: Project,
        start_date: str,
        end_date: str,
        dimensions: Optional[list[str]] = None,
        filters: Optional[dict] = None,
    ) -> list[SyncResult]:
        if not project.gsc_website_link:
            raise ValueError("Project is missing gsc_website_link (Project.gsc_website_link).")

        dims = dimensions or DEFAULT_DIMENSIONS
        filt = filters or {}

        start = _parse_yyyy_mm_dd(start_date)
        end = _parse_yyyy_mm_dd(end_date)

        results: list[SyncResult] = []
        for day in _daterange(start, end):
            results.append(self._sync_one_day(project=project, day=day, dimensions=dims, filters=filt))
        return results

    def _sync_one_day(
        self,
        *,
        project: Project,
        day: date,
        dimensions: list[str],
        filters: dict,
    ) -> SyncResult:
        now = timezone.now()
        site_url = project.gsc_website_link.strip()
        cache_key = gsc_cache_key(
            project_id=project.id,
            site_url=site_url,
            date=str(day),
            dimensions=dimensions,
            filters=filters,
        )

        cached = (
            GscSyncRun.objects.filter(
                project=project,
                cache_key=cache_key,
                cache_expires_at__gt=now,
                status=GscSyncRun.Status.COMPLETED,
            )
            .order_by("-requested_at")
            .first()
        )
        if cached:
            return SyncResult(run=cached, served_from_cache=True)

        run = GscSyncRun.objects.create(
            project=project,
            site_url=site_url,
            date=day,
            dimensions_json=dimensions,
            filters_json=filters,
            status=GscSyncRun.Status.RUNNING,
            requested_at=now,
            cache_key=cache_key,
            cache_expires_at=now + timedelta(hours=self.TTL_HOURS),
        )

        total_fetched = 0
        total_upserted = 0
        raw_bundle = {"pages": []}

        try:
            start_row = 0
            while True:
                req = GscQueryRequest(
                    site_url=site_url,
                    start_date=str(day),
                    end_date=str(day),
                    dimensions=dimensions,
                    row_limit=self.ROW_LIMIT,
                    start_row=start_row,
                    dimension_filter_groups=filters.get("dimensionFilterGroups") if filters else None,
                )
                data = self.client.search_analytics_query(req)
                raw_bundle["pages"].append(data)

                http_status = int(data.get("_http_status") or 0)
                run.response_status = http_status

                if http_status >= 400:
                    run.status = GscSyncRun.Status.FAILED
                    run.completed_at = timezone.now()
                    run.error = f"GSC HTTP {http_status}"
                    run.raw_json = raw_bundle
                    run.save(update_fields=["status", "completed_at", "response_status", "error", "raw_json"])
                    return SyncResult(run=run, served_from_cache=False)

                rows = data.get("rows") or []
                total_fetched += len(rows)

                up = self._upsert_rows(project=project, day=day, rows=rows, dimensions=dimensions)
                total_upserted += up

                if len(rows) < self.ROW_LIMIT:
                    break
                start_row += self.ROW_LIMIT

            run.status = GscSyncRun.Status.COMPLETED
            run.completed_at = timezone.now()
            run.rows_fetched = total_fetched
            run.rows_upserted = total_upserted
            run.raw_json = raw_bundle
            run.save(update_fields=["status", "completed_at", "response_status", "rows_fetched", "rows_upserted", "raw_json"])
            return SyncResult(run=run, served_from_cache=False)

        except Exception as e:
            run.status = GscSyncRun.Status.FAILED
            run.completed_at = timezone.now()
            run.error = str(e)
            run.raw_json = raw_bundle
            run.save(update_fields=["status", "completed_at", "error", "raw_json"])
            return SyncResult(run=run, served_from_cache=False)

    @transaction.atomic
    def _upsert_rows(self, *, project: Project, day: date, rows: list, dimensions: list[str]) -> int:
        objs: list[GscRow] = []
        for r in rows:
            keys = r.get("keys") or []
            key_map = {dim: (keys[idx] if idx < len(keys) else "") for idx, dim in enumerate(dimensions)}

            objs.append(
                GscRow(
                    project=project,
                    date=day,
                    query=str(key_map.get("query") or ""),
                    page=str(key_map.get("page") or ""),
                    country=str(key_map.get("country") or ""),
                    device=str(key_map.get("device") or ""),
                    clicks=r.get("clicks"),
                    impressions=r.get("impressions"),
                    ctr=r.get("ctr"),
                    position=r.get("position"),
                    raw_json=r,
                )
            )

        if not objs:
            return 0

        created = GscRow.objects.bulk_create(objs, ignore_conflicts=True)
        return len(created)
