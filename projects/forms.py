from __future__ import annotations

from django import forms

from geo.models import Country, Language
from projects.models import Project
from geo.models import Region, City

class ProjectAdminForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["region"].queryset = Region.objects.all()
        self.fields["city"].queryset = City.objects.all()

        country_id = None
        region_id = None

        if self.is_bound:
            country_id = self.data.get("country") or None
            region_id = self.data.get("region") or None
        elif self.instance:
            country_id = getattr(self.instance, "country_id", None)
            region_id = getattr(self.instance, "region_id", None)

        if country_id:
            qs = Region.objects.filter(country_id=country_id)
            if self.instance and self.instance.region_id:
                qs = qs | Region.objects.filter(pk=self.instance.region_id)
            self.fields["region"].queryset = qs.distinct()

        if region_id:
            qs = City.objects.filter(region_id=region_id)
            if self.instance and self.instance.city_id:
                qs = qs | City.objects.filter(pk=self.instance.city_id)
            self.fields["city"].queryset = qs.distinct()


class KeywordImportForm(forms.Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    country = forms.ModelChoiceField(
        queryset=Country.objects.all().order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    city = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    language = forms.ModelChoiceField(
        queryset=Language.objects.all().order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    device = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "desktop / mobile"}),
    )

    keywords_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 12, "placeholder": "One keyword per line", "class": "form-control"}),
    )

    csv_file = forms.FileField(required=False)

    def clean(self):
        cleaned = super().clean()
        text = (cleaned.get("keywords_text") or "").strip()
        csv_file = cleaned.get("csv_file")
        if not text and not csv_file:
            raise forms.ValidationError("Paste keywords or upload a CSV file.")
        return cleaned

