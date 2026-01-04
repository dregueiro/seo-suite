from django.core.management.base import BaseCommand
from core.services import RunSpec, create_run, mark_running, mark_success, attach_provider_response
from core.models import Run


class Command(BaseCommand):
    help = "Crea un Run de ejemplo (trazabilidad + provider response)."

    def handle(self, *args, **options):
        spec = RunSpec(
            provider=Run.Provider.INTERNAL,
            kind="internal.sample",
            inputs={"hello": "world", "n": 1},
        )
        run = create_run(spec)
        mark_running(run)

        attach_provider_response(
            run=run,
            provider=Run.Provider.INTERNAL,
            endpoint="internal://sample",
            http_status=200,
            request_body='{"ping": true}',
            response_body='{"pong": true}',
        )

        mark_success(run, outputs={"ok": True}, cost_micros=0)
        self.stdout.write(self.style.SUCCESS(f"Run creado: {run.id}"))
