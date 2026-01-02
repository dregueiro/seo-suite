from django.contrib import admin

from serp.models import SerpRun, SerpResult, SerpKeywordSnapshot, SerpFeature


@admin.register(SerpRun)
class SerpRunAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "provider", "status", "started_at", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("project__domain",)
    ordering = ("-created_at",)



@admin.register(SerpResult)
class SerpResultAdmin(admin.ModelAdmin):
    list_display = ("serp_run", "position", "domain", "url")
    search_fields = ("domain", "url", "title")
    ordering = ("serp_run_id", "position")


@admin.register(SerpKeywordSnapshot)
class SerpKeywordSnapshotAdmin(admin.ModelAdmin):
    list_display = ("serp_run", "keyword", "tracked_position", "top_url")
    search_fields = ("keyword__keyword", "top_url")
    ordering = ("-serp_run_id",)


@admin.register(SerpFeature)
class SerpFeatureAdmin(admin.ModelAdmin):
    list_display = ("serp_run", "feature_type", "created_at")
    search_fields = ("feature_type",)
    ordering = ("-created_at",)
