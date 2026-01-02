from django.contrib import admin

from projects.models import Project, Keyword, ProjectCompetitor
from clients.models import Client


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "domain", "is_active", "created_at")
    list_filter = ("is_active", "device", "country", "language")
    search_fields = ("name", "domain")
    ordering = ("-created_at",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.primary_country_id:
            ensure_country_cities_seeded(obj.primary_country.code)

@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "keyword", "status", "priority", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("keyword",)
    ordering = ("-created_at",)


@admin.register(ProjectCompetitor)
class ProjectCompetitorAdmin(admin.ModelAdmin):
    list_display = ("project", "competitor_domain")
    search_fields = ("competitor_domain",)
    ordering = ("project_id",)
