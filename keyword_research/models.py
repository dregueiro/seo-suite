from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class Keyword(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="keywords")
    keyword = models.CharField(max_length=255)
    country = models.ForeignKey("geo.Country", on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey("geo.Language", on_delete=models.SET_NULL, null=True, blank=True)

    city = models.CharField(max_length=120, blank=True, default="")
    device = models.CharField(max_length=10, blank=True, default="")

    target_url = models.URLField(blank=True, default="")
    intent = models.CharField(max_length=40, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    priority = models.PositiveSmallIntegerField(default=3, help_text="1=low cost, 5=high priority")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Clave: conservar la tabla existente creada por projects.Keyword
        db_table = "projects_keyword"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "keyword", "country", "city", "language", "device"],
                name="uniq_keyword_scope",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="pk_kw_pr_stat_idx"),
            models.Index(fields=["keyword"], name="pk_kw_kw_idx"),
        ]

        ordering = ["project__client__name", "project__name", "keyword"]

    def __str__(self) -> str:
        return f"{self.project.name} | {self.keyword}"

class KeywordSeed(models.Model):
    class Kind(models.TextChoices):
        KEYWORD = "keyword", "Keyword"
        DOMAIN = "domain", "Domain"
        URL = "url", "URL"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="keyword_seeds")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.KEYWORD)
    seed = models.CharField(max_length=255)

    country = models.ForeignKey("geo.Country", on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey("geo.Language", on_delete=models.SET_NULL, null=True, blank=True)
    city = models.CharField(max_length=120, blank=True, default="")
    device = models.CharField(max_length=10, blank=True, default="desktop")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "kind", "seed", "country", "city", "language", "device"],
                name="uniq_keyword_seed_scope",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["seed"]),
        ]

    def __str__(self):
        return f"{self.project_id} | {self.kind} | {self.seed}"

class KeywordIdeaRun(models.Model):
    class Provider(models.TextChoices):
        GOOGLE_ADS = "google_ads", "Google Ads"
        DATAFORSEO = "dataforseo", "DataForSEO"
        DATAFORSEO_LABS = "dataforseo_labs", "DataForSEO Labs"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="keyword_idea_runs")
     # NUEVO: referencia al seed persistido (opcional)
    seed_ref = models.ForeignKey("planner.KeywordSeed", on_delete=models.SET_NULL, null=True, blank=True)

    seed_keyword = models.CharField(max_length=255)
    location_code = models.IntegerField(default=2840)
    language_code = models.CharField(max_length=16, default="en")

    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.DATAFORSEO)

    # NUEVO: lifecycle estándar
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
# NUEVO: timestamps estándar (no rompen tu created_at)
    requested_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    # NUEVO: trazabilidad HTTP/costo
    response_status = models.PositiveIntegerField(default=0)
    cost_units = models.PositiveIntegerField(default=0)

    # NUEVO: caching real 24h
    cache_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    cache_expires_at = models.DateTimeField(null=True, blank=True)

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
            models.Index(fields=["cache_key", "cache_expires_at"]),
            models.Index(fields=["status", "requested_at"]),
        ]
    def clean(self):
        super().clean()
        if self.seed_ref:
            ref_seed = (self.seed_ref.seed or "").strip().lower()
            run_seed = (self.seed_keyword or "").strip().lower()

            if not run_seed:
                # se completa en save(), pero clean no debería mutar; ok dejar pasar
                return

            if ref_seed and run_seed and ref_seed != run_seed:
                raise ValidationError({"seed_keyword": "seed_keyword debe coincidir con seed_ref.seed."})

    def save(self, *args, **kwargs):
        if self.seed_ref and not (self.seed_keyword or "").strip():
            self.seed_keyword = (self.seed_ref.seed or "").strip().lower()
        super().save(*args, **kwargs)

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

class KeywordMetricsRun(models.Model):
    class Provider(models.TextChoices):
        DATAFORSEO = "dataforseo", "DataForSEO"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="keyword_metrics_runs")

    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.DATAFORSEO)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)

    location_code = models.IntegerField(default=2840)
    language_code = models.CharField(max_length=16, default="en")

    requested_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    response_status = models.PositiveIntegerField(default=0)
    cost_units = models.PositiveIntegerField(default=0)

    cache_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    cache_expires_at = models.DateTimeField(null=True, blank=True)

    keywords_count = models.PositiveIntegerField(default=0)
    raw_json = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "requested_at"]),
            models.Index(fields=["status", "requested_at"]),
            models.Index(fields=["cache_key", "cache_expires_at"]),
        ]

    def __str__(self):
        return f"KeywordMetricsRun({self.project_id}, {self.provider}, {self.status})"


class KeywordMetricSnapshot(models.Model):
    run = models.ForeignKey("planner.KeywordMetricsRun", on_delete=models.CASCADE, related_name="snapshots")
    keyword = models.ForeignKey("planner.Keyword", on_delete=models.CASCADE, related_name="metric_snapshots")

    search_volume = models.IntegerField(null=True, blank=True)
    competition = models.CharField(max_length=10, blank=True, default="")
    competition_index = models.IntegerField(null=True, blank=True)
    cpc = models.FloatField(null=True, blank=True)
    low_top_of_page_bid = models.FloatField(null=True, blank=True)
    high_top_of_page_bid = models.FloatField(null=True, blank=True)

    monthly_searches = models.JSONField(null=True, blank=True)
    raw = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "keyword"], name="uniq_kw_metric_snapshot_per_run"),
        ]
        indexes = [
            models.Index(fields=["keyword"]),
            models.Index(fields=["search_volume"]),
        ]

    def __str__(self):
        return f"{self.keyword.keyword} | {self.search_volume}"

