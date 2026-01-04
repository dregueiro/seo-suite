from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Optional

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from core.models import Run, ProviderResponse


def stable_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _status(name: str, fallback: str) -> str:
    try:
        return getattr(Run.Status, name)
    except Exception:
        return fallback


@dataclass(frozen=True)
class RunSpec:
    provider: str
    kind: str
    inputs: Dict[str, Any]
    entity_content_type: Optional[ContentType] = None
    entity_object_id: Optional[int] = None


def create_run(spec: RunSpec) -> Run:
    return Run.objects.create(
        provider=spec.provider,
        kind=spec.kind,
        status=_status("QUEUED", "queued"),
        inputs=spec.inputs,
        input_hash=stable_hash(spec.inputs),
        entity_content_type=spec.entity_content_type,
        entity_object_id=spec.entity_object_id,
    )


def mark_running(run: Run) -> Run:
    run.status = _status("RUNNING", "running")
    run.started_at = run.started_at or timezone.now()
    run.save(update_fields=["status", "started_at"])
    return run


def mark_success(run: Run, outputs: Optional[Dict[str, Any]] = None, cost_micros: int = 0) -> Run:
    run.status = _status("SUCCESS", "success")
    if outputs is not None:
        run.outputs = outputs
    run.cost_micros = cost_micros or 0
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "outputs", "cost_micros", "finished_at"])
    return run


def mark_failed(run: Run, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> Run:
    run.status = _status("FAILED", "failed")
    run.error_message = error_message
    if error_details is not None:
        run.error_details = json.dumps(error_details, ensure_ascii=False)[:200000]
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "error_message", "error_details", "finished_at"])
    return run


def attach_provider_response(
    *,
    run: Run,
    provider: str,
    endpoint: str,
    http_status: int = 200,
    request_body: Optional[Dict[str, Any]] = None,
    response_body: Optional[Dict[str, Any]] = None,
) -> ProviderResponse:
    return ProviderResponse.objects.create(
        run=run,
        provider=provider,
        endpoint=endpoint,
        http_status=http_status,
        request_body=json.dumps(request_body or {}, ensure_ascii=False)[:200000],
        response_body=json.dumps(response_body or {}, ensure_ascii=False)[:200000],
    )


def get_cached_success_run(
    *,
    provider: str,
    kind: str,
    inputs: Optional[Dict[str, Any]] = None,
    input_hash: Optional[str] = None,
    max_age_days: int = 7,
) -> Optional[Run]:
    ih = input_hash or (stable_hash(inputs) if inputs is not None else None)
    if not ih:
        return None

    run = (
        Run.objects.filter(provider=provider, kind=kind, input_hash=ih, status=_status("SUCCESS", "success"))
        .order_by("-created_at")
        .first()
    )
    if not run:
        return None

    cutoff = timezone.now() - timedelta(days=max_age_days)
    if run.created_at and run.created_at < cutoff:
        return None

    return run
