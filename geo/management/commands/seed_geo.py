from django.core.management.base import BaseCommand
import pycountry

from geo.models import Country, Language


class Command(BaseCommand):
    help = "Seed Country and Language tables using ISO data (pycountry)."

    def handle(self, *args, **options):
        c_created = 0
        l_created = 0

        # Countries
        for c in pycountry.countries:
            code = getattr(c, "alpha_2", None)
            name = getattr(c, "name", None)
            if not code or not name:
                continue
            obj, created = Country.objects.get_or_create(code=code, defaults={"name": name})
            if created:
                c_created += 1

        # Languages
        for l in pycountry.languages:
            code = getattr(l, "alpha_2", None)
            name = getattr(l, "name", None)
            if not code or not name:
                continue
            obj, created = Language.objects.get_or_create(code=code, defaults={"name": name})
            if created:
                l_created += 1

        self.stdout.write(self.style.SUCCESS(f"Countries created: {c_created}"))
        self.stdout.write(self.style.SUCCESS(f"Languages created: {l_created}"))
