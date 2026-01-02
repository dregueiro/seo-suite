# geo/services.py
from django.core.management import call_command
from geo.models import City


def ensure_country_cities_seeded(country_code: str) -> None:
    country_code = country_code.strip().upper()
    # Guard: si ya hay ciudades, no re-seed
    if City.objects.filter(country__code=country_code).exists():
        return
    call_command("seed_geo_country", "--country", country_code)
