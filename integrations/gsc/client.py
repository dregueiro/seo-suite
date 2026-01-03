from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import requests
from django.conf import settings


GSC_API_BASE = "https://searchconsole.googleapis.com/webmasters/v3"


class GscConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class GscQueryRequest:
    site_url: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    dimensions: Sequence[str]
    row_limit: int = 25000
    start_row: int = 0
    dimension_filter_groups: Optional[list] = None


class GscClient:
    """
    Auth options (priority):
    - settings.GSC_ACCESS_TOKEN (manual / short-lived)
    - settings.GSC_SERVICE_ACCOUNT_FILE (requires google-auth)
    """

    def __init__(self) -> None:
        self._access_token = getattr(settings, "GSC_ACCESS_TOKEN", "") or ""
        self._service_account_file = getattr(settings, "GSC_SERVICE_ACCOUNT_FILE", "") or ""

        if not self._access_token and not self._service_account_file:
            raise GscConfigError(
                "GSC is not configured. Set GSC_ACCESS_TOKEN or GSC_SERVICE_ACCOUNT_FILE in .env/settings."
            )

    def _bearer_token(self) -> str:
        if self._access_token:
            return self._access_token.strip()

        path = self._service_account_file
        if not path:
            raise GscConfigError("Missing GSC_ACCESS_TOKEN and GSC_SERVICE_ACCOUNT_FILE.")
        if not os.path.exists(path):
            raise GscConfigError(f"GSC_SERVICE_ACCOUNT_FILE not found: {path}")

        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request as GoogleRequest
        except Exception as e:
            raise GscConfigError(
                "google-auth is required for service account auth. Add 'google-auth' to requirements.txt."
            ) from e

        scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
        creds.refresh(GoogleRequest())
        if not creds.token:
            raise GscConfigError("Failed to obtain access token from service account credentials.")
        return str(creds.token)

    def search_analytics_query(self, req: GscQueryRequest) -> Dict[str, Any]:
        site_url = req.site_url.strip()
        if not site_url:
            raise ValueError("site_url is required")

        url = f"{GSC_API_BASE}/sites/{requests.utils.quote(site_url, safe='')}/searchAnalytics/query"

        payload: Dict[str, Any] = {
            "startDate": req.start_date,
            "endDate": req.end_date,
            "dimensions": list(req.dimensions),
            "rowLimit": int(req.row_limit),
            "startRow": int(req.start_row),
        }
        if req.dimension_filter_groups:
            payload["dimensionFilterGroups"] = req.dimension_filter_groups

        headers = {
            "Authorization": f"Bearer {self._bearer_token()}",
            "Content-Type": "application/json",
        }

        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        try:
            data = r.json() if r.content else {}
        except Exception:
            data = {"raw_text": (r.text or "")[:5000]}
        data["_http_status"] = r.status_code
        return data
