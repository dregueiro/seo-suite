import json
from typing import Any, Dict, Tuple

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


def test_gsc_access(project: Project, use_cache: bool = True) -> Run:
    provider = Run.Provider.GSC
    kind = "integrations.test_access.gsc"
    inputs = {"project_id": project.id, "gsc_property": project.gsc_property}

    status_obj = _upsert_status(project, IntegrationStatus.Provider.GSC)

    if not project.gsc_property:
        run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
        mark_failed(run, "Falta project.gsc_property", {"hint": "Configura gsc_property en el Project (sc-domain:...)"} )
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

        # Llamada mínima de verificación: Sites.get
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


def test_ga4_access(project: Project, use_cache: bool = True) -> Run:
    provider = Run.Provider.GA4
    kind = "integrations.test_access.ga4"
    inputs = {"project_id": project.id, "ga4_property_id": project.ga4_property_id}

    status_obj = _upsert_status(project, IntegrationStatus.Provider.GA4)

    if not project.ga4_property_id:
        run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
        mark_failed(run, "Falta project.ga4_property_id", {"hint": "Configura ga4_property_id (solo el número) en el Project"})
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
        attach_provider_response(run=run, provider=provider, endpoint="import", response_body=_json_text({"error": str(e)}))
        mark_failed(run, "Dependencias no instaladas para GA4 Admin", {"hint": "pip install google-auth google-api-python-client"})
        status_obj.mark(IntegrationStatus.Status.FAIL, "Faltan deps (google-auth/google-api-python-client)", run)
        status_obj.save()
        return run

    except Exception as e:
        attach_provider_response(run=run, provider=provider, endpoint="analyticsadmin.properties.get", response_body=_json_text({"error": str(e)}))
        mark_failed(run, "Error testeando acceso GA4", {"error": str(e)})
        status_obj.mark(IntegrationStatus.Status.FAIL, f"Error: {e}", run)
        status_obj.save()
        return run


def test_ads_access(project: Project, use_cache: bool = True) -> Run:
    provider = Run.Provider.ADS
    kind = "integrations.test_access.ads"
    inputs = {"project_id": project.id, "ads_customer_id": project.ads_customer_id}

    status_obj = _upsert_status(project, IntegrationStatus.Provider.ADS)

    if not project.ads_customer_id:
        run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
        mark_failed(run, "Falta project.ads_customer_id", {"gate": "Keyword Research bloqueado hasta tener Ads", "hint": "Configura ads_customer_id (123-456-7890) en el Project"})
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

        # google-ads.yaml en raíz por defecto, o override por env
        import os
        from django.conf import settings

        cfg = os.environ.get("GOOGLE_ADS_CONFIG_PATH", str(settings.BASE_DIR / "google-ads.yaml"))
        client = GoogleAdsClient.load_from_storage(path=cfg)

        customer_service = client.get_service("CustomerService")
        resp = customer_service.list_accessible_customers()

        # Opcional: validar que el customer_id del proyecto está accesible
        accessible = [r.replace("customers/", "") for r in resp.resource_names]
        normalized = project.ads_customer_id.replace("-", "")
        ok = normalized in accessible

        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="googleads.CustomerService.ListAccessibleCustomers",
            http_status=200,
            request_body=_json_text({"config_path": cfg}),
            response_body=_json_text({"accessible_customers": accessible}),
        )

        if not ok:
            mark_failed(run, "ads_customer_id no está en list_accessible_customers()", {"ads_customer_id": project.ads_customer_id, "accessible": accessible})
            status_obj.mark(IntegrationStatus.Status.FAIL, "No accesible (revisa permisos/config)", run)
            status_obj.save()
            return run

        mark_success(run, outputs={"ok": True, "ads_customer_id": project.ads_customer_id})
        status_obj.mark(IntegrationStatus.Status.PASS, "OK", run)
        status_obj.save()
        return run

    except ImportError as e:
        attach_provider_response(run=run, provider=provider, endpoint="import", response_body=_json_text({"error": str(e)}))
        mark_failed(run, "Dependencias no instaladas para Google Ads", {"hint": "pip install google-ads"})
        status_obj.mark(IntegrationStatus.Status.FAIL, "Faltan deps (google-ads)", run)
        status_obj.save()
        return run

    except Exception as e:
        attach_provider_response(run=run, provider=provider, endpoint="googleads.CustomerService.ListAccessibleCustomers", response_body=_json_text({"error": str(e)}))
        mark_failed(run, "Error testeando acceso Google Ads", {"error": str(e)})
        status_obj.mark(IntegrationStatus.Status.FAIL, f"Error: {e}", run)
        status_obj.save()
        return run
