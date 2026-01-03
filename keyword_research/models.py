from __future__ import annotations

from django.db import models
from django.utils import timezone


class KeywordIdeaRun(models.Model):
    class Provider(models.TextChoices):
        GOOGLE_ADS = "google_ads", "Google Ads"
        DATAFORSEO = "dataforseo", "DataForSEO"
        DATAFORSEO_LABS = "dataforseo_labs", "DataForSEO Labs"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="keyword_idea_runs")
    seed_keyword = models.CharField(max_length=255)
    location_code = models.IntegerField(default=2840)
    language_code = models.CharField(max_length=16, default="en")

    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.DATAFORSEO)
    from_cache = models.BooleanField(default=False)

    # rate-limit: True solo cuando este seed+loc+lang se crea por primera vez (nueva búsqueda)
    is_new_seed = models.BooleanField(default=False)

    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    raw = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["project", "seed_keyword", "location_code", "language_code"]),
            models.Index(fields=["project", "is_new_seed", "created_at"]),
        ]

    def __str__(self):
        return f"KeywordIdeaRun({self.project_id}, {self.seed_keyword}, {self.provider})"

class KeywordIdea(models.Model):
    run = models.ForeignKey("planner.KeywordIdeaRun", on_delete=models.CASCADE, related_name="ideas")

    keyword = models.CharField(max_length=255)
    search_volume = models.IntegerField(default=0)
    competition_index = models.IntegerField(null=True, blank=True)
    low_top_of_page_bid = models.FloatField(null=True, blank=True)
    high_top_of_page_bid = models.FloatField(null=True, blank=True)
    cpc = models.FloatField(null=True, blank=True)
    raw = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "keyword"], name="uniq_keyword_idea_per_run"),
        ]
        indexes = [
            models.Index(fields=["keyword"]),
            models.Index(fields=["search_volume"]),
        ]

    def __str__(self):
        return f"{self.keyword} ({self.search_volume})"


