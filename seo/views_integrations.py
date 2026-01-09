# seo/views_integrations.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from projects.models import Project
from integrations.services.test_access import test_gsc_access, test_ga4_access, test_ads_access


@login_required
def test_access(request, project_id: int, provider: str):
    if request.method != "POST":
        return redirect("seo:project_setup", project_id=project_id)

    project = get_object_or_404(Project, id=project_id)
    provider = (provider or "").lower().strip()

    try:
        if provider == "gsc":
            run = test_gsc_access(project, use_cache=True)
        elif provider == "ga4":
            run = test_ga4_access(project, use_cache=True)
        elif provider == "ads":
            run = test_ads_access(project, use_cache=True)
        else:
            messages.error(request, f"Provider inválido: {provider}")
            return redirect("seo:project_setup", project_id=project_id)

        # Mensaje + link al admin del run (trazabilidad)
        run_admin_url = f"/admin/core/run/{run.id}/change/"
        messages.success(request, f"Test access {provider.upper()} ejecutado. Run: {run.id} (ver en admin)")
        # guardo el link para el template si querés mostrarlo
        request.session["last_run_admin_url"] = run_admin_url

    except Exception as e:
        messages.error(request, f"Falló test access {provider.upper()}: {e}")
        return redirect("seo:project_setup", project_id=project_id)

    # Volver al setup (para ver PASS/FAIL en cards)
    return redirect("seo:project_setup", project_id=project_id)
