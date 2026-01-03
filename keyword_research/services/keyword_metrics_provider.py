from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from integrations.dataforseo.client import DataForSEOClient


@dataclass
class KeywordMetricRow:
    keyword: str
    search_volume: Optional[int] = None
    competition: str = ""
    competition_index: Optional[int] = None
    cpc: Optional[float] = None
    low_top_of_page_bid: Optional[float] = None
    high_top_of_page_bid: Optional[float] = None
    monthly_searches: Optional[list] = None
    raw: Optional[dict] = None


class DataForSEOKeywordMetricsProvider:
    """
    DataForSEO Keywords Data -> Google Ads Search Volume (LIVE)
    Endpoint: /v3/keywords_data/google_ads/search_volume/live
    """

    def __init__(self) -> None:
        self.client = DataForSEOClient()

    def search_volume_live(
        self,
        *,
        keywords: List[str],
        location_code: int,
        language_code: str,
        include_adult_keywords: bool = False,
    ) -> Dict[str, Any]:
        clean = [k.strip().lower() for k in keywords if k and k.strip()]
        payload = [
            {
                "keywords": clean,
                "location_code": int(location_code),
                "language_code": (language_code or "en").strip().lower(),
                "include_adult_keywords": bool(include_adult_keywords),
            }
        ]
        raw = self.client.post("/keywords_data/google_ads/search_volume/live", payload)
        rows = self.parse_rows(raw)
        return {"rows": rows, "raw": raw}

    def parse_rows(self, raw: dict) -> List[KeywordMetricRow]:
        tasks = raw.get("tasks") or []
        if not tasks:
            return []

        t0 = tasks[0] or {}
        result = t0.get("result") or []
        if not isinstance(result, list):
            return []

        out: List[KeywordMetricRow] = []
        for it in result:
            kw = (it.get("keyword") or "").strip().lower()
            if not kw:
                continue
            out.append(
                KeywordMetricRow(
                    keyword=kw,
                    search_volume=it.get("search_volume"),
                    competition=(it.get("competition") or "") or "",
                    competition_index=it.get("competition_index"),
                    cpc=it.get("cpc"),
                    low_top_of_page_bid=it.get("low_top_of_page_bid"),
                    high_top_of_page_bid=it.get("high_top_of_page_bid"),
                    monthly_searches=it.get("monthly_searches"),
                    raw=it,
                )
            )
        return out
