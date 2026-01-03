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


class DataForSEOKeywordPlannerProvider:
    """
    DataForSEO Keywords Data -> Google Ads -> Keywords For Keywords (live)

    OJO: Las sugerencias vienen en tasks[0].result (lista de objetos),
    NO en result[0].items. :contentReference[oaicite:3]{index=3}
    """

    def __init__(self):
        self.client = DataForSEOClient()

    def keywords_for_keywords_live(
        self,
        *,
        seed_keyword: str,
        location_code: int,
        language_code: str,
        top_n: int = 15,
        sort_by: str = "search_volume",
    ) -> Dict[str, Any]:
        seed = (seed_keyword or "").strip()
        if not seed:
            return {"ideas": [], "raw": {"error": "seed_keyword vacío"}}

        payload = [
            {
                "keywords": [seed],
                "location_code": int(location_code),
                "language_code": (language_code or "en").strip().lower(),
                "sort_by": sort_by,  # search_volume / relevance etc :contentReference[oaicite:4]{index=4}
            }
        ]

        resp = self.client.post("/keywords_data/google_ads/keywords_for_keywords/live", payload)
        ideas = self._parse_keywords_for_keywords(resp, seed=seed, top_n=top_n)

        return {"ideas": [i.__dict__ for i in ideas], "raw": resp}

    def _parse_keywords_for_keywords(self, resp: dict, *, seed: str, top_n: int) -> List[KeywordIdeaRow]:
        tasks = resp.get("tasks") or []
        if not tasks:
            return []

        t0 = tasks[0] or {}
        result = t0.get("result") or []  # <- LISTA de keywords sugeridas :contentReference[oaicite:5]{index=5}
        if not isinstance(result, list):
            return []

        out: List[KeywordIdeaRow] = []

        for row in result:
            if not isinstance(row, dict):
                continue

            kw = (row.get("keyword") or "").strip().lower()
            if not kw:
                continue

            # Excluir el seed exacto (el usuario quiere "similares", no el mismo)
            if kw == seed.strip().lower():
                continue

            sv = row.get("search_volume")
            try:
                sv_i = int(sv) if sv is not None else 0
            except Exception:
                sv_i = 0

            comp_idx = row.get("competition_index")
            try:
                comp_i = int(comp_idx) if comp_idx is not None else None
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
                    low_top_of_page_bid=f(row.get("low_top_of_page_bid")),
                    high_top_of_page_bid=f(row.get("high_top_of_page_bid")),
                    cpc=f(row.get("cpc")),
                    raw=row,
                )
            )

        out.sort(key=lambda x: x.search_volume, reverse=True)
        return out[: int(top_n)]
