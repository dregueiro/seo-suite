# geo/management/commands/seed_geo_country.py
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import pycountry

from geo.models import Country, Region, City


class Command(BaseCommand):
    help = "Seed regions (ISO subdivisions) and optionally cities for a single country."

    def add_arguments(self, parser):
        parser.add_argument("--country", type=str, required=True, help="Country code (alpha_2). Ex: US")
        parser.add_argument("--no-regions", action="store_true", help="Do not seed regions/subdivisions.")
        parser.add_argument("--cities", action="store_true", help="Seed cities (requires geonamescache).")
        parser.add_argument("--min-population", type=int, default=50000, help="Min population for cities (default 50000).")
        parser.add_argument("--max-cities", type=int, default=200, help="Max cities per country (default 200).")

    @transaction.atomic
    def handle(self, *args, **options):
        cc = options["country"].strip().upper()
        seed_regions = not options["no_regions"]
        seed_cities = bool(options["cities"])
        min_pop = int(options["min_population"])
        max_cities = int(options["max_cities"])

        try:
            country = Country.objects.get(code=cc)
        except Country.DoesNotExist:
            raise CommandError(f"Country {cc} not found. Run: python manage.py seed_geo")

        regions_created = 0
        cities_created = 0

        # 1) Regions (ISO 3166-2) via pycountry.subdivisions
        if seed_regions:
            for s in pycountry.subdivisions:
                if getattr(s, "country_code", None) != cc:
                    continue

                code = getattr(s, "code", None)   # e.g. "US-CA"
                name = getattr(s, "name", None)
                if not code or not name:
                    continue

                _, created = Region.objects.get_or_create(
                    country=country,
                    code=code,
                    defaults={"name": name},
                )
                if created:
                    regions_created += 1

        # 2) Cities (optional) via geonamescache
        if seed_cities:
            try:
                import geonamescache  # type: ignore
            except Exception:
                raise CommandError("To seed cities: pip install geonamescache")

            gc = geonamescache.GeonamesCache()
            all_cities = gc.get_cities()

            # preload regions map: "US-CA" -> Region
            region_map = {r.code: r for r in Region.objects.filter(country=country)}

            # fallback region if mapping fails
            fallback_region, _ = Region.objects.get_or_create(
                country=country,
                code="ALL",
                defaults={"name": "All / Unknown"},
            )

            items = []
            for _, c in all_cities.items():
                if (c.get("countrycode") or "").upper() != cc:
                    continue
                pop = int(c.get("population") or 0)
                if pop < min_pop:
                    continue
                items.append(c)

            items.sort(key=lambda x: int(x.get("population") or 0), reverse=True)
            items = items[:max_cities]

            for c in items:
                name = (c.get("name") or "").strip()
                if not name:
                    continue

                admin1 = (c.get("admin1code") or "").strip()  # e.g. "CA"
                region = fallback_region
                if admin1:
                    iso_code = f"{cc}-{admin1}"
                    region = region_map.get(iso_code, fallback_region)

                _, created = City.objects.get_or_create(
                    country=country,
                    region=region,
                    name=name,
                )
                if created:
                    cities_created += 1

        self.stdout.write(self.style.SUCCESS(f"Regions created: {regions_created}"))
        self.stdout.write(self.style.SUCCESS(f"Cities created: {cities_created}"))
