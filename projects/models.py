from __future__ import annotations

from django.db import models


class Client(models.Model):
    name = models.CharField(max_length=120, unique=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

class Project(models.Model):
    class Device(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        MOBILE = "mobile", "Mobile"

    client = models.ForeignKey("projects.Client", on_delete=models.PROTECT, related_name="projects")
    name = models.CharField(max_length=160)
    domain = models.CharField(max_length=255)  # ejemplo: voicesenglish.com
    is_active = models.BooleanField(default=True)

    city = models.CharField(max_length=120, blank=True, default="")
    country = models.ForeignKey("geo.Country", on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey("geo.Language", on_delete=models.SET_NULL, null=True, blank=True)
    device = models.CharField(max_length=10, choices=Device.choices, default=Device.DESKTOP)

    # ✅ para Google Ads Keyword Planner (NO es secreto, solo el ID)
    google_ads_customer_id = models.CharField(max_length=32, blank=True, default="")

    gsc_site_url = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Search Console property. Ejemplo: sc-domain:example.com o https://example.com/",
    )

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["client", "domain"], name="uniq_client_domain"),
        ]
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["is_active"]),
        ]
        ordering = ["client__name", "name"]

    def __str__(self) -> str:
        return f"{self.client.name} | {self.name}"

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
    intent = models.CharField(max_length=40, blank=True, default="")  # informativa, comercial, etc
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    priority = models.PositiveSmallIntegerField(default=3, help_text="1=low cost, 5=high priority")

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "keyword", "country", "city", "language", "device"],
                name="uniq_keyword_scope",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["keyword"]),
        ]
        ordering = ["project__client__name", "project__name", "keyword"]

    def __str__(self) -> str:
        return f"{self.project.name} | {self.keyword}"


# -------------------------
# SERP MODELS
# -------------------------


class ProjectCompetitor(models.Model):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="competitors")
    competitor_domain = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "competitor_domain"], name="uniq_competitor_per_project"),
        ]
        indexes = [
            models.Index(fields=["project", "competitor_domain"]),
        ]

    def __str__(self):
        return f"{self.competitor_domain}"

