from django import forms
from .models import Project, Country, Language


class KeywordImportForm(forms.Form):
    project = forms.ModelChoiceField(queryset=Project.objects.all())

    country = forms.ModelChoiceField(queryset=Country.objects.all(), required=False)
    city = forms.CharField(required=False, max_length=120)

    language = forms.ModelChoiceField(queryset=Language.objects.all(), required=False)
    device = forms.CharField(required=False, max_length=10)

    keywords_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 12, "placeholder": "One keyword per line"}),
    )

    csv_file = forms.FileField(required=False)

    def clean(self):
        cleaned = super().clean()
        text = (cleaned.get("keywords_text") or "").strip()
        csv_file = cleaned.get("csv_file")
        if not text and not csv_file:
            raise forms.ValidationError("Paste keywords or upload a CSV file.")
        return cleaned
