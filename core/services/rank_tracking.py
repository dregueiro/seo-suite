from urllib.parse import urlparse

from core.models import SerpRun, SerpResult, SerpKeywordSnapshot
from core.services.serpapi_provider import SerpApiProvider
from core.services.dataforseo_provider import DataForSEOProvider

PROVIDERS = {
    "serpapi": SerpApiProvider,
    "dataforseo": DataForSEOProvider,
}

def get_provider(name: str):
    name = (name or "serpapi").lower().strip()
    cls = PROVIDERS.get(name, SerpApiProvider)
    return cls()


def normalize_domain(domain_or_url: str) -> str:
    s = (domain_or_url or "").strip().lower()
    if not s:
        return ""
    if "://" in s:
        try:
            s = urlparse(s).netloc.lower()
        except Exception:
            pass
    if s.startswith("www."):
        s = s[4:]
    s = s.strip(".")
    return s


def domain_matches(result_domain: str, tracked_domain: str) -> bool:
    rd = normalize_domain(result_domain)
    td = normalize_domain(tracked_domain)
    if not rd or not td:
        return False
    if rd == td:
        return True
    return rd.endswith("." + td)


def build_snapshots_for_run(run: SerpRun, keyword_ids: list[int]) -> int:
    tracked = normalize_domain(run.project.domain)

    results = (
        SerpResult.objects
        .filter(serp_run=run)
        .only("keyword_id", "position", "domain","url")
        .order_by("keyword_id", "position")
    )

    grouped: dict[int, list[SerpResult]] = {}
    for r in results:
        grouped.setdefault(r.keyword_id, []).append(r)

    bulk = []
    for kw_id in keyword_ids:
        rows = grouped.get(kw_id, [])
        top3 = rows[:3]
        top3_domains = [normalize_domain(r.domain) for r in top3]
        top3_urls = [(r.url or "") for r in top3]

        if rows:
            top_position = rows[0].position
            top_domain = normalize_domain(rows[0].domain)
            top_url = rows[0].url or ""
        else:
            top_position = None
            top_domain = ""
            top_url = ""

        tracked_pos = None
        for r in rows:
            if domain_matches(r.domain, tracked):
                tracked_pos = r.position
                break

        bulk.append(
            SerpKeywordSnapshot(
                serp_run=run,
                keyword_id=kw_id,
                tracked_domain=tracked,
                tracked_position=tracked_pos,
                top_domain=top_domain,
                top_position=top_position,
                top_url=top_url,
                top3 = rows[:3]
                top3_domains = [normalize_domain(r.domain) for r in top3]
                top3_urls = [(r.url or "") for r in top3]
            )
        )

    if bulk:
        SerpKeywordSnapshot.objects.bulk_create(bulk, batch_size=500)

    return len(bulk)
