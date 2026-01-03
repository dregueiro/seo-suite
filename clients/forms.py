# clients/forms.py
from django import forms
from django.urls import reverse

from .models import Client
from geo.models import Region, City


class ClientAdminForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # OJO: estos deben coincidir con get_urls() en admin.py
        self.fields["region"].widget.attrs["data-ajax-url"] = reverse("admin:clients_client_ajax_regions")
        self.fields["city"].widget.attrs["data-ajax-url"] = reverse("admin:clients_client_ajax_cities")

        self.fields["region"].queryset = Region.objects.none()
        self.fields["city"].queryset = City.objects.none()

        country_id = self.data.get("country") or getattr(self.instance, "country_id", None)
        region_id = self.data.get("region") or getattr(self.instance, "region_id", None)

        if country_id:
            self.fields["region"].queryset = Region.objects.filter(country_id=country_id).order_by("name")

        if region_id:
            self.fields["city"].queryset = City.objects.filter(region_id=region_id).order_by("name")
