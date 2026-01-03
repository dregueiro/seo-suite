from django.core.management.base import BaseCommand

from projects.models import Project
from keyword_research.models import Keyword
from keyword_research.services.keyword_metrics_service import KeywordMetricsService


class Command(BaseCommand):
    help = "Enrich metrics for tracked keywords using DataForSEO Search Volume."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True)
        parser.add_argument("--priority_min", type=int, default=3)
        parser.add_argument("--location_code", type=int, default=2840)
        parser.add_argument("--language_code", type=str, default="en")

    def handle(self, *args, **opts):
        project = Project.objects.get(id=opts["project"])
        qs = Keyword.objects.filter(project=project, status="active", priority__gte=opts["priority_min"])

        svc = KeywordMetricsService()
        run = svc.enrich(
            project=project,
            keywords=qs,
            location_code=opts["location_code"],
            language_code=opts["language_code"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"KeywordMetricsRun id={run.id} status={run.status} keywords={run.keywords_count} cost_units={run.cost_units}"
            )
        )
