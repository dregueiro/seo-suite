from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class Project(models.Model):
    class Device(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        MOBILE = "mobile", "Mobile"

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="projects",
    )

    name = models.CharField(max_length=160, verbose_name="Nombre del projecto")
    domain = models.CharField(max_length=255, help_text="Ejemplo: voicesenglish.com")
    is_active = models.BooleanField(default=True)

    country = models.ForeignKey("geo.Country", on_delete=models.SET_NULL, null=True, blank=True)
    region = models.ForeignKey("geo.Region", on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey("geo.City", on_delete=models.SET_NULL, null=True, blank=True)

    language = models.ForeignKey("geo.Language", on_delete=models.SET_NULL, null=True, blank=True)
    device = models.CharField(max_length=10, choices=Device.choices, default=Device.DESKTOP)

    # Integrations (mismos nombres que estaban en Client)
    gsc_website_link = models.URLField(max_length=2048, blank=True, default="", verbose_name="Gsc website link")
    google_analytics_id = models.CharField(max_length=128, blank=True, default="", verbose_name="Google analytics id")
    gads_login_customer_id = models.CharField(
        max_length=32,
        blank=True,
        default="",
        verbose_name="Gads login customer id",
        help_text="Google Ads login customer id (sin guiones). Ej: 1234567890",
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

    def clean(self):
        if self.region and self.country and self.region.country_id != self.country_id:
            raise ValidationError({"region": "La región no pertenece al país seleccionado."})

        if self.city:
            if self.region and self.city.region_id != self.region_id:
                raise ValidationError({"city": "La ciudad no pertenece a la región seleccionada."})
            if self.country and self.city.country_id != self.country_id:
                raise ValidationError({"city": "La ciudad no pertenece al país seleccionado."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

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
    intent = models.CharField(max_length=40, blank=True, default="")
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
