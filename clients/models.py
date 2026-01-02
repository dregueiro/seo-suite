from django.core.exceptions import ValidationError
from django.db import models

class Client(models.Model):
    name = models.CharField(max_length=255, unique=True)

    # Integrations
    gsc_website_link = models.URLField(max_length=2048, blank=True, default="")
    google_analytics_id = models.CharField(max_length=128, blank=True, default="")
    gads_login_customer_id = models.CharField(max_length=32, blank=True, default="")

    # Geo (todo viene de la app geo)
    country = models.ForeignKey("geo.Country", null=True, blank=True, on_delete=models.SET_NULL)
    region = models.ForeignKey("geo.Region", null=True, blank=True, on_delete=models.SET_NULL)
    city = models.ForeignKey("geo.City", null=True, blank=True, on_delete=models.SET_NULL)
    zipcode = models.CharField(max_length=20, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Singleton guard
        if not self.pk and Client.objects.exists():
            raise ValidationError("Solo puede existir un único Cliente en esta instancia.")

        # Consistencia geo
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
        return self.name
