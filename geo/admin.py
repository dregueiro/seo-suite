from django.contrib import admin

from geo.models import Country, Language,Region, City


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    search_fields = ("name", "code", "country__name")  # ajusta campos reales
    list_display = ("name", "country")

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    search_fields = ("name", "region__name", "country__name")  # ajusta campos reales
    list_display = ("name", "region", "country")

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
