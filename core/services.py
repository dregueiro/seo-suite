from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from django.utils import timezone

from core.models import Run, ProviderResponse
from core.utils import make_input_hash


@dataclass(frozen=True)
class RunSpec:
    provider: str
    kind: str
    inputs: Dict[str, Any]
    entity: Optional[object] = None  # Project u otro (GenericFK)


def create_run(spec: RunSpec) -> Run:
    input_hash = make_input_hash(spec.provider, spec.kind, spec.inputs)
    run = Run.objects.create(
        provider=spec.provider,
        kind=spec.kind,
        inputs=spec.inputs,
        outputs={},
        input_hash=input_hash,
        status=Run.Status.PENDING,
        started_at=None,
        finished_at=None,
        entity=spec.entity,
    )
    return run


def mark_running(run: Run) -> Run:
    run.status = Run.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at", "updated_at"])
    return run


def mark_success(run: Run, outputs: Dict[str, Any], cost_micros: int = 0) -> Run:
    run.status = Run.Status.SUCCESS
    run.outputs = outputs or {}
    run.cost_micros = int(cost_micros or 0)
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "outputs", "cost_micros", "finished_at", "updated_at"])
    return run


def mark_failed(run: Run, message: str, details: Optional[Dict[str, Any]] = None) -> Run:
    run.status = Run.Status.FAILED
    run.error_message = message or ""
    run.error_details = details or {}
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "error_message", "error_details", "finished_at", "updated_at"])
    return run


def attach_provider_response(
    run: Run,
    provider: str,
    endpoint: str = "",
    http_status: Optional[int] = None,
    request_headers: Optional[Dict[str, Any]] = None,
    request_body: str = "",
    response_headers: Optional[Dict[str, Any]] = None,
    response_body: str = "",
) -> ProviderResponse:
    return ProviderResponse.objects.create(
        run=run,
        provider=provider,
        endpoint=endpoint,
        http_status=http_status,
        request_headers=request_headers or {},
        request_body=request_body or "",
        response_headers=response_headers or {},
        response_body=response_body or "",
    )


def get_cached_success_run(provider: str, kind: str, inputs: Dict[str, Any]) -> Optional[Run]:
    """
    Caché mínima: si existe un SUCCESS con el mismo input_hash, lo devolvemos.
    TTL lo añadimos cuando empecemos a gastar dinero en providers.
    """
    input_hash = make_input_hash(provider, kind, inputs)
    return (
        Run.objects.filter(provider=provider, kind=kind, input_hash=input_hash, status=Run.Status.SUCCESS)
        .order_by("-finished_at")
        .first()
    )
