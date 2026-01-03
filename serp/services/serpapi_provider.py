import os
from urllib.parse import urlparse

from serpapi import GoogleSearch

from integrations.serp.types import SerpParsed, SerpRequest, SerpResultItem, SerpFeatureItem


class SerpApiProvider:
    """
    SerpAPI provider.

    - fetch_parsed(req): hace request real y retorna SerpParsed (contrato interno).
    - parse_raw(raw): parsea raw sin llamar a la API (para tests).
    - fetch(...): método legacy para compatibilidad (devuelve list[dict], raw).
    """

    def __init__(self):
        api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
        if not api_key or "pega_tu_api_key" in api_key:
            raise RuntimeError("SERPAPI_API_KEY is missing or placeholder. Put a real key in .env.")
        self.api_key = api_key
        self.google_domain = os.environ.get("SERPAPI_GOOGLE_DOMAIN", "google.com").strip() or "google.com"

    @staticmethod
    def _domain_from_url(url: str) -> str:
        try:
            netloc = (urlparse(url).netloc or "").lower()
            return netloc.replace("www.", "")
        except Exception:
            return ""

    @staticmethod
    def parse_raw(raw: dict) -> SerpParsed:
        organic = raw.get("organic_results", []) or []
        results: list[SerpResultItem] = []

        for idx, r in enumerate(organic, start=1):
            link = r.get("link", "") or ""
            results.append(
                SerpResultItem(
                    position=idx,
                    title=r.get("title", "") or "",
                    url=link,
                    domain=SerpApiProvider._domain_from_url(link),
                    snippet=r.get("snippet", "") or "",
                    displayed_url=r.get("displayed_link", "") or "",
                    raw=r if isinstance(r, dict) else {},
                )
            )

        features: list[SerpFeatureItem] = []
        # Opcional: mapear featured_snippet, local_pack, top_stories si lo necesitas luego.

        return SerpParsed(provider="serpapi", results=results, features=features, raw=raw)

    def fetch_parsed(self, req: SerpRequest) -> SerpParsed:
        params = {
            "engine": "google",
            "q": req.normalized_query(),
            "api_key": self.api_key,
            "google_domain": self.google_domain,
            "num": req.num_results,
            "device": req.device,  # "desktop" o "mobile"
            "hl": req.language_code,
            "gl": req.country_code,
        }

        # SerpAPI "location" es opcional
        if getattr(req, "location_name", ""):
            params["location"] = req.location_name

        data = GoogleSearch(params).get_dict() or {}

        meta = data.get("search_metadata", {}) or {}
        status = (meta.get("status") or "").lower()
        if status and status != "success":
            err = data.get("error") or f"SerpAPI status: {meta.get('status')}"
            raise RuntimeError(err)

        return self.parse_raw(data)

    # Método legacy, para no romper el pipeline actual
    def fetch(
        self,
        query: str,
        country_code: str = "us",
        language_code: str = "en",
        device: str = "desktop",
        num: int = 10,
        location: str = "",
    ):
        parsed = self.fetch_parsed(
            SerpRequest(
                query=query,
                country_code=country_code,
                language_code=language_code,
                device="mobile" if device == "mobile" else "desktop",
                num_results=num,
                location_name=location or "",
            )
        )

        results_dicts = [
            {
                "position": r.position,
                "title": r.title,
                "url": r.url,
                "domain": r.domain,
                "snippet": r.snippet,
                "raw": r.raw,
            }
            for r in parsed.results
        ]
        return results_dicts, parsed.raw
