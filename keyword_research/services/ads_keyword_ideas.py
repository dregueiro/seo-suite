import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.utils import timezone

from core.models import Run, RunArtifact
from keyword_research.models import KeywordMetric
from integrations.models import IntegrationStatus
from projects.models import Project


# --- Mapping mínimo y trazable (MVP) ---
# GeoTargetConstants (Google Ads) - expandimos después con catálogo/cache
GEO_TARGETS = {
    "US": "geoTargetConstants/2840",
    "AR": "geoTargetConstants/2032",
    "MX": "geoTargetConstants/2484",
    "ES": "geoTargetConstants/2724",
}

# Language constants (Google Ads)
LANGUAGES = {
    "en": "languageConstants/1000",
    "es": "languageConstants/1003",
}


def _normalize_cid(cid: str) -> str:
    return (cid or "").replace("-", "").strip()


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_run_artifact_json(*, run: Run, filename: str, payload: Any) -> RunArtifact:
    """
    Guarda JSON crudo como artifact trazable. Evita reventar ProviderResponse con payload gigante.
    """
    base_dir = Path(settings.BASE_DIR) / "artifacts" / str(run.id)
    _ensure_dir(base_dir)

    path = base_dir / filename
    content = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    path.write_bytes(content)

    import hashlib
    sha = hashlib.sha256(content).hexdigest()

    return RunArtifact.objects.create(
        run=run,
        name=filename,
        artifact_type=RunArtifact.ArtifactType.JSON,
        storage_path=str(path),
        sha256=sha,
        size_bytes=len(content),
    )


def _resolve_ads_mode(project: Project) -> Tuple[str, str]:
    """
    Devuelve (ads_mode, login_customer_id)
    - direct: login_customer_id=""
    - manager: login_customer_id=... (obligatorio)
    """
    st = IntegrationStatus.objects.filter(project=project, provider=IntegrationStatus.Provider.ADS).first()
    if not st:
        return ("direct", "")

    # backward compatible si aún no existen los campos
    ads_mode = getattr(st, "ads_mode", "direct") or "direct"
    login_cid = getattr(st, "login_customer_id", "") or ""
    login_cid = _normalize_cid(login_cid)

    if ads_mode == "manager" and not login_cid:
        # configuración inconsistente
        return ("manager", "")

    return (ads_mode, login_cid)


def _competition_to_level(comp_enum_name: str) -> str:
    """
    comp_enum_name viene de Google Ads como string tipo 'LOW', 'MEDIUM', 'HIGH', 'UNSPECIFIED'
    """
    v = (comp_enum_name or "").upper()
    if v in ("LOW", "MEDIUM", "HIGH"):
        return v
    return ""


def fetch_keyword_overview_close_variants(
    *,
    project: Project,
    run: Run,
    keyword: str,
    locale: str = "en_US",
    language: str = "en",
    geo: str = "US",
    page_size: int = 200,
) -> Dict[str, Any]:
    """
    Fetch REAL desde Google Ads KeywordPlanIdeaService.GenerateKeywordIdeas.
    Close variants: en la práctica Google devuelve ideas/variantes para el keyword seed.
    Guardamos:
    - ProviderResponse (muestra pequeña)
    - Artifact JSON completo
    - KeywordMetric (contrato canónico)
    """
    from google.ads.googleads.client import GoogleAdsClient

    ads_customer_id = _normalize_cid(project.ads_customer_id)
    if not ads_customer_id:
        raise ValueError("Project missing ads_customer_id")

    ads_mode, login_customer_id = _resolve_ads_mode(project)

    cfg = os.environ.get("GOOGLE_ADS_CONFIG_PATH") or str(settings.BASE_DIR / "google-ads.yaml")
    client = GoogleAdsClient.load_from_storage(path=cfg)

    if ads_mode == "manager":
        if not login_customer_id:
            raise ValueError("ads_mode=manager pero falta login_customer_id")
        client.login_customer_id = login_customer_id

    # --- request ---
    kp_service = client.get_service("KeywordPlanIdeaService")
    request = client.get_type("GenerateKeywordIdeasRequest")

    request.customer_id = ads_customer_id
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

    # language + geo
    lang_const = LANGUAGES.get(language, LANGUAGES["en"])
    request.language = lang_const

    geo_const = GEO_TARGETS.get(geo, GEO_TARGETS["US"])
    request.geo_target_constants.append(geo_const)

    # seed keyword
    request.keyword_seed.keywords.append(keyword)

    # paging (limit MVP)
    request.page_size = page_size

    # --- call ---
    resp = kp_service.generate_keyword_ideas(request=request)

    # parse response -> rows
    now = timezone.now()
    rows: List[Dict[str, Any]] = []
    created_metrics = 0

    for idea in resp:
        text = getattr(idea, "text", "") or ""
        m = getattr(idea, "keyword_idea_metrics", None)
        if not m or not text:
            continue

        avg = getattr(m, "avg_monthly_searches", None)
        comp = getattr(m, "competition", None)
        comp_name = comp.name if comp is not None else ""
        comp_level = _competition_to_level(comp_name)

        low_bid = getattr(m, "low_top_of_page_bid_micros", None)
        high_bid = getattr(m, "high_top_of_page_bid_micros", None)
        cpc_micros = None
        if low_bid and high_bid:
            cpc_micros = int((low_bid + high_bid) / 2)
        elif high_bid:
            cpc_micros = int(high_bid)
        elif low_bid:
            cpc_micros = int(low_bid)

        rows.append(
            {
                "keyword": text,
                "avg_monthly_searches": int(avg) if avg is not None else None,
                "cpc_micros": cpc_micros,
                "competition_level": comp_level,
                "locale": locale,
                "language": language,
                "geo": geo,
                "source": "ads",
                "source_confidence": 0.85,
            }
        )

    # Persist KeywordMetric (bulk)
    objs = []
    for r in rows:
        objs.append(
            KeywordMetric(
                project=project,
                run=run,
                keyword=r["keyword"],
                locale=r["locale"],
                language=r["language"],
                geo=r["geo"],
                avg_monthly_searches=r["avg_monthly_searches"],
                cpc_micros=r["cpc_micros"],
                competition_level=r["competition_level"],
                source=r["source"],
                source_confidence=r["source_confidence"],
                retrieved_at=now,
            )
        )

    KeywordMetric.objects.bulk_create(objs, ignore_conflicts=True)
    created_metrics = len(objs)

    # Artifact raw completo + muestra para ProviderResponse
    raw_payload = {
        "request": {
            "customer_id": ads_customer_id,
            "ads_mode": ads_mode,
            "login_customer_id": login_customer_id or None,
            "keyword": keyword,
            "language": lang_const,
            "geo_target_constants": [geo_const],
            "network": "GOOGLE_SEARCH",
            "page_size": page_size,
        },
        "results_count": len(rows),
        "items": rows,  # ya normalizado al contrato (más útil que proto bruto)
    }

    art = _write_run_artifact_json(run=run, filename=f"ads_keyword_overview_{keyword[:40]}.json", payload=raw_payload)

    return {
        "created_metrics": created_metrics,
        "rows_count": len(rows),
        "artifact_id": str(art.id),
        "ads_mode": ads_mode,
        "login_customer_id": login_customer_id or None,
        "config_path": cfg,
        "sample": rows[:10],
    }
