from django.contrib import admin

from keyword_research.models import KeywordIdeaRun, KeywordIdea


@admin.register(KeywordIdeaRun)
class KeywordIdeaRunAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "seed_keyword", "provider", "created_at")
    list_filter = ("provider",)
    search_fields = ("seed_keyword", "project__domain")
    ordering = ("-created_at",)


@admin.register(KeywordIdea)
class KeywordIdeaAdmin(admin.ModelAdmin):
    list_display = ("run", "keyword", "search_volume", "cpc")
    search_fields = ("keyword",)
    ordering = ("-search_volume",)
