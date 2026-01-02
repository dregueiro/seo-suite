import os
from urllib.parse import urlparse

from serpapi import GoogleSearch

api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
if not api_key or "pega_tu_api_key" in api_key:
    raise RuntimeError("SERPAPI_API_KEY missing or placeholder. Put a real key in .env.")

class SerpApiProvider:
    def __init__(self):
        api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("SERPAPI_API_KEY is missing in environment (.env).")
        self.api_key = api_key
        self.google_domain = os.environ.get("SERPAPI_GOOGLE_DOMAIN", "google.com").strip() or "google.com"

    @staticmethod
    def _domain_from_url(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def fetch(self, *, q: str, location: str | None, gl: str | None, hl: str | None, device: str, num: int):
        params = {
            "engine": "google",
            "q": q,
            "api_key": self.api_key,
            "google_domain": self.google_domain,
            "device": device,   # desktop, mobile, tablet :contentReference[oaicite:3]{index=3}
            "num": num,
        }

        if location:
            params["location"] = location
        if gl:
            params["gl"] = gl
        if hl:
            params["hl"] = hl

        data = GoogleSearch(params).get_dict()

        meta = data.get("search_metadata", {}) or {}
        status = (meta.get("status") or "").lower()
        if status and status != "success":
            err = data.get("error") or f"SerpAPI status: {meta.get('status')}"
            raise RuntimeError(err)

        organic = data.get("organic_results", []) or []
        results = []

        for idx, r in enumerate(organic[:num], start=1):
            link = r.get("link", "") or ""
            results.append(
                {
                    "position": idx,
                    "title": r.get("title", "") or "",
                    "url": link,
                    "domain": self._domain_from_url(link),
                    "snippet": r.get("snippet", "") or "",
                    "raw": r,
                }
            )


        return results, data
