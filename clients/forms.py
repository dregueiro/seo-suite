from django import forms

from .models import Client
from geo.models import Region, City  # asumiendo que existen en geo


class ClientAdminForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Defaults seguros: no romper admin si no hay país/región seleccionados aún
        self.fields["region"].queryset = Region.objects.all()
        self.fields["city"].queryset = City.objects.all()

        # Si viene POST/GET (cuando el usuario cambia selects), respeta eso
        country_id = self.data.get("country") or None
        region_id = self.data.get("region") or None

        # Si estamos editando un objeto existente y no hay data, usar la instancia
        if self.instance and self.instance.pk and not self.data:
            country_id = self.instance.country_id
            region_id = self.instance.region_id

        # Filtrado por country para region (sin perder el valor guardado)
        if country_id:
            qs = Region.objects.filter(country_id=country_id)
            # incluir la región actual aunque no calce (por seguridad)
            if self.instance and self.instance.region_id:
                qs = qs | Region.objects.filter(pk=self.instance.region_id)
            self.fields["region"].queryset = qs.distinct()

        # Filtrado por region para city (sin perder el valor guardado)
        if region_id:
            qs = City.objects.filter(region_id=region_id)
            if self.instance and self.instance.city_id:
                qs = qs | City.objects.filter(pk=self.instance.city_id)
            self.fields["city"].queryset = qs.distinct()
