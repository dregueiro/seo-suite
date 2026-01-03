import hashlib
from integrations.serp.types import SerpRequest

def _sha32(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]

def serp_cache_key(req: SerpRequest, provider: str) -> str:
    q = (req.normalized_query() or "").lower()
    country = (req.country_code or "").lower()
    lang = (req.language_code or "").lower()
    device = (req.device or "desktop").lower()
    location = (getattr(req, "location_name", "") or "").lower().strip()

    base = f"serp|{provider}|q={q}|gl={country}|hl={lang}|device={device}|loc={location}|n={req.num_results}"
    return f"serp:{provider}:{_sha32(base)}"

def keyword_ideas_cache_key(
    *, provider: str, seed: str, location_code: int, language_code: str, project_id: int, top_n: int
) -> str:
    base = (
        f"kw_ideas|p={project_id}|prov={provider}|seed={(seed or '').strip().lower()}"
        f"|loc={int(location_code)}|lang={(language_code or '').strip().lower()}|top={int(top_n)}"
    )
    return f"kw_ideas:{provider}:{_sha32(base)}"

def keyword_metrics_cache_key(
    *, provider: str, keyword: str, location_code: int, language_code: str, project_id: int
) -> str:
    base = (
        f"kw_metrics|p={project_id}|prov={provider}|kw={(keyword or '').strip().lower()}"
        f"|loc={int(location_code)}|lang={(language_code or '').strip().lower()}"
    )
    return f"kw_metrics:{provider}:{_sha32(base)}"

def gsc_cache_key(
    *,
    project_id: int,
    site_url: str,
    date: str,
    dimensions: list[str] | tuple[str, ...],
    filters: dict | None = None,
) -> str:
    dims = ",".join([d.strip().lower() for d in (dimensions or [])])
    filt = (filters or {})
    base = (
        f"gsc|p={project_id}|site={(site_url or '').strip().lower()}"
        f"|date={date}|dims={dims}|filters={str(sorted(filt.items()))}"
    )
    return f"gsc:{_sha32(base)}"
