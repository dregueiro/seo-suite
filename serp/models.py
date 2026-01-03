from __future__ import annotations

from django.db import models
from django.utils import timezone


class SerpRun(models.Model):
    """
    Un "run" agrupa la recolección de SERPs para un proyecto en un momento.
    """

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        ERROR = "error", "Error"
        SUBMITTED = "submitted", "Submitted"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="serp_runs")

    provider = models.CharField(max_length=30, default="serpapi")
    status = models.CharField(max_length=30, default=Status.CREATED)
    run_type = models.CharField(max_length=40, blank=True, default="rank_tracking")

    cache_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    cache_expires_at = models.DateTimeField(null=True, blank=True)

    response_status = models.PositiveIntegerField(default=0)
    cost_units = models.PositiveIntegerField(default=0)

    country = models.ForeignKey("geo.Country", on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey("geo.Language", on_delete=models.SET_NULL, null=True, blank=True)
    city = models.CharField(max_length=120, blank=True, default="")
    device = models.CharField(max_length=10, blank=True, default="")

    top_n = models.PositiveIntegerField(default=10)
    total_keywords = models.PositiveIntegerField(default=0)
    total_results = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    task_id = models.CharField(max_length=120, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["cache_key", "cache_expires_at"]),
            models.Index(fields=["provider", "status", "created_at"]),

        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SERP Run {self.id} | {self.project.name} | {self.provider} | {self.status}"

class SerpResult(models.Model):
    class ResultType(models.TextChoices):
        ORGANIC = "organic", "Organic"
        AD = "ad", "Ad"
        FEATURE = "feature", "Feature"

    serp_run = models.ForeignKey("serp.SerpRun", on_delete=models.CASCADE, related_name="results")
    keyword = models.ForeignKey("planner.Keyword", on_delete=models.CASCADE, related_name="serp_results")

    position = models.PositiveIntegerField()
    result_type = models.CharField(max_length=10, choices=ResultType.choices, default=ResultType.ORGANIC)

    title = models.CharField(max_length=512, blank=True, default="")
    url = models.URLField(max_length=600, blank=True, default="")
    domain = models.CharField(max_length=255, blank=True, default="")
    snippet = models.TextField(blank=True, default="")

    raw = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["serp_run", "keyword", "position", "result_type"],
                name="uniq_serpresult_position",
            ),
        ]
        indexes = [
            models.Index(fields=["serp_run", "keyword"]),
            models.Index(fields=["domain"]),
        ]
        ordering = ["keyword_id", "position"]

    def __str__(self) -> str:
        return f"{self.keyword.keyword} #{self.position} {self.domain}"

class SerpKeywordSnapshot(models.Model):
    serp_run = models.ForeignKey("serp.SerpRun", on_delete=models.CASCADE, related_name="snapshots")
    keyword = models.ForeignKey("planner.Keyword", on_delete=models.CASCADE, related_name="snapshots")

    tracked_domain = models.CharField(max_length=255)  # dominio del proyecto normalizado
    tracked_position = models.PositiveIntegerField(null=True, blank=True)  # la mejor posición de tu dominio o None

    top_domain = models.CharField(max_length=255, blank=True, default="")
    top_position = models.PositiveIntegerField(null=True, blank=True)  # mejor posición en general
    top_url = models.URLField(max_length=600, blank=True, default="")
    top3_domains = models.JSONField(default=list, blank=True)
    top3_urls = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["serp_run", "keyword"], name="uniq_snapshot_per_run_keyword"),
        ]
        indexes = [
            models.Index(fields=["serp_run", "keyword"]),
            models.Index(fields=["tracked_domain"]),
        ]
        ordering = ["keyword_id"]

    def __str__(self) -> str:
        return f"{self.keyword.keyword} | {self.tracked_domain} | {self.tracked_position}"


# -------------------------
# KEYWORD IDEAS (CACHE + LIMIT)
# -------------------------


class SerpFeature(models.Model):
    serp_run = models.ForeignKey("serp.SerpRun", on_delete=models.CASCADE, related_name="features")
    feature_type = models.CharField(max_length=50)
    payload_json = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["serp_run_id", "feature_type"]
        indexes = [
            models.Index(fields=["serp_run", "feature_type"]),
        ]

    def __str__(self):
        return f"{self.feature_type}"

