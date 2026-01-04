from django.core.management.base import BaseCommand, CommandError
from projects.models import Project
from keyword_research.services.google_ads_keywords import fetch_keyword_overview_ads


class Command(BaseCommand):
    help = "Keyword Overview via Google Ads Keyword Planner (crea Run + KeywordMetric)"

    def add_arguments(self, parser):
        parser.add_argument("--project-id", type=int, required=True)
        parser.add_argument("--keyword", type=str, required=True)
        parser.add_argument("--no-cache", action="store_true")

    def handle(self, *args, **options):
        project_id = options["project_id"]
        keyword = options["keyword"]
        use_cache = not options["no_cache"]

        project = Project.objects.filter(id=project_id).first()
        if not project:
            raise CommandError("Project no existe")

        run = fetch_keyword_overview_ads(project, keyword, use_cache=use_cache)

        self.stdout.write(f"run_id={run.id} status={run.status}")
        if run.status != "success":
            self.stdout.write(f"error={run.error_message}")
            return
        self.stdout.write(str(run.outputs))
