from urllib.parse import quote

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html

from clients.models import Client
from geo.models import Region, City
from projects.forms import ProjectAdminForm
from projects.models import Project, ProjectCompetitor
from projects.models import Project, ProjectCompetitor, GscRow, GscSyncRun

@admin.register(GscSyncRun)
class GscSyncRunAdmin(admin.ModelAdmin):
    list_display = ("id","project","date","status","rows_fetched","rows_upserted","requested_at","completed_at","response_status")
    list_filter = ("status","date")
    search_fields = ("project__domain","site_url")
    readonly_fields = ("raw_json","error","cache_key","cache_expires_at")

@admin.register(GscRow)
class GscRowAdmin(admin.ModelAdmin):
    list_display = ("id","project","date","query","country","device","clicks","impressions","ctr","position")
    list_filter = ("date","country","device")
    search_fields = ("query","page","project__domain")
    readonly_fields = ("raw_json",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    form = ProjectAdminForm
    list_display = (
        "id",
        "client",
        "name",
        "domain",
        "country",
        "region",
        "city",
        "is_active",
        "gsc_open_link",
        "updated_at",
    )
    list_filter = ("is_active", "device", "country", "language")
    search_fields = ("name", "domain", "client__name")

    readonly_fields = ("gsc_open_link", "created_at", "updated_at")
    fieldsets = (
        ("Base", {"fields": ("client", "name", "domain", "is_active")}),
        ("Geo", {"fields": ("country", "region", "city", "language", "device")}),
        ("Integrations", {
            "fields": (
                ("gsc_website_link", "gsc_open_link"),  # <-- misma fila
                "google_analytics_id",
                "gads_login_customer_id",
            )
        }),
        ("Notes", {"fields": ("notes",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    class Media:
        js = ("projects/admin/project_location.js",)

    @admin.display(description="Abrir en GSC")
    def gsc_open_link(self, obj: Project):
        if not obj.gsc_website_link:
            return "-"

        site = obj.gsc_website_link.strip()

        # Si guardas domain property: sc-domain:epicmoments.media
        # lo convertimos para UI: https://epicmoments.media/
        if site.startswith("sc-domain:"):
            domain = site.split("sc-domain:", 1)[1].strip()
            site_for_ui = f"https://{domain}/"
        else:
            site_for_ui = site

        deeplink = "https://search.google.com/search-console?resource_id=" + quote(site_for_ui, safe="")
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Abrir</a>',
            deeplink,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("ajax/regions/", self.admin_site.admin_view(self.ajax_regions), name="projects_project_ajax_regions"),
            path("ajax/cities/", self.admin_site.admin_view(self.ajax_cities), name="projects_project_ajax_cities"),
            path(
                "ajax/client-defaults/",
                self.admin_site.admin_view(self.ajax_client_defaults),
                name="projects_project_ajax_client_defaults",
            ),
        ]
        return custom + urls

    def ajax_regions(self, request):
        country_id = "".join(ch for ch in str(request.GET.get("country", "")) if ch.isdigit())
        if not country_id:
            return JsonResponse([], safe=False)
        qs = Region.objects.filter(country_id=country_id).order_by("name").values("id", "name")
        return JsonResponse(list(qs), safe=False)

    def ajax_cities(self, request):
        region_id = "".join(ch for ch in str(request.GET.get("region", "")) if ch.isdigit())
        if not region_id:
            return JsonResponse([], safe=False)
        qs = City.objects.filter(region_id=region_id).order_by("name").values("id", "name")
        return JsonResponse(list(qs), safe=False)

    def ajax_client_defaults(self, request):
        client_id = "".join(ch for ch in str(request.GET.get("client", "")) if ch.isdigit())
        if not client_id:
            return JsonResponse({"country": None, "region": None, "city": None}, safe=False)

        c = Client.objects.filter(pk=client_id).only("country_id", "region_id", "city_id").first()
        if not c:
            return JsonResponse({"country": None, "region": None, "city": None}, safe=False)

        return JsonResponse({"country": c.country_id, "region": c.region_id, "city": c.city_id}, safe=False)


@admin.register(ProjectCompetitor)
class ProjectCompetitorAdmin(admin.ModelAdmin):
    list_display = ("project", "competitor_domain")
    search_fields = ("competitor_domain",)
    ordering = ("project_id",)
