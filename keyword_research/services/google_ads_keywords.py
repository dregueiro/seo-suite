import json
from typing import Any, Dict, Optional

from django.conf import settings

from core.models import Run
from core.services.runs import (
    RunSpec,
    attach_provider_response,
    create_run,
    get_cached_success_run,
    mark_failed,
    mark_running,
    mark_success,
)
from integrations.models import IntegrationStatus
from projects.models import Project
from keyword_research.models import KeywordMetric


def _json_text(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def _ensure_ads_ready(project: Project) -> Optional[str]:
    """
    Gate: Ads debe estar PASS para permitir keyword research.
    Devuelve mensaje de error si bloquea, None si OK.
    """
    if not project.ads_customer_id:
        return "Falta project.ads_customer_id (gate Keyword Research)."

    st = IntegrationStatus.objects.filter(project=project, provider=IntegrationStatus.Provider.ADS).first()
    if not st or st.status != IntegrationStatus.Status.PASS:
        return "Ads no está PASS en Integrations (gate Keyword Research). Ejecuta Test access: Ads."
    return None


def _load_ads_client():
    from google.ads.googleads.client import GoogleAdsClient

    import os
    cfg = os.environ.get("GOOGLE_ADS_CONFIG_PATH", str(settings.BASE_DIR / "google-ads.yaml"))
    return GoogleAdsClient.load_from_storage(path=cfg), cfg


def _gaql_one(googleads_service, customer_id: str, query: str) -> Optional[Any]:
    resp = googleads_service.search(customer_id=customer_id, query=query)
    for row in resp:
        return row
    return None


def _resolve_language_resource_name(client, customer_id: str, language_code: str) -> str:
    """
    Resuelve language_constant por code (sin hardcodear IDs).
    """
    googleads_service = client.get_service("GoogleAdsService")
    q = f"""
        SELECT language_constant.resource_name, language_constant.code
        FROM language_constant
        WHERE language_constant.code = '{language_code}'
        LIMIT 1
    """
    row = _gaql_one(googleads_service, customer_id, q)
    if not row:
        raise RuntimeError(f"No se pudo resolver language_constant para code='{language_code}'")
    return row.language_constant.resource_name


def _resolve_geo_country_resource_name(client, customer_id: str, country_code: str) -> str:
    """
    Resuelve geo_target_constant del país por ISO2 (sin hardcodear IDs).
    """
    googleads_service = client.get_service("GoogleAdsService")
    q = f"""
        SELECT geo_target_constant.resource_name, geo_target_constant.country_code, geo_target_constant.target_type
        FROM geo_target_constant
        WHERE geo_target_constant.country_code = '{country_code}'
          AND geo_target_constant.target_type = 'Country'
        LIMIT 1
    """
    row = _gaql_one(googleads_service, customer_id, q)
    if not row:
        raise RuntimeError(f"No se pudo resolver geo_target_constant para country_code='{country_code}'")
    return row.geo_target_constant.resource_name


def fetch_keyword_overview_ads(project: Project, keyword: str, use_cache: bool = True) -> Run:
    provider = Run.Provider.ADS
    kind = "keyword_research.ads.keyword_overview"
    inputs = {
        "project_id": project.id,
        "ads_customer_id": project.ads_customer_id,
        "keyword": keyword,
        "country_code": project.country_code,
        "language_code": project.language_code,
    }

    gate_error = _ensure_ads_ready(project)
    if gate_error:
        run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
        mark_failed(run, gate_error, {"gate": "ads_required"})
        return run

    if use_cache:
        cached = get_cached_success_run(provider=provider, kind=kind, inputs=inputs)
        if cached:
            return cached

    run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
    mark_running(run)

    try:
        client, cfg_path = _load_ads_client()
        customer_id = project.ads_customer_id.replace("-", "")

        language_rn = _resolve_language_resource_name(client, customer_id, project.language_code)
        geo_rn = _resolve_geo_country_resource_name(client, customer_id, project.country_code)

        kp_service = client.get_service("KeywordPlanIdeaService")

        req = client.get_type("GenerateKeywordHistoricalMetricsRequest")
        req.customer_id = customer_id
        req.keywords.append(keyword)
        req.language = language_rn
        req.geo_target_constants.append(geo_rn)
        req.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

        resp = kp_service.generate_keyword_historical_metrics(request=req)

        # Guardar raw request/response
        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="googleads.KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics",
            http_status=200,
            request_body=_json_text(
                {
                    "config_path": cfg_path,
                    "customer_id": customer_id,
                    "keywords": [keyword],
                    "language": language_rn,
                    "geo_target_constants": [geo_rn],
                    "network": "GOOGLE_SEARCH",
                }
            ),
            response_body=_json_text(resp),
        )

        created = 0
        for r in resp.results:
            m = r.keyword_metrics
            # CPC: usamos low_top_of_page_bid_micros como señal simple (barata y estable)
            km = KeywordMetric.objects.create(
                project=project,
                run=run,
                keyword=r.text,
                locale=f"{project.country_code}-{project.language_code}",
                language=project.language_code,
                geo=geo_rn,
                avg_monthly_searches=getattr(m, "avg_monthly_searches", None),
                cpc_micros=getattr(m, "low_top_of_page_bid_micros", None),
                competition_level=str(getattr(m, "competition", "")),
                source="ads",
                source_confidence=0.95,
            )
            created += 1

        mark_success(run, outputs={"ok": True, "created_metrics": created, "keyword": keyword}, cost_micros=0)
        return run

    except Exception as e:
        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="googleads.KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics",
            http_status=None,
            response_body=_json_text({"error": str(e)}),
        )
        mark_failed(run, "Error fetch_keyword_overview_ads", {"error": str(e)})
        return run
