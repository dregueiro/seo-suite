import json
import os
from typing import Any, Optional

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


def _upsert_status(project: Project, provider: str) -> IntegrationStatus:
    obj, _ = IntegrationStatus.objects.get_or_create(project=project, provider=provider)
    return obj


def _json_text(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def _normalize_cid(cid: str) -> str:
    return (cid or "").replace("-", "").strip()


def _resolve_login_customer_id(project: Optional[Project] = None) -> Optional[str]:
    """
    Soporta dos modos:
    - MCC por proyecto: project.ads_manager_customer_id (si existe)
    - MCC global por env: GOOGLE_ADS_LOGIN_CUSTOMER_ID
    Si no hay nada, modo directo (sin login-customer-id).
    """
    if project is not None and hasattr(project, "ads_manager_customer_id"):
        v = _normalize_cid(getattr(project, "ads_manager_customer_id", "") or "")
        if v:
            return v

    v = _normalize_cid(os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""))
    return v or None


# -------------------------
# GSC
# -------------------------
def test_gsc_access(project: Project, use_cache: bool = True) -> Run:
    provider = Run.Provider.GSC
    kind = "integrations.test_access.gsc"
    inputs = {"project_id": project.id, "gsc_property": project.gsc_property}

    status_obj = _upsert_status(project, IntegrationStatus.Provider.GSC)

    if not project.gsc_property:
        run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
        mark_failed(
            run,
            "Falta project.gsc_property",
            {"hint": "Configura gsc_property en el Project (sc-domain:... o https://...)"},
        )
        status_obj.mark(IntegrationStatus.Status.FAIL, "Falta gsc_property", run)
        status_obj.save()
        return run

    if use_cache:
        cached = get_cached_success_run(provider=provider, kind=kind, inputs=inputs)
        if cached:
            status_obj.mark(IntegrationStatus.Status.PASS, "OK (cache)", cached)
            status_obj.save()
            return cached

    run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
    mark_running(run)

    try:
        import google.auth
        from googleapiclient.discovery import build

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)

        resp = service.sites().get(siteUrl=project.gsc_property).execute()

        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="searchconsole.sites.get",
            http_status=200,
            request_body=_json_text({"siteUrl": project.gsc_property}),
            response_body=_json_text(resp),
        )
        mark_success(run, outputs={"ok": True, "site": project.gsc_property})
        status_obj.mark(IntegrationStatus.Status.PASS, "OK", run)
        status_obj.save()
        return run

    except ImportError as e:
        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="import",
            http_status=None,
            response_body=_json_text({"error": str(e)}),
        )
        mark_failed(run, "Dependencias no instaladas para GSC", {"hint": "pip install google-auth google-api-python-client"})
        status_obj.mark(IntegrationStatus.Status.FAIL, "Faltan deps (google-auth/google-api-python-client)", run)
        status_obj.save()
        return run

    except Exception as e:
        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="searchconsole.sites.get",
            http_status=None,
            response_body=_json_text({"error": str(e)}),
        )
        mark_failed(run, "Error testeando acceso GSC", {"error": str(e)})
        status_obj.mark(IntegrationStatus.Status.FAIL, f"Error: {e}", run)
        status_obj.save()
        return run


# -------------------------
# GA4
# -------------------------
def test_ga4_access(project: Project, use_cache: bool = True) -> Run:
    provider = Run.Provider.GA4
    kind = "integrations.test_access.ga4"
    inputs = {"project_id": project.id, "ga4_property_id": project.ga4_property_id}

    status_obj = _upsert_status(project, IntegrationStatus.Provider.GA4)

    if not project.ga4_property_id:
        run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
        mark_failed(
            run,
            "Falta project.ga4_property_id",
            {"hint": "Configura ga4_property_id (solo el número) en el Project"},
        )
        status_obj.mark(IntegrationStatus.Status.FAIL, "Falta ga4_property_id", run)
        status_obj.save()
        return run

    if use_cache:
        cached = get_cached_success_run(provider=provider, kind=kind, inputs=inputs)
        if cached:
            status_obj.mark(IntegrationStatus.Status.PASS, "OK (cache)", cached)
            status_obj.save()
            return cached

    run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
    mark_running(run)

    try:
        import google.auth
        from googleapiclient.discovery import build

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/analytics.readonly"])
        service = build("analyticsadmin", "v1beta", credentials=creds, cache_discovery=False)

        name = f"properties/{project.ga4_property_id}"
        resp = service.properties().get(name=name).execute()

        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="analyticsadmin.properties.get",
            http_status=200,
            request_body=_json_text({"name": name}),
            response_body=_json_text(resp),
        )
        mark_success(run, outputs={"ok": True, "property": name})
        status_obj.mark(IntegrationStatus.Status.PASS, "OK", run)
        status_obj.save()
        return run

    except ImportError as e:
        attach_provider_response(run=run, provider=provider, endpoint="import", http_status=None, response_body=_json_text({"error": str(e)}))
        mark_failed(run, "Dependencias no instaladas para GA4 Admin", {"hint": "pip install google-auth google-api-python-client"})
        status_obj.mark(IntegrationStatus.Status.FAIL, "Faltan deps (google-auth/google-api-python-client)", run)
        status_obj.save()
        return run

    except Exception as e:
        attach_provider_response(run=run, provider=provider, endpoint="analyticsadmin.properties.get", http_status=None, response_body=_json_text({"error": str(e)}))
        mark_failed(run, "Error testeando acceso GA4", {"error": str(e)})
        status_obj.mark(IntegrationStatus.Status.FAIL, f"Error: {e}", run)
        status_obj.save()
        return run


# -------------------------
# ADS
# -------------------------
def test_ads_access(project: Project, use_cache: bool = True) -> Run:
    provider = Run.Provider.ADS
    kind = "integrations.test_access.ads"

    customer_id = _normalize_cid(project.ads_customer_id)
    login_id = _resolve_login_customer_id(project)
    auth_mode = "mcc" if login_id else "direct"

    inputs = {
        "project_id": project.id,
        "ads_customer_id": project.ads_customer_id,
        "customer_id": customer_id,
        "auth_mode": auth_mode,
        "login_customer_id": login_id,
    }

    status_obj = _upsert_status(project, IntegrationStatus.Provider.ADS)

    if not project.ads_customer_id:
        run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
        mark_failed(
            run,
            "Falta project.ads_customer_id",
            {"gate": "Keyword Research bloqueado hasta tener Ads", "hint": "Configura ads_customer_id (123-456-7890) en el Project"},
        )
        status_obj.mark(IntegrationStatus.Status.FAIL, "Falta ads_customer_id (gate Keyword Research)", run)
        status_obj.save()
        return run

    if use_cache:
        cached = get_cached_success_run(provider=provider, kind=kind, inputs=inputs)
        if cached:
            status_obj.mark(IntegrationStatus.Status.PASS, "OK (cache)", cached)
            status_obj.save()
            return cached

    run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
    mark_running(run)

    try:
        from google.ads.googleads.client import GoogleAdsClient

        cfg = os.environ.get("GOOGLE_ADS_CONFIG_PATH") or str(settings.BASE_DIR / "google-ads.yaml")
        client = GoogleAdsClient.load_from_storage(path=cfg)

        # ✅ Aplica MCC si corresponde
        if login_id:
            client.login_customer_id = login_id

        # 1) Auth check (lista accesibles)
        customer_service = client.get_service("CustomerService")
        resp = customer_service.list_accessible_customers()
        accessible = [r.replace("customers/", "") for r in resp.resource_names]

        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="googleads.CustomerService.ListAccessibleCustomers",
            http_status=200,
            request_body=_json_text({"config_path": cfg, "auth_mode": auth_mode, "login_customer_id": login_id}),
            response_body=_json_text({"accessible_customers": accessible}),
        )

        if customer_id not in accessible:
            mark_failed(
                run,
                "ads_customer_id no está en list_accessible_customers()",
                {"ads_customer_id": project.ads_customer_id, "customer_id": customer_id, "accessible": accessible, "auth_mode": auth_mode, "login_customer_id": login_id},
            )
            status_obj.mark(IntegrationStatus.Status.FAIL, "No accesible (revisa permisos/config)", run)
            status_obj.save()
            return run

        # 2) Usability check real: GAQL mínima contra el customer del proyecto
        ga_service = client.get_service("GoogleAdsService")
        try:
            _ = ga_service.search(customer_id=customer_id, query="SELECT customer.id FROM customer LIMIT 1")
        except Exception as e:
            msg = str(e)

            # Mensajes más útiles / trazables
            if "manager's customer id must be set" in msg or "login-customer-id" in msg:
                mark_failed(
                    run,
                    "Falta login-customer-id para acceder a cliente vía MCC",
                    {"auth_mode": auth_mode, "login_customer_id": login_id, "customer_id": customer_id, "error": msg},
                )
                status_obj.mark(IntegrationStatus.Status.FAIL, "Falta login-customer-id (usa MCC)", run)
                status_obj.save()
                return run

            if "only approved for use with test accounts" in msg:
                mark_failed(
                    run,
                    "Developer token solo aprobado para cuentas de prueba (Test Account Access). Aplica a Basic/Standard.",
                    {"auth_mode": auth_mode, "login_customer_id": login_id, "customer_id": customer_id, "error": msg},
                )
                status_obj.mark(IntegrationStatus.Status.FAIL, "Developer token en Test Account Access", run)
                status_obj.save()
                return run

            # fallback genérico
            mark_failed(run, "Error GAQL mínimo (GoogleAdsService.search)", {"error": msg, "auth_mode": auth_mode})
            status_obj.mark(IntegrationStatus.Status.FAIL, f"Error GAQL: {e}", run)
            status_obj.save()
            return run

        mark_success(run, outputs={"ok": True, "ads_customer_id": project.ads_customer_id, "auth_mode": auth_mode, "login_customer_id": login_id})
        status_obj.mark(IntegrationStatus.Status.PASS, "OK", run)
        status_obj.save()
        return run

    except ImportError as e:
        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="import",
            http_status=None,
            response_body=_json_text({"error": str(e)}),
        )
        mark_failed(run, "Dependencias no instaladas para Google Ads", {"hint": "pip install google-ads"})
        status_obj.mark(IntegrationStatus.Status.FAIL, "Faltan deps (google-ads)", run)
        status_obj.save()
        return run

    except Exception as e:
        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="googleads",
            http_status=None,
            response_body=_json_text({"error": str(e)}),
        )
        mark_failed(run, "Error testeando acceso Google Ads", {"error": str(e)})
        status_obj.mark(IntegrationStatus.Status.FAIL, f"Error: {e}", run)
        status_obj.save()
        return run
