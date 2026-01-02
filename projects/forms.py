from __future__ import annotations

from django import forms

from geo.models import Country, Language
from projects.models import Project


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

