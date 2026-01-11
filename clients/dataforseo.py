import json
import requests
from dataclasses import dataclass
from django.conf import settings


@dataclass
class DataForSEOResponse:
    http_status: int
    payload: dict


class DataForSEOClient:
    def __init__(self):
        self.base_url = (getattr(settings, "DATAFORSEO_BASE_URL", "https://api.dataforseo.com/v3") or "").rstrip("/")
        self.login = getattr(settings, "DATAFORSEO_LOGIN", "") or ""
        self.password = getattr(settings, "DATAFORSEO_PASSWORD", "") or ""

    def is_configured(self) -> bool:
        return bool(self.login and self.password and self.base_url)

    def _url(self, path: str) -> str:
        path = "/" + (path or "").lstrip("/")

        # evita .../v3/v3/...
        if self.base_url.endswith("/v3") and path.startswith("/v3/"):
            path = path[3:]

        return f"{self.base_url}{path}"

    def post(self, path: str, body) -> DataForSEOResponse:
        if not self.is_configured():
            raise RuntimeError("DataForSEO no está configurado (DATAFORSEO_LOGIN/PASSWORD).")

        url = self._url(path)
        r = requests.post(url, json=body, auth=(self.login, self.password), timeout=60)

        try:
            payload = r.json()
        except Exception:
            payload = {"_raw": r.text}

        return DataForSEOResponse(http_status=r.status_code, payload=payload)
