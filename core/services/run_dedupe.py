import hashlib
import json
from datetime import timedelta
from typing import Any, Dict, Optional

from django.utils import timezone

from core.models import Run


def stable_hash(payload: Dict[str, Any]) -> str:
    """
    Hash determinístico para dedupe.
    """
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_success_run(
    *,
    provider: str,
    kind: str,
    input_hash: str,
    max_age_days: int = 7,
) -> Optional[Run]:
    """
    Devuelve el último Run success que coincida con provider/kind/input_hash
    y que no sea más viejo que max_age_days.
    """
    qs = Run.objects.filter(provider=provider, kind=kind, input_hash=input_hash, status="success").order_by("-created_at")
    run = qs.first()
    if not run:
        return None

    if max_age_days is not None:
        cutoff = timezone.now() - timedelta(days=max_age_days)
        if run.created_at and run.created_at < cutoff:
            return None

    return run
