from __future__ import annotations

import inspect

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Project, SerpRun
from core.services.rank_tracking import build_snapshots_for_run
from core.services.dataforseo_provider import DataForSEOProvider
from core.services.serpapi_provider import SerpAPIProvider


def call_compatible(fn, **kwargs):
    """
    Llama fn pasando SOLO los kwargs que fn realmente acepta.
    Evita errores tipo: got an unexpected keyword argument 'project'
    """
    sig = inspect.signature(fn)
    accepted = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in accepted and v is not None}
    return fn(**filtered)


class Command(BaseCommand):
    help = "Run SERP fetch for a project (mock/serpapi/dataforseo)."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True)
        parser.add_argument(
            "--provider",
            type=str,
            default="serpapi",
            choices=["mock", "serpapi", "dataforseo"],
        )
        parser.add_argument("--top", type=int, default=10)
        parser.add_argument("--limit", type=int, default=50)

        # DataForSEO async flow
        parser.add_argument(
            "--submit",
            action="store_true",
            help="Submit tasks to DataForSEO (async).",
        )
        parser.add_argument(
            "--poll",
            action="store_true",
            help="Poll DataForSEO tasks and store results.",
        )
        parser.add_argument(
            "--location-code",
            dest="location_code",
            type=int,
            help="Numeric DataForSEO location_code (e.g. 2840).",
        )
        parser.add_argument(
            "--language-code",
            dest="language_code",
            type=str,
            default="en",
            help="Language code (e.g. en).",
        )

    def handle(self, *args, **opts):
        project_id = opts["project"]
        provider = opts["provider"]
        top = opts["top"]
        limit = opts["limit"]

        project = Project.objects.filter(id=project_id).first()
        if not project:
            raise CommandError(f"Project {project_id} not found")

        # If no flags passed for dataforseo, do submit+poll in one go (single pass)
        do_submit = bool(opts.get("submit"))
        do_poll = bool(opts.get("poll"))
        if provider == "dataforseo" and not do_submit and not do_poll:
            do_submit, do_poll = True, True

        serp_run = None

        # IMPORTANT:
        # If you run poll-only in a separate command, you MUST reuse the last SerpRun that has task_id.
        if provider == "dataforseo" and do_poll and not do_submit:
            serp_run = (
                SerpRun.objects.filter(project=project, provider="dataforseo")
                .exclude(task_id__isnull=True)
                .exclude(task_id="")
                .order_by("-id")
                .first()
            )
            if not serp_run:
                raise CommandError(
                    "No encontré ningún SerpRun previo con task_id para hacer poll. Ejecuta primero --submit."
                )

            serp_run.status = SerpRun.Status.RUNNING if hasattr(SerpRun, "Status") else "running"
            if hasattr(serp_run, "started_at") and not serp_run.started_at:
                serp_run.started_at = timezone.now()
                serp_run.save(update_fields=["status", "started_at"])
            else:
                serp_run.save(update_fields=["status"])

        # Otherwise, create a new SerpRun
        if serp_run is None:
            serp_run = SerpRun.objects.create(
                project=project,
                provider=provider,
                status=SerpRun.Status.RUNNING if hasattr(SerpRun, "Status") else "running",
                started_at=timezone.now() if hasattr(SerpRun, "started_at") else None,
            )

        try:
            if provider == "mock":
                serp_run.raw = {"mock": True, "note": "No external calls made."}
                serp_run.status = SerpRun.Status.DONE if hasattr(SerpRun, "Status") else "done"
                if hasattr(serp_run, "completed_at"):
                    serp_run.completed_at = timezone.now()
                    serp_run.save(update_fields=["raw", "status", "completed_at"])
                else:
                    serp_run.save(update_fields=["raw", "status"])
                return

            if provider == "serpapi":
                prov = SerpAPIProvider()
                results = call_compatible(prov.fetch, project=project, limit=limit)

                serp_run.raw = results
                serp_run.status = SerpRun.Status.DONE if hasattr(SerpRun, "Status") else "done"
                if hasattr(serp_run, "completed_at"):
                    serp_run.completed_at = timezone.now()
                serp_run.save()

                build_snapshots_for_run(serp_run, top=top)
                return

            # provider == dataforseo
            prov = DataForSEOProvider()

            if do_submit:
                location_code = opts.get("location_code")
                if not location_code:
                    raise CommandError(
                        "--location-code is required for --submit with dataforseo (numeric, e.g. 2840)."
                    )
                language_code = (opts.get("language_code") or "en").strip()

                task_ids = call_compatible(
                    prov.submit_task,
                    project=project,
                    location_code=location_code,
                    language_code=language_code,
                    limit=limit,
                )

                serp_run.task_id = ",".join(task_ids) if isinstance(task_ids, list) else str(task_ids)
                serp_run.status = SerpRun.Status.SUBMITTED if hasattr(SerpRun, "Status") else "submitted"
                serp_run.save(update_fields=["task_id", "status"])

            if do_poll:
                # Ensure we have a task_id
                if not getattr(serp_run, "task_id", None):
                    raise CommandError(
                        "Este SerpRun no tiene task_id. Ejecuta primero --submit o usa el SerpRun correcto."
                    )

                results = call_compatible(
                    prov.poll_task,
                    project=project,
                    serp_run=serp_run,
                    task_id=serp_run.task_id,
                    limit=limit,
                )

                serp_run.raw = results
                serp_run.status = SerpRun.Status.DONE if hasattr(SerpRun, "Status") else "done"
                if hasattr(serp_run, "completed_at"):
                    serp_run.completed_at = timezone.now()
                serp_run.save()

                build_snapshots_for_run(serp_run, top=top)

        except Exception as e:
            serp_run.status = SerpRun.Status.ERROR if hasattr(SerpRun, "Status") else "error"
            if hasattr(serp_run, "error"):
                serp_run.error = str(e)
            if hasattr(serp_run, "error_message"):
                serp_run.error_message = str(e)
            serp_run.save()
            raise
