import base64
import json
import requests
from django.conf import settings


class DataForSEOClient:
    def __init__(self):
        base = getattr(settings, "DATAFORSEO_BASE_URL", "https://api.dataforseo.com/v3")
        self.base_url = base.rstrip("/")

        login = getattr(settings, "DATAFORSEO_LOGIN", "")
        password = getattr(settings, "DATAFORSEO_PASSWORD", "")
        token = base64.b64encode(f"{login}:{password}".encode("utf-8")).decode("utf-8")
        self.auth_header = f"Basic {token}"

    def _headers(self):
        return {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
        }

    def post(self, path: str, payload):
        url = f"{self.base_url}/{path.lstrip('/')}"
        r = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=60)
        r.raise_for_status()
        return r.json()

    def get(self, path: str):
        url = f"{self.base_url}/{path.lstrip('/')}"
        r = requests.get(url, headers=self._headers(), timeout=60)
        r.raise_for_status()
        return r.json()
