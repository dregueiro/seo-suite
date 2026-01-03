# clients/admin.py
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from .models import Client
from .forms import ClientAdminForm
from geo.models import Region, City


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    form = ClientAdminForm

    class Media:
        js = ("clients/admin/client_chained_geo.js",)

    def get_urls(self):
        urls = super().get_urls()
        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        custom = [
            path(
                "ajax/regions/",
                self.admin_site.admin_view(self.ajax_regions),
                name=f"{app_label}_{model_name}_ajax_regions",
            ),
            path(
                "ajax/cities/",
                self.admin_site.admin_view(self.ajax_cities),
                name=f"{app_label}_{model_name}_ajax_cities",
            ),
        ]
        return custom + urls

    def ajax_regions(self, request):
        raw = request.GET.get("country", "")
        country_id = "".join(ch for ch in str(raw) if ch.isdigit())
        if not country_id:
            return JsonResponse([], safe=False)

        qs = Region.objects.filter(country_id=country_id).order_by("name").values("id", "name")
        return JsonResponse(list(qs), safe=False)

    def ajax_cities(self, request):
        raw = request.GET.get("region", "")
        region_id = "".join(ch for ch in str(raw) if ch.isdigit())
        if not region_id:
            return JsonResponse([], safe=False)

        qs = City.objects.filter(region_id=region_id).order_by("name").values("id", "name")
        return JsonResponse(list(qs), safe=False)
