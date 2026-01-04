import hashlib
import json
from typing import Any, Dict


def deterministic_json(data: Dict[str, Any]) -> str:
    """
    JSON determinístico: claves ordenadas, sin espacios.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def make_input_hash(provider: str, kind: str, inputs: Dict[str, Any]) -> str:
    """
    Hash estable para dedupe/caché.
    """
    payload = {
        "provider": provider,
        "kind": kind,
        "inputs": inputs or {},
    }
    raw = deterministic_json(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
