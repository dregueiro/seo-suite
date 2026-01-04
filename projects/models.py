from django.db import models

# Create your models here.
from django.db import models
from clients.models import Client


class Project(models.Model):
    client = models.ForeignKey(Client, related_name="projects", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    # Identificadores (Blueprint)
    domain = models.CharField(max_length=255, help_text="Dominio principal, ej: example.com")

    gsc_property = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="GSC property URL, ej: sc-domain:example.com o https://example.com/",
    )
    ga4_property_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="GA4 property id (solo el número), ej: 123456789",
    )
    ads_customer_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Google Ads customer id, ej: 123-456-7890 (obligatorio para Keyword Research)",
    )

    # Locale defaults (para contracts y runs)
    country_code = models.CharField(max_length=2, default="ES", help_text="ISO2, ej: ES")
    language_code = models.CharField(max_length=5, default="es", help_text="ej: es, en")

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("client", "name")]

    def __str__(self) -> str:
        return f"{self.client.name} / {self.name}"
