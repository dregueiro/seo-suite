from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from keyword_research.models import (
    Keyword,
    KeywordIdea,
    KeywordIdeaRun,
    KeywordMetricsRun,
    KeywordMetricSnapshot,
    KeywordSeed,
)
from keyword_research.services.admin_actions import (
    add_ideas_to_tracked_keywords,
    enrich_metrics_for_keywords,
    run_ideas_for_seeds,
)


@admin.register(KeywordSeed)
class KeywordSeedAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "kind", "seed", "country", "language", "device", "created_at")
    list_filter = ("kind", "device", "country", "language")
    search_fields = ("seed", "project__domain")
    actions = ["action_run_ideas", "action_run_ideas_with_fallback"]

    @admin.action(description=_("Run keyword ideas for selected seeds"))
    def action_run_ideas(self, request, queryset):
        res = run_ideas_for_seeds(seeds=queryset, top_n=15, use_fallback=False)
        self.message_user(
            request,
            f"Ideas runs: created={res.created}, cached={res.cached}, failed={res.failed}",
        )

    @admin.action(description="Run keyword ideas (fallback ON) for selected seeds")
    def action_run_ideas_with_fallback(self, request, queryset):
        res = run_ideas_for_seeds(seeds=queryset, top_n=15, use_fallback=True)
        self.message_user(request, f"Ideas runs (fallback): created={res.created}, cached={res.cached}, failed={res.failed}")

@admin.register(KeywordIdeaRun)
class KeywordIdeaRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "seed_keyword",
        "provider",
        "status",
        "from_cache",
        "requested_at",
        "completed_at",
        "cost_units",
    )
    list_filter = ("provider", "status", "from_cache")
    search_fields = ("seed_keyword", "project__domain")
    readonly_fields = ("raw",)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.seed_ref_id:
            ro.append("seed_keyword")
        return ro


@admin.register(KeywordIdea)
class KeywordIdeaAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "keyword", "search_volume", "cpc", "competition_index")
    list_filter = ("search_volume",)
    search_fields = ("keyword", "run__project__domain")
    actions = ["action_add_to_tracked_keywords"]

    @admin.action(description=_("Add selected ideas to tracked Keywords"))
    def action_add_to_tracked_keywords(self, request, queryset):
        res = add_ideas_to_tracked_keywords(ideas=queryset.select_related("run", "run__project"))
        self.message_user(request, f"Tracked keywords: created={res.created}, skipped={res.skipped}")


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "keyword", "status", "priority", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("keyword", "project__domain")
    ordering = ("-created_at",)
    actions = ["action_enrich_metrics"]

    @admin.action(description=_("Enrich metrics for selected Keywords"))
    def action_enrich_metrics(self, request, queryset):
        res = enrich_metrics_for_keywords(keywords=queryset.select_related("project", "country", "language"), priority_min=1)
        self.message_user(request, f"Metrics: created={res.created}, cached={res.cached}, failed={res.failed}")


@admin.register(KeywordMetricsRun)
class KeywordMetricsRunAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "provider", "status", "keywords_count", "requested_at", "completed_at", "cost_units")
    list_filter = ("provider", "status")
    search_fields = ("project__domain",)
    readonly_fields = ("raw_json",)


@admin.register(KeywordMetricSnapshot)
class KeywordMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "keyword", "search_volume", "competition", "competition_index", "cpc")
    list_filter = ("competition",)
    search_fields = ("keyword__keyword", "keyword__project__domain")

