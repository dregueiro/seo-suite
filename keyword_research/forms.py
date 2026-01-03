from __future__ import annotations

from django import forms

from geo.models import Country, Language


class KeywordPlannerForm(forms.Form):
    seed_keyword = forms.CharField(
        max_length=255,
        required=True,
        label="Seed keyword",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "ej: seo tools"}),
    )

    country = forms.ModelChoiceField(
        queryset=Country.objects.all().order_by("name"),
        required=True,
        label="País",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    language = forms.ModelChoiceField(
        queryset=Language.objects.all().order_by("name"),
        required=True,
        label="Idioma",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    top_n = forms.IntegerField(
        required=False,
        initial=15,
        min_value=10,
        max_value=15,
        label="Top ideas (10-15)",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    use_fallback = forms.BooleanField(
        required=False,
        initial=False,
        label="Usar fallback (DataForSEO Labs, costo extra)",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_country(self):
        country = self.cleaned_data["country"]
        if not getattr(country, "dataforseo_location_code", None):
            raise forms.ValidationError("Este país no tiene DataForSEO location_code configurado.")
        return country

