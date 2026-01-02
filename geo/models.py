from __future__ import annotations

from django.db import models


class Region(models.Model):
    country = models.ForeignKey("geo.Country", on_delete=models.CASCADE, related_name="regions")
    code = models.CharField(max_length=20, blank=True, default="")
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["country", "code"], name="uniq_region_country_code"),
        ]
        ordering = ["country__code", "name"]

    def __str__(self):
        return f"{self.name} - {self.country.code}"


class City(models.Model):
    country = models.ForeignKey("geo.Country", on_delete=models.CASCADE, related_name="cities")
    region = models.ForeignKey("geo.Region", on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["country", "region", "name"], name="uniq_city_country_region_name"),
        ]
        ordering = ["country__code", "region__name", "name"]

    def __str__(self):
        return f"{self.name}, {self.region.name} ({self.country.code})"

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

