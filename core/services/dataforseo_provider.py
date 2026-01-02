from dataclasses import dataclass
from urllib.parse import urlparse
from core.services.dataforseo_client import DataForSEOClient


@dataclass
class SerpParsed:
    results: list
    features: list


class DataForSEOProvider:
    """
    Standard queue, submit task, luego poll por task_id.
    """

    def __init__(self):
        self.client = DataForSEOClient()

    def submit_task(
        self,
        keyword: str,
        language_code: str,
        location_code: int,
        device: str = "mobile",
        depth: int = 10,
    ) -> str:
        payload = [
            {
                "keyword": keyword,
                "language_code": language_code,
                "location_code": location_code,
                "device": device,
                "depth": depth,
            }
        ]

        resp = self.client.post("/serp/google/organic/task_post", payload)

        tasks = resp.get("tasks") or []
        if not tasks:
            raise RuntimeError(f"DataForSEO: respuesta sin tasks: {resp}")

        task_id = tasks[0].get("id")
        if not task_id:
            raise RuntimeError(f"DataForSEO: task sin id: {resp}")

        return task_id

    def poll_task(self, task_id: str) -> dict:
        resp = self.client.get(f"/serp/google/organic/task_get/{task_id}")
        return resp

    def is_ready(self, resp: dict) -> bool:
        tasks = resp.get("tasks") or []
        if not tasks:
            return False
        task = tasks[0]
        status_code = task.get("status_code")
        result = task.get("result")
        return status_code == 20000 and bool(result)

    def parse_top10(self, resp: dict) -> SerpParsed:
        tasks = resp.get("tasks") or []
        task = tasks[0]
        result0 = (task.get("result") or [None])[0] or {}
        items = result0.get("items") or []

        results = []
        features = []

        for item in items:
            t = item.get("type")
            if t == "organic":
                url = item.get("url") or ""
                domain = item.get("domain") or ""
                if not domain and url:
                    try:
                        domain = urlparse(url).netloc.replace("www.", "")
                    except Exception:
                        domain = ""
                results.append(
                    {
                        "position": item.get("rank_group") or item.get("rank_absolute") or 0,
                        "title": item.get("title") or "",
                        "url": url,
                        "domain": domain,
                        "snippet": item.get("description") or "",
                        "raw": item,
                    }
                )
            elif t in {"people_also_ask", "local_pack", "featured_snippet", "sitelinks"}:
                features.append({"type": t, "raw": item})

        results = sorted(results, key=lambda x: x["position"])[:10]
        return SerpParsed(results=results, features=features)
