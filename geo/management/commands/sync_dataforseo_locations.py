from django.core.management.base import BaseCommand
from geo.models import Country
from integrations.dataforseo.client import DataForSEOClient


class Command(BaseCommand):
    help = "Sync DataForSEO location_code for countries (Keyword Data locations)."

    def handle(self, *args, **opts):
        client = DataForSEOClient()

        updated = 0
        skipped = 0

        for c in Country.objects.all().order_by("name"):
            # si ya tiene code, no tocar (ahorro / control manual)
            if c.dataforseo_location_code:
                skipped += 1
                continue

            # Docs: GET /v3/keywords_data/google/locations/$country :contentReference[oaicite:2]{index=2}
            # Nota: el $country suele ser ISO2 en minúsculas en la doc.
            country_code = (c.code or "").lower().strip()
            if not country_code:
                continue

            try:
                resp = client.get(f"/keywords_data/google/locations/{country_code}")
                tasks = resp.get("tasks") or []
                result = (tasks[0].get("result") if tasks else None) or []
                # buscamos una fila tipo "Country" que coincida con el país
                chosen = None
                for row in result:
                    if (row.get("location_type") or "").lower() == "country":
                        chosen = row
                        break

                if chosen and chosen.get("location_code"):
                    c.dataforseo_location_code = int(chosen["location_code"])
                    c.save(update_fields=["dataforseo_location_code"])
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f"{c.code} -> {c.dataforseo_location_code}"))
                else:
                    self.stdout.write(self.style.WARNING(f"{c.code}: no country-level location_code encontrado"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"{c.code}: error {e}"))

        self.stdout.write(self.style.SUCCESS(f"Done. updated={updated}, skipped={skipped}"))
