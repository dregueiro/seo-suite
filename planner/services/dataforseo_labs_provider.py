from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from integrations.dataforseo.client import DataForSEOClient


@dataclass
class KeywordIdeaRow:
    keyword: str
    search_volume: int = 0
    competition_index: Optional[int] = None
    low_top_of_page_bid: Optional[float] = None
    high_top_of_page_bid: Optional[float] = None
    cpc: Optional[float] = None
    raw: Optional[dict] = None


class DataForSEOLabsProvider:
    """
    DataForSEO Labs Google Keyword Suggestions (live).
    POST /v3/dataforseo_labs/google/keyword_suggestions/live
    Respuesta: tasks[0].result[0].items[].keyword_info.search_volume, cpc, competition, etc.
    """

    def __init__(self):
        self.client = DataForSEOClient()

    def keyword_suggestions_live(
        self,
        *,
        seed_keyword: str,
        location_code: int,
        language_code: str,
        limit: int = 15,
    ) -> Dict[str, Any]:
        seed = (seed_keyword or "").strip()
        if not seed:
            return {"ideas": [], "raw": {"error": "seed_keyword vacío"}}

        # Nota: Labs usa "keyword" (string), no "keywords" array.
        payload = [
            {
                "keyword": seed,
                "location_code": int(location_code),
                "language_code": (language_code or "en").strip().lower(),
                "limit": int(limit),
                "include_seed_keyword": False,
                "include_serp_info": False,
                "ignore_synonyms": True,
                # ordenar por search_volume desc (si el API lo soporta, lo hace)
                "order_by": ["keyword_info.search_volume,desc"],
            }
        ]

        resp = self.client.post("/dataforseo_labs/google/keyword_suggestions/live", payload)
        ideas = self._parse(resp, limit=limit)

        return {"ideas": [i.__dict__ for i in ideas], "raw": resp}

    def _parse(self, resp: dict, *, limit: int) -> List[KeywordIdeaRow]:
        tasks = resp.get("tasks") or []
        if not tasks:
            return []

        t0 = tasks[0] or {}
        result0 = (t0.get("result") or [None])[0] or {}
        items = result0.get("items") or []

        out: List[KeywordIdeaRow] = []

        for it in items:
            kw = (it.get("keyword") or "").strip().lower()
            if not kw:
                continue

            ki = it.get("keyword_info") or {}

            sv = ki.get("search_volume")
            try:
                sv_i = int(sv) if sv is not None else 0
            except Exception:
                sv_i = 0

            # competition en Labs suele venir como float 0..1, lo convertimos a 0..100
            comp = ki.get("competition")
            comp_i = None
            try:
                if comp is not None:
                    comp_i = int(round(float(comp) * 100))
            except Exception:
                comp_i = None

            def f(x):
                try:
                    return float(x) if x is not None else None
                except Exception:
                    return None

            out.append(
                KeywordIdeaRow(
                    keyword=kw,
                    search_volume=sv_i,
                    competition_index=comp_i,
                    low_top_of_page_bid=f(ki.get("low_top_of_page_bid")),
                    high_top_of_page_bid=f(ki.get("high_top_of_page_bid")),
                    cpc=f(ki.get("cpc")),
                    raw=it,
                )
            )

        out.sort(key=lambda x: x.search_volume, reverse=True)
        return out[: int(limit)]
