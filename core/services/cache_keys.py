import hashlib
from integrations.serp.types import SerpRequest


def serp_cache_key(req: SerpRequest, provider: str) -> str:
    q = (req.normalized_query() or "").lower()
    country = (req.country_code or "").lower()
    lang = (req.language_code or "").lower()
    device = (req.device or "desktop").lower()
    location = (getattr(req, "location_name", "") or "").lower().strip()

    base = f"serp|{provider}|q={q}|gl={country}|hl={lang}|device={device}|loc={location}|n={req.num_results}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]
    return f"serp:{provider}:{digest}"
