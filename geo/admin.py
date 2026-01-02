from django.contrib import admin

from geo.models import Country, Language


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "dataforseo_location_code")
    search_fields = ("code", "name")
    ordering = ("name",)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "google_ads_language_id")
    search_fields = ("code", "name")
    ordering = ("name",)
