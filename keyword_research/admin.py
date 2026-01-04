from django.contrib import admin

# Register your models here.
from django.contrib import admin
from keyword_research.models import KeywordMetric


@admin.register(KeywordMetric)
class KeywordMetricAdmin(admin.ModelAdmin):
    list_display = ("keyword", "project", "locale", "avg_monthly_searches", "cpc_micros", "competition_level", "source", "retrieved_at", "run")
    list_filter = ("source", "locale", "competition_level")
    search_fields = ("keyword", "project__name", "project__domain", "run__id")
