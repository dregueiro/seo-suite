from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.conf import settings


@dataclass
class KeywordIdeaRow:
    keyword: str
    search_volume: int
    competition_index: Optional[int]
    low_top_of_page_bid: Optional[float]
    high_top_of_page_bid: Optional[float]
    cpc: Optional[float]
    raw: Optional[dict] = None


def _language_constant_id(language_code: str) -> int:
    # mapping mínimo (puedes ampliar)
    code = (language_code or "en").lower().strip()
    return {
        "en": 1000,
        "es": 1003,
        "pt": 1014,
        "fr": 1002,
        "de": 1001,
        "it": 1004,
    }.get(code, 1000)


class GoogleAdsKeywordPlannerProvider:
    """
    Google Ads Keyword Planner (GenerateKeywordIdeas).
    Usa credenciales en settings (env vars).
    """

    def __init__(self):
        self._client = None

    def is_configured(self) -> bool:
        return all(
            [
                getattr(settings, "GOOGLE_ADS_DEVELOPER_TOKEN", ""),
                getattr(settings, "GOOGLE_ADS_CLIENT_ID", ""),
                getattr(settings, "GOOGLE_ADS_CLIENT_SECRET", ""),
                getattr(settings, "GOOGLE_ADS_REFRESH_TOKEN", ""),
            ]
        )

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not self.is_configured():
            raise RuntimeError("Google Ads no configurado (faltan env vars).")

        from google.ads.googleads.client import GoogleAdsClient

        config = {
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
            **(
                {"login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID}
                if getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
                else {}
            ),
            "use_proto_plus": True,
        }
        self._client = GoogleAdsClient.load_from_dict(config)
        return self._client

    def generate_keyword_ideas(
        self,
        *,
        customer_id: str,
        seed_keyword: str,
        location_code: int,
        language_code: str,
        top_n: int = 15,
    ) -> Dict[str, Any]:
        client = self._get_client()

        service = client.get_service("KeywordPlanIdeaService")
        request = client.get_type("GenerateKeywordIdeasRequest")

        request.customer_id = str(customer_id).replace("-", "").strip()
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS

        lang_id = _language_constant_id(language_code)
        request.language = f"languageConstants/{lang_id}"

        # Geo target constants usan IDs numéricos
        request.geo_target_constants.append(f"geoTargetConstants/{int(location_code)}")

        request.keyword_seed.keywords.append(seed_keyword.strip())

        resp = service.generate_keyword_ideas(request=request)

        ideas: List[KeywordIdeaRow] = []
        for idea in resp:
            text = getattr(idea, "text", "") or ""
            metrics = getattr(idea, "keyword_idea_metrics", None)

            avg = 0
            comp = None
            low = None
            high = None

            if metrics:
                avg = int(getattr(metrics, "avg_monthly_searches", 0) or 0)

                comp_enum = getattr(metrics, "competition", None)
                if comp_enum is not None:
                    try:
                        comp = int(comp_enum)
                    except Exception:
                        comp = None

                low_m = getattr(metrics, "low_top_of_page_bid_micros", None)
                high_m = getattr(metrics, "high_top_of_page_bid_micros", None)

                def micros_to_unit(x):
                    try:
                        return float(x) / 1_000_000 if x is not None else None
                    except Exception:
                        return None

                low = micros_to_unit(low_m)
                high = micros_to_unit(high_m)

            ideas.append(
                KeywordIdeaRow(
                    keyword=text,
                    search_volume=avg,
                    competition_index=comp,
                    low_top_of_page_bid=low,
                    high_top_of_page_bid=high,
                    cpc=None,
                    raw=None,
                )
            )

        ideas.sort(key=lambda x: x.search_volume, reverse=True)
        ideas = ideas[: int(top_n)]

        return {
            "seed": seed_keyword.strip().lower(),
            "location_code": int(location_code),
            "language_code": (language_code or "en").strip().lower(),
            "ideas": [i.__dict__ for i in ideas],
            "raw": None,
        }
