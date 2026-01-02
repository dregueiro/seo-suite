from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import urlparse

from integrations.dataforseo.client import DataForSEOClient


@dataclass
class SerpParsed:
    results: List[dict]
    features: List[dict]


class DataForSEOProvider:
    """
    DataForSEO SERP Provider.

    - Soporta:
      1) Live Advanced (sin cola) para 1 keyword: fetch_live_advanced(...)
      2) Cola async:
         - submit_task(...) -> devuelve task_id (str) o lista de task_id (list[str])
         - poll_task(task_id=...) -> devuelve dict normalizado listo para guardar en SerpRun.raw

    Nota:
    - DataForSEO usa location_code NUMERICO (ej: 2840 para USA), no "us".
    """

    def __init__(self):
        self.client = DataForSEOClient()

    # -------------------------
    # Public API (Live)
    # -------------------------
    def fetch_live_advanced(
        self,
        *,
        keyword: str,
        language_code: str,
        location_code: int,
        device: str = "desktop",
        depth: int = 10,
    ) -> Tuple[List[dict], dict]:
        """
        Llamada sin cola (live advanced).
        Devuelve (results_normalizados, raw_response).
        """
        payload = [
            {
                "keyword": keyword,
                "language_code": language_code,
                "location_code": int(location_code),
                "device": device,
                "depth": int(depth),
            }
        ]

        resp = self.client.post("/serp/google/organic/live/advanced", payload)

        parsed = self.parse_top10(resp)

        results = [
            {
                "position": int(r.get("position") or 0) or 0,
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "domain": r.get("domain") or "",
                "snippet": r.get("snippet") or "",
                "raw": r.get("raw"),
            }
            for r in parsed.results
        ]

        return results, resp

    # -------------------------
    # Public API (Async Queue)
    # -------------------------
    def submit_task(
        self,
        keyword: Optional[str] = None,
        language_code: str = "en",
        location_code: int = 2840,
        device: str = "mobile",
        depth: int = 10,
        *,
        # Opcionales para batch / integración con tu management command
        keywords: Optional[Iterable[str]] = None,
        project: Any = None,
        limit: Optional[int] = None,
    ) -> Union[str, List[str]]:
        """
        Crea task(s) en DataForSEO.

        Soporta 3 formas:
        - submit_task(keyword="...", ...)
        - submit_task(keywords=[...], ...)
        - submit_task(project=<Project>, ...)  -> intenta extraer keywords del proyecto

        Retorna:
        - str si enviaste 1 keyword
        - list[str] si enviaste varias
        """
        kw_list = self._resolve_keywords(keyword=keyword, keywords=keywords, project=project, limit=limit)
        if not kw_list:
            raise RuntimeError("DataForSEO: no keywords para submit_task()")

        payload = [
            {
                "keyword": kw,
                "language_code": language_code,
                "location_code": int(location_code),
                "device": device,
                "depth": int(depth),
            }
            for kw in kw_list
        ]

        resp = self.client.post("/serp/google/organic/task_post", payload)

        tasks = resp.get("tasks") or []
        if not tasks:
            raise RuntimeError(f"DataForSEO: respuesta sin tasks: {resp}")

        ids: List[str] = []
        for t in tasks:
            tid = t.get("id")
            if tid:
                ids.append(str(tid))

        if not ids:
            raise RuntimeError(f"DataForSEO: tasks sin id: {resp}")

        # Compat: si solo 1 keyword, devolvemos str
        if len(kw_list) == 1:
            return ids[0]
        return ids

    def poll_task(
        self,
        task_id: Union[str, List[str]],
        *,
        # opcionales para compat con tu run_serp (se filtran con call_compatible)
        project: Any = None,
        serp_run: Any = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Poll de task(s) por id(s).

        task_id puede ser:
        - "1234567890"
        - "id1,id2,id3"
        - ["id1","id2"]

        Devuelve dict NORMALIZADO:
        {
          "provider": "dataforseo",
          "results": [
            {
              "task_id": "...",
              "keyword": "...",
              "items": [ {position,title,url,domain,snippet,raw}, ... ],
              "features": [ {type, raw}, ... ],
              "raw": <respuesta_raw_del_task_get>
            },
            ...
          ],
          "raw_tasks": [<raw_task_get_1>, <raw_task_get_2>, ...]
        }
        """
        task_ids = self._normalize_task_ids(task_id)
        if limit:
            task_ids = task_ids[: int(limit)]

        normalized_results: List[dict] = []
        raw_tasks: List[dict] = []

        for tid in task_ids:
            raw = self.client.get(f"/serp/google/organic/task_get/{tid}")
            raw_tasks.append(raw)

            if not self.is_ready(raw):
                # Todavía no listo -> lo incluimos como placeholder, útil para debug
                normalized_results.append(
                    {
                        "task_id": tid,
                        "keyword": self._extract_keyword_from_task_get(raw) or "",
                        "items": [],
                        "features": [],
                        "raw": raw,
                        "ready": False,
                    }
                )
                continue

            parsed = self.parse_top10(raw)
            kw = self._extract_keyword_from_task_get(raw) or ""

            items = [
                {
                    "position": int(r.get("position") or 0) or 0,
                    "title": r.get("title") or "",
                    "url": r.get("url") or "",
                    "domain": r.get("domain") or "",
                    "snippet": r.get("snippet") or "",
                    "raw": r.get("raw"),
                }
                for r in parsed.results
            ]

            normalized_results.append(
                {
                    "task_id": tid,
                    "keyword": kw,
                    "items": items,
                    "features": parsed.features,
                    "raw": raw,
                    "ready": True,
                }
            )

        return {
            "provider": "dataforseo",
            "results": normalized_results,
            "raw_tasks": raw_tasks,
        }

    # -------------------------
    # Helpers (Ready / Parse)
    # -------------------------
    def is_ready(self, resp: dict) -> bool:
        """
        True si el task_get trae status_code OK y result con items.
        """
        tasks = resp.get("tasks") or []
        if not tasks:
            return False
        task = tasks[0] or {}
        status_code = task.get("status_code")

        # 20000 suele ser "Ok" en DataForSEO
        if status_code != 20000:
            return False

        result = task.get("result") or []
        if not result:
            return False

        result0 = result[0] or {}
        items = result0.get("items") or []
        return bool(items)

    def parse_top10(self, resp: dict) -> SerpParsed:
        """
        Parsea respuesta DataForSEO (live advanced o task_get).
        Devuelve top 10 orgánicos + features básicas.
        """
        tasks = resp.get("tasks") or []
        if not tasks:
            return SerpParsed(results=[], features=[])

        task = tasks[0] or {}
        result0 = (task.get("result") or [None])[0] or {}
        items = result0.get("items") or []

        results: List[dict] = []
        features: List[dict] = []

        for item in items:
            t = item.get("type")
            if t == "organic":
                url = item.get("url") or ""
                domain = item.get("domain") or ""
                if not domain and url:
                    domain = self._safe_domain(url)

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

        results = sorted(results, key=lambda x: int(x.get("position") or 0))[:10]
        return SerpParsed(results=results, features=features)

    # -------------------------
    # Internal utilities
    # -------------------------
    def _safe_domain(self, url: str) -> str:
        try:
            netloc = urlparse(url).netloc or ""
            return netloc.replace("www.", "")
        except Exception:
            return ""

    def _normalize_task_ids(self, task_id: Union[str, List[str]]) -> List[str]:
        if isinstance(task_id, list):
            return [str(x).strip() for x in task_id if str(x).strip()]
        if isinstance(task_id, str):
            s = task_id.strip()
            if not s:
                return []
            if "," in s:
                return [p.strip() for p in s.split(",") if p.strip()]
            return [s]
        return [str(task_id).strip()]

    def _extract_keyword_from_task_get(self, resp: dict) -> Optional[str]:
        """
        Intenta extraer keyword desde task_get.
        DataForSEO suele incluir task->data->keyword o result0->keyword.
        """
        tasks = resp.get("tasks") or []
        if not tasks:
            return None
        task = tasks[0] or {}

        data = task.get("data") or {}
        if isinstance(data, dict):
            kw = data.get("keyword")
            if kw:
                return str(kw)

        result0 = (task.get("result") or [None])[0] or {}
        kw2 = result0.get("keyword")
        if kw2:
            return str(kw2)

        return None

    def _resolve_keywords(
        self,
        *,
        keyword: Optional[str],
        keywords: Optional[Iterable[str]],
        project: Any,
        limit: Optional[int],
    ) -> List[str]:
        """
        Resuelve lista de keywords desde:
        - keyword (single)
        - keywords (iterable)
        - project (intenta detectar related manager típico)
        """
        out: List[str] = []

        if keyword:
            out = [str(keyword).strip()]
        elif keywords is not None:
            out = [str(k).strip() for k in keywords if str(k).strip()]
        elif project is not None:
            out = self._extract_keywords_from_project(project)

        if limit:
            out = out[: int(limit)]

        # dedupe conservando orden
        seen = set()
        deduped: List[str] = []
        for k in out:
            if k and k not in seen:
                seen.add(k)
                deduped.append(k)

        return deduped

    def _extract_keywords_from_project(self, project: Any) -> List[str]:
        """
        Intenta extraer keywords del proyecto sin depender de un modelo exacto.
        Prueba nombres comunes de related managers.
        """
        # si es queryset/manager directo
        candidates = [
            "keywords",          # project.keywords.all()
            "projectkeyword_set",
            "trackedkeyword_set",
            "serpkeyword_set",
            "keywords_set",
        ]

        for attr in candidates:
            rel = getattr(project, attr, None)
            if rel is None:
                continue

            try:
                qs = rel.all()
            except Exception:
                qs = None

            if qs is None:
                continue

            # intenta campos comunes en modelos de keyword
            field_candidates = ["keyword", "query", "term", "text", "name"]
            for f in field_candidates:
                try:
                    vals = list(qs.values_list(f, flat=True))
                    vals = [str(v).strip() for v in vals if str(v).strip()]
                    if vals:
                        return vals
                except Exception:
                    pass

            # fallback: str(obj)
            try:
                vals = [str(obj).strip() for obj in qs]
                vals = [v for v in vals if v]
                if vals:
                    return vals
            except Exception:
                pass

        raise RuntimeError(
            "DataForSEOProvider: no pude extraer keywords desde project. "
            "Pasa keyword=..., keywords=[...], o ajusta _extract_keywords_from_project() "
            "al related_name real de tu modelo."
        )
