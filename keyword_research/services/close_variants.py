# keyword_research/services/close_variants.py
import io,unicodedata,csv, traceback, re,json

from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.db.models import Q
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
from keyword_research.models import KeywordMetric
from projects.models import Project

from .artifacts import write_run_artifact


# Incluimos letras (ya normalizadas sin acentos)
_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

KIND = "keyword_research.close_variants"
ALGO_VERSION = "close_variants_v3"  # bump cuando cambie lógica


def _strip_accents(s: str) -> str:
    # NFKD separa acento y letra, luego eliminamos marcas diacríticas
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = _strip_accents(s)
    s = s.replace("&", " and ")
    s = re.sub(r"\s+", " ", s)
    return s


def _tokens(s: str) -> List[str]:
    return _WORD_RE.findall(_norm(s))


def _token_keys(tokens: List[str], n: int = 5) -> Set[str]:
    """
    Clave por prefijo para matching barato:
    - photography vs photographer => photog...
    - quinceañera (-> quinceanera) vs quince => quinc...
    """
    keys = set()
    for t in tokens:
        t = (t or "").strip()
        if not t:
            continue
        keys.add(t[:n])
    return keys


def _score(seed_text: str, seed_tokens: List[str], seed_keys: Set[str], kw_text: str, kw_tokens: List[str]) -> Tuple[int, Dict]:
    """
    Score barato pero más tolerante:
    +3 si contiene la seed completa (substring)
    +2 si contiene TODOS los tokens (por prefijo) (en cualquier orden)
    +1 por cada token compartido (prefijo) (cap 3)
    +1 si comparte al menos 1 token (prefijo) (boost)
    """
    if not kw_text or not kw_tokens:
        return 0, {"reason": "empty_kw"}

    kw_keys = _token_keys(kw_tokens)

    # inter por prefijos
    inter = seed_keys.intersection(kw_keys)
    inter_n = len(inter)

    score = 0
    debug = {"inter_prefixes": sorted(list(inter))[:10], "inter_n": inter_n}

    if seed_text and seed_text in kw_text:
        score += 3
        debug["has_seed_substring"] = True
    else:
        debug["has_seed_substring"] = False

    # "contiene todos" tokens seed (por prefijo)
    if seed_keys and seed_keys.issubset(kw_keys):
        score += 2
        debug["has_all_seed_tokens"] = True
    else:
        debug["has_all_seed_tokens"] = False

    if inter_n >= 1:
        score += 1  # boost por “al menos 1 token”
    score += min(3, inter_n)  # +1 por token (cap)

    debug["score"] = score
    return score, debug


def compute_close_variants(
    seed: str,
    metrics: Iterable[KeywordMetric],
    limit: int = 200,
    min_score: int = 2,  # configurable
) -> Tuple[List[Dict], Dict]:
    seed_text = _norm(seed)
    seed_tokens = _tokens(seed_text)
    seed_keys = _token_keys(seed_tokens)

    items: List[Dict] = []
    filtered_out = 0

    for m in metrics:
        kw = m.keyword or ""
        kw_text = _norm(kw)
        kw_tokens = _tokens(kw_text)

        sc, dbg = _score(seed_text, seed_tokens, seed_keys, kw_text, kw_tokens)

        if sc < min_score:
            filtered_out += 1
            continue

        items.append(
            {
                "keyword": m.keyword,
                "avg_monthly_searches": m.avg_monthly_searches,
                "cpc_micros": m.cpc_micros,
                "competition_level": m.competition_level,
                "source": m.source,
                "source_confidence": m.source_confidence,
                "retrieved_at": m.retrieved_at.isoformat() if m.retrieved_at else None,
                "score": sc,
            }
        )

    items.sort(
        key=lambda x: (
            -(x.get("score") or 0),
            -(x.get("avg_monthly_searches") or 0),
            (x.get("keyword") or ""),
        )
    )

    info = {
        "algo_version": ALGO_VERSION,
        "seed_tokens": seed_tokens[:20],
        "seed_prefixes": sorted(list(seed_keys))[:20],
        "min_score": min_score,
        "filtered_out": filtered_out,
        "returned": min(limit, len(items)),
    }

    return items[:limit], info


def _find_cached_close_variants_run(*, project: Project, seed: str, source_run: Run, limit: int, min_score: int) -> Optional[Run]:
    seed = (seed or "").strip()
    if not seed:
        return None

    return (
        Run.objects.filter(
            entity_object_id=project.id,
            kind=KIND,
            status=Run.Status.SUCCESS,
            inputs__seed=seed,
            inputs__source_run_id=str(source_run.id),
            inputs__limit=limit,
            inputs__min_score=min_score,
            inputs__algo_version=ALGO_VERSION,
        )
        .order_by("-created_at")
        .first()
    )


def build_close_variants_run(
    *,
    project: Project,
    seed: str,
    source_run: Run,
    limit: int = 200,
    min_score: int = 2,
    force: bool = False,
) -> Run:
    """
    Run interno que toma KeywordMetric del source_run y genera close variants.
    - Dedupe fuerte por inputs
    - Normalización robusta
    - Prefilter DB barato para no iterar miles
    """
    provider = Run.Provider.INTERNAL if hasattr(Run.Provider, "INTERNAL") else Run.Provider.ADS
    kind = KIND
    seed = (seed or "").strip()

    inputs = {
        "project_id": project.id,
        "seed": seed,
        "source_run_id": str(source_run.id) if source_run else None,
        "limit": limit,
        "min_score": min_score,
        "source_kind": getattr(source_run, "kind", None),
        "algo_version": ALGO_VERSION,
        "force": bool(force),
    }

    run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
    mark_running(run)

    try:
        if not seed or not source_run:
            mark_failed(run, "Inputs inválidos", {"seed": bool(seed), "source_run": bool(source_run)})
            return run

        if not force:
            cached = _find_cached_close_variants_run(project=project, seed=seed, source_run=source_run, limit=limit, min_score=min_score)
            if cached:
                # devolvemos el cached directamente (sin crear otro run “fantasma”)
                return cached

        # Query base
        base = KeywordMetric.objects.filter(project=project, run=source_run).only(
            "keyword",
            "avg_monthly_searches",
            "cpc_micros",
            "competition_level",
            "source",
            "source_confidence",
            "retrieved_at",
        )

        source_total = base.count()

        # Prefilter DB: keywords que contengan algún prefijo/token del seed (barato y reduce CPU)
        # OJO: icontains con prefijo de 4-5 chars funciona mejor que tokens completos.
        seed_tokens = _tokens(seed)
        prefixes = [t[:5] for t in seed_tokens if len(t) >= 4][:5]  # max 5 prefijos para no explotar OR
        q = Q()
        seed_norm = _norm(seed)
        if seed_norm:
            q |= Q(keyword__icontains=seed_norm)

        for p in prefixes:
            q |= Q(keyword__icontains=p)

        qs = base.filter(q) if q else base
        prefilter_count = qs.count()

        # fallback si prefilter deja 0
        prefilter_used = True
        if prefilter_count == 0:
            qs = base
            prefilter_used = False
            prefilter_count = source_total

        items, info = compute_close_variants(seed, qs, limit=limit, min_score=min_score)

        payload = {
            "seed": seed,
            "project_id": project.id,
            "source_run_id": str(source_run.id),
            "source_kind": source_run.kind,
            "algo_version": ALGO_VERSION,
            "created_at": timezone.now().isoformat(timespec="seconds"),
            "count": len(items),
            "source_total": source_total,
            "prefilter_prefixes": prefixes,
            "info": info,
            "items": items,
            "prefilter_used": prefilter_used,
            "prefilter_count": prefilter_count,
            "skipped_by_prefilter": max(0, source_total - prefilter_count),

        }

        attach_provider_response(
            run=run,
            provider=run.provider,
            endpoint="internal.close_variants",
            http_status=200,
            request_body=json.dumps(inputs, ensure_ascii=False, indent=2),
            response_body=json.dumps(
                {
                    "count": len(items),
                    "source_total": source_total,
                    "prefilter_used": prefilter_used,
                    "prefilter_count": prefilter_count,
                    "skipped_by_prefilter": max(0, source_total - prefilter_count),
                    "filtered_out": info.get("filtered_out"),
                    "min_score": min_score,
                    "algo_version": ALGO_VERSION,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        # --- Artifact JSON (CANÓNICO) ---
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        json_art = write_run_artifact(
            run=run,
            filename=f"close_variants_{project.id}_{str(run.id)[:8]}.json",
            artifact_type=RunArtifact.ArtifactType.JSON,
            content_bytes=json_bytes,
        )

        # --- Artifact CSV (best-effort: si falla, NO falla el run) ---
        csv_art = None
        csv_error = ""
        csv_trace = ""

        try:
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["keyword", "avg_monthly_searches", "cpc_micros", "competition_level", "source", "score"])
            for it in items:
                w.writerow([
                    it.get("keyword"),
                    it.get("avg_monthly_searches"),
                    it.get("cpc_micros"),
                    it.get("competition_level"),
                    it.get("source"),
                    it.get("score"),
                ])

            csv_bytes = buf.getvalue().encode("utf-8")
            csv_art = write_run_artifact(
                run=run,
                filename=f"close_variants_{project.id}_{str(run.id)[:8]}.csv",
                artifact_type=RunArtifact.ArtifactType.CSV,
                content_bytes=csv_bytes,
            )
        except Exception as e:
            mark_failed(
                run,
                "Error generando close variants",
                {
                    "error": str(e),
                    "trace": traceback.format_exc()[:4000],
                },
            )
            return run


        # --- Success ---
        mark_success(
            run,
            outputs={
                "ok": True,
                "count": len(items),
                "source_total": source_total,
                "filtered_out": info.get("filtered_out"),
                "seed": seed,
                "source_run_id": str(source_run.id),
                "source_kind": source_run.kind,
                "algo_version": ALGO_VERSION,
                "min_score": min_score,
                "prefilter_prefixes": prefixes,
                "prefilter_used": prefilter_used,
                "prefilter_count": prefilter_count,
                "evaluated_count": prefilter_count,
                "skipped_by_prefilter": max(0, source_total - prefilter_count),

                # IDs de artifacts (oro para UI)
                "artifact_json_id": str(json_art.id),
                "artifact_csv_id": str(csv_art.id) if csv_art else "",

                # Si falló el CSV, lo dejamos trazable
                "csv_error": csv_error,
                "csv_trace": csv_trace,
            },
        )
        return run




        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["keyword", "avg_monthly_searches", "cpc_micros", "competition_level", "source", "score"])
        for it in items:
            w.writerow([it.get("keyword"), it.get("avg_monthly_searches"), it.get("cpc_micros"), it.get("competition_level"), it.get("source"), it.get("score")])
        csv_art = write_run_artifact(
            run=run,
            filename=f"close_variants_{project.id}_{str(run.id)[:8]}.csv",
            artifact_type=RunArtifact.ArtifactType.CSV,
            content_bytes=csv_bytes,
        )


        mark_success(
            run,
            outputs={
                "ok": True,
                "count": len(items),
                "source_total": source_total,
                "filtered_out": info.get("filtered_out"),
                "seed": seed,
                "source_run_id": str(source_run.id),
                "source_kind": source_run.kind,
                "algo_version": ALGO_VERSION,
                "min_score": min_score,
                "prefilter_prefixes": prefixes,
                "prefilter_used": prefilter_used,
                "prefilter_count": prefilter_count,
                "evaluated_count": prefilter_count,
                "skipped_by_prefilter": max(0, source_total - prefilter_count),
                "seed_tokens": (info.get("seed_tokens") or [])[:10],
                "seed_prefixes": (info.get("seed_prefixes") or [])[:10],
                "artifact_json_id": str(json_art.id),
                "artifact_csv_id": str(csv_art.id),

            },
        )
        return run

    except Exception as e:
        mark_failed(run, "Error generando close variants", {"error": str(e)})
        return run
