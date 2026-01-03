from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


phone_validator = RegexValidator(
    regex=r"^\+?[0-9\s().-]{7,20}$",
    message="Teléfono inválido. Usa solo números y caracteres + ( ) . - y espacios.",
)


class Client(models.Model):
    name = models.CharField(max_length=255, unique=True)

    # Contact
    contact_name = models.CharField(max_length=255, blank=True, default="")
    contact_email = models.EmailField(max_length=254, blank=True, default="")
    contact_phone = models.CharField(
        max_length=32,
        blank=True,
        default="",
        validators=[phone_validator],
    )


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
