from django.contrib import admin
from .models import Client, Project, Keyword, Country, Language,SerpRun, SerpResult


@admin.register(SerpRun)
class SerpRunAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "provider", "status", "top_n", "total_keywords", "total_results", "created_at")
    list_filter = ("provider", "status", "project")
    search_fields = ("project__name", "project__domain")
    ordering = ("-created_at",)


@admin.register(SerpResult)
class SerpResultAdmin(admin.ModelAdmin):
    list_display = ("serp_run", "keyword", "position", "result_type", "domain", "url")
    list_filter = ("result_type", "serp_run__project", "serp_run__provider")
    search_fields = ("keyword__keyword", "domain", "url", "title")
    ordering = ("-created_at",)

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "domain", "is_active", "country", "language", "device", "updated_at")
    list_filter = ("is_active", "country", "language", "device")
    search_fields = ("name", "domain", "client__name")
    autocomplete_fields = ("client",)



@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("keyword", "project", "status", "country", "city", "language", "device", "updated_at")
    list_filter = ("status", "country", "language", "device", "project")
    search_fields = ("keyword", "target_url", "project__name", "project__domain")
    autocomplete_fields = ("project",)
