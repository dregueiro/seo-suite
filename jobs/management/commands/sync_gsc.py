from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from projects.models import Project
from projects.services.gsc_sync import GscSyncService


class Command(BaseCommand):
    help = "Sync Google Search Console performance rows for a project (daily)."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID")
        parser.add_argument("--start", type=str, required=True, help="Start date YYYY-MM-DD (inclusive)")
        parser.add_argument("--end", type=str, required=True, help="End date YYYY-MM-DD (inclusive)")

    def handle(self, *args, **opts):
        project_id = int(opts["project"])
        start = opts["start"]
        end = opts["end"]

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project not found: {project_id}")

        svc = GscSyncService()
        results = svc.sync_project(project=project, start_date=start, end_date=end)

        cached = sum(1 for r in results if r.served_from_cache)
        completed = sum(1 for r in results if r.run.status == "completed")
        failed = sum(1 for r in results if r.run.status == "failed")
        total_rows = sum(int(r.run.rows_upserted or 0) for r in results)

        self.stdout.write(
            self.style.SUCCESS(
                f"sync_gsc: project={project_id} days={len(results)} completed={completed} cached={cached} failed={failed} rows_upserted={total_rows}"
            )
        )
