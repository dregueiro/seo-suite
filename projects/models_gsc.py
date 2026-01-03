from __future__ import annotations

from django.db import models
from django.utils import timezone


class GscSyncRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="gsc_sync_runs")
    site_url = models.URLField(max_length=2048)
    date = models.DateField()

    dimensions_json = models.JSONField(default=list, blank=True)
    filters_json = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    response_status = models.PositiveIntegerField(default=0)
    cost_units = models.PositiveIntegerField(default=0)

    cache_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    cache_expires_at = models.DateTimeField(null=True, blank=True)

    rows_fetched = models.PositiveIntegerField(default=0)
    rows_upserted = models.PositiveIntegerField(default=0)

    raw_json = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["project", "date"]),
            models.Index(fields=["status", "requested_at"]),
            models.Index(fields=["cache_key", "cache_expires_at"]),
        ]
        ordering = ["-requested_at"]


class GscRow(models.Model):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="gsc_rows")

    date = models.DateField()
    query = models.TextField(blank=True, default="")
    page = models.URLField(max_length=2048, blank=True, default="")
    country = models.CharField(max_length=8, blank=True, default="")
    device = models.CharField(max_length=20, blank=True, default="")

    clicks = models.FloatField(null=True, blank=True)
    impressions = models.FloatField(null=True, blank=True)
    ctr = models.FloatField(null=True, blank=True)
    position = models.FloatField(null=True, blank=True)

    raw_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "date", "query", "page", "country", "device"],
                name="uniq_gscrow_project_date_dims",
            )
        ]
        indexes = [
            models.Index(fields=["project", "date"]),
            models.Index(fields=["project", "query"]),
            models.Index(fields=["project", "page"]),
        ]
        ordering = ["-date"]
