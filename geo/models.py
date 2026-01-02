from __future__ import annotations

from django.db import models


class Country(models.Model):
    code = models.CharField(max_length=2, unique=True)  # ISO-2
    name = models.CharField(max_length=120)
    dataforseo_location_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="DataForSEO location_code (numérico). Ej: 2840 = United States",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

class Language(models.Model):
    code = models.CharField(max_length=10, unique=True)  # en, es, pt-BR
    name = models.CharField(max_length=120)
    google_ads_language_id = models.IntegerField(null=True, blank=True, help_text="Google Ads language constant ID")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

