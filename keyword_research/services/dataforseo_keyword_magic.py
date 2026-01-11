import csv
import io
import json
import hashlib
from typing import Optional, List, Dict

from django.utils import timezone

from core.models import Run, RunArtifact
from core.services.runs import (
    RunSpec,
    attach_provider_response,
    create_run,
    mark_failed,
    mark_running,
    mark_success,
)
from projects.models import Project
from keyword_research.models import KeywordMetric

from clients.dataforseo import DataForSEOClient
from keyword_research.services.artifacts import write_run_artifact


KIND = "keyword_research.dataforseo.keyword_magic"
ALGO_VERSION = "dataforseo_keyword_magic_v2"

ENDPOINT_KK = "/keywords_data/google_ads/keywords_for_keywords/live"
ENDPOINT_LABS = "/dataforseo_labs/google/related_keywords/live"


def _dedupe_hash(project_id: int, inputs: dict) -> str:
    raw = json.dumps({"kind": KIND, "project_id": project_id, "inputs": inputs}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _find_cached_success(project: Project, dedupe: str) -> Optional[Run]:
    return (
        Run.objects.filter(
            entity_object_id=project.id,
            kind=KIND,
            status=Run.Status.SUCCESS,
            inputs__dedupe=dedupe,
        )
        .order_by("-created_at")
        .first()
    )


def _as_micros(x) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(round(float(x) * 1_000_000))
    except Exception:
        return None


def _lang_name(language_code: str) -> str:
    m = {
        "en": "English",
        "es": "Spanish",
        "pt": "Portuguese",
        "fr": "French",
        "de": "German",
        "it": "Italian",
    }
    return m.get((language_code or "").lower(), "English")


def _needs_fallback(rows: List[dict]) -> bool:
    # si no hay ideas o sólo viene la seed, o vienen todas las métricas nulas
    if not rows or len(rows) <= 1:
        return True
    non_null = 0
    for r in rows:
        if r.get("search_volume") is not None or r.get("cpc") is not None or r.get("competition") is not None:
            non_null += 1
    return non_null == 0


def build_dataforseo_keyword_magic_run(
    *,
    project: Project,
    seed: str,
    limit: int = 200,
    location_name: str = "United States",
    language_code: str = "en",
    force: bool = False,
) -> Run:
    seed = (seed or "").strip()
    client = DataForSEOClient()

    inputs = {
        "project_id": project.id,
        "seed": seed,
        "limit": int(limit),
        "location_name": location_name,
        "language_code": language_code,
        "algo_version": ALGO_VERSION,
        "force": bool(force),
    }
    inputs["dedupe"] = _dedupe_hash(project.id, inputs)

    run = create_run(RunSpec(provider="dataforseo", kind=KIND, inputs=inputs, entity=project))
    mark_running(run)

    try:
        if not seed:
            mark_failed(run, "Falta seed", {})
            return run

        if not client.is_configured():
            mark_failed(run, "DataForSEO no está configurado (DATAFORSEO_LOGIN/PASSWORD).", {})
            return run

        if not force:
            cached = _find_cached_success(project, inputs["dedupe"])
            if cached:
                return cached

        total_cost = 0.0
        fallback_used = False

        # 1) Keywords Data: keywords_for_keywords
        req_kk = [{
            "keywords": [seed],
            "location_name": location_name,
            "language_code": language_code,
            "sort_by": "relevance",
            "include_adult_keywords": False,
        }]

        resp_kk = client.post(ENDPOINT_KK, req_kk)
        payload_kk = resp_kk.payload

        attach_provider_response(
            run=run,
            provider="dataforseo",
            endpoint=ENDPOINT_KK,
            http_status=resp_kk.http_status,
            request_body=json.dumps(req_kk, ensure_ascii=False, indent=2),
            response_body=json.dumps(payload_kk, ensure_ascii=False, indent=2),
        )

        total_cost += float(payload_kk.get("cost") or 0.0)

        tasks = payload_kk.get("tasks") or []
        t0 = tasks[0] if tasks else {}
        rows_kk = t0.get("result") or []
        if isinstance(rows_kk, dict):
            rows_kk = [rows_kk]

        items: List[Dict] = []

        # 2) Fallback Labs si no hay data útil
        if _needs_fallback(rows_kk):
            fallback_used = True

            req_labs = [{
                "keyword": seed,
                "location_name": location_name,
                "language_name": _lang_name(language_code),
                "limit": int(limit),
            }]

            resp_labs = client.post(ENDPOINT_LABS, req_labs)
            payload_labs = resp_labs.payload

            attach_provider_response(
                run=run,
                provider="dataforseo",
                endpoint=ENDPOINT_LABS,
                http_status=resp_labs.http_status,
                request_body=json.dumps(req_labs, ensure_ascii=False, indent=2),
                response_body=json.dumps(payload_labs, ensure_ascii=False, indent=2),
            )

            total_cost += float(payload_labs.get("cost") or 0.0)

            tL = (payload_labs.get("tasks") or [{}])[0]
            resL0 = (tL.get("result") or [{}])[0]
            labs_items = resL0.get("items") or []

            for it in labs_items:
                kd = (it.get("keyword_data") or {})
                ki = (kd.get("keyword_info") or {})
                kw = kd.get("keyword")
                if not kw:
                    continue
                items.append({
                    "keyword": kw,
                    "avg_monthly_searches": ki.get("search_volume"),
                    "cpc_micros": _as_micros(ki.get("cpc")),
                    "competition_level": ki.get("competition_level"),
                    "source": "dataforseo_labs",
                    "source_confidence": 0.75,
                    "retrieved_at": timezone.now().isoformat(),
                    "score": None,
                })
        else:
            for row in rows_kk:
                kw = row.get("keyword")
                if not kw:
                    continue
                items.append({
                    "keyword": kw,
                    "avg_monthly_searches": row.get("search_volume"),
                    "cpc_micros": _as_micros(row.get("cpc") or row.get("high_top_of_page_bid") or row.get("low_top_of_page_bid")),
                    "competition_level": row.get("competition"),
                    "source": "dataforseo_keywords_data",
                    "source_confidence": 0.65,
                    "retrieved_at": timezone.now().isoformat(),
                    "score": None,
                })

        # dedupe por keyword
        seen = set()
        uniq = []
        for it in items:
            k = (it.get("keyword") or "").strip().lower()
            if not k or k in seen:
                continue
            seen.add(k)
            uniq.append(it)

        uniq = uniq[:int(limit)]

        # Persistir KeywordMetric (contract)
        now = timezone.now()
        objs = []
        for it in uniq:
            objs.append(KeywordMetric(
                project=project,
                run=run,
                keyword=it.get("keyword"),
                locale=f"{language_code}_US" if location_name == "United States" else None,
                language=language_code,
                geo=location_name,
                avg_monthly_searches=it.get("avg_monthly_searches"),
                cpc_micros=it.get("cpc_micros"),
                competition_level=it.get("competition_level"),
                source=it.get("source"),
                source_confidence=it.get("source_confidence"),
                retrieved_at=now,
            ))
        if objs:
            KeywordMetric.objects.bulk_create(objs)

        # Artifact normalizado JSON
        norm_payload = {
            "seed": seed,
            "project_id": project.id,
            "algo_version": ALGO_VERSION,
            "fallback_used": fallback_used,
            "count": len(uniq),
            "limit": int(limit),
            "location_name": location_name,
            "language_code": language_code,
            "cost_total_usd": total_cost,
            "created_at": now.isoformat(timespec="seconds"),
            "items": uniq,
        }

        art_json = write_run_artifact(
            run=run,
            filename=f"keyword_magic_dataforseo_{project.id}_{str(run.id)[:8]}.json",
            artifact_type=RunArtifact.ArtifactType.JSON,
            content_bytes=json.dumps(norm_payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )

        # Artifact CSV
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["keyword", "avg_monthly_searches", "cpc_micros", "competition_level", "source", "source_confidence"])
        for it in uniq:
            w.writerow([
                it.get("keyword"),
                it.get("avg_monthly_searches"),
                it.get("cpc_micros"),
                it.get("competition_level"),
                it.get("source"),
                it.get("source_confidence"),
            ])

        art_csv = write_run_artifact(
            run=run,
            filename=f"keyword_magic_dataforseo_{project.id}_{str(run.id)[:8]}.csv",
            artifact_type=RunArtifact.ArtifactType.CSV,
            content_bytes=buf.getvalue().encode("utf-8"),
        )

        mark_success(run, outputs={
            "ok": True,
            "created_metrics": len(objs),
            "rows_count": len(uniq),
            "seed": seed,
            "limit": int(limit),
            "location_name": location_name,
            "language_code": language_code,
            "algo_version": ALGO_VERSION,
            "fallback_used": fallback_used,
            "cost_total_usd": total_cost,
            "artifact_json_id": str(art_json.id),
            "artifact_csv_id": str(art_csv.id),
        })
        return run

    except Exception as e:
        mark_failed(run, "DataForSEO keyword magic failed", {"error": str(e)})
        return run
