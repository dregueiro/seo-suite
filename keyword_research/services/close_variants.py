# keyword_research/services/close_variants.py
import csv
import io
import json
import re
import unicodedata
from typing import Iterable, List, Dict, Any, Tuple
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


_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("&", " and ")
    return s


def _tokens(s: str) -> List[str]:
    return _WORD_RE.findall(_norm(s))


def _score(seed_tokens: List[str], kw_tokens: List[str], kw_text: str, seed_text: str) -> int:
    """
    Score simple (barato):
    +2 si contiene la seed completa como substring
    +1 si comparte >= 1 token
    +1 si comparte >= 2 tokens
    """
    if not kw_text or not kw_tokens:
        return 0

    score = 0
    if seed_text and seed_text in kw_text:
        score += 2

    inter = set(seed_tokens).intersection(set(kw_tokens))
    if len(inter) >= 1:
        score += 1
    if len(inter) >= 2:
        score += 1

    return score





_STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "at",
    "near", "me", "my", "your", "with", "without", "from", "by",
}

# Alias básicos (MVP) para casos típicos: photo/photography/photographer
_ALIASES = {
    "photographer": {"photographers", "photography", "photo", "photos", "photog"},
    "photographers": {"photographer", "photography", "photo", "photos", "photog"},
    "photography": {"photographer", "photographers", "photo", "photos", "photog"},
    "photo": {"photography", "photographer", "photographers", "photos", "photog"},
    "photos": {"photo", "photography", "photographer", "photographers", "photog"},
}


def _normalize_text(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    # deja letras/números/espacios
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokenize(s: str) -> List[str]:
    s = _normalize_text(s)
    if not s:
        return []
    toks = [t for t in s.split(" ") if t and t not in _STOPWORDS]
    return toks


def _expand_seed_tokens(seed_tokens: List[str]) -> List[str]:
    """
    Expande tokens del seed con aliases básicos. (MVP, no dependencias)
    """
    expanded = set(seed_tokens)
    for t in seed_tokens:
        for alt in _ALIASES.get(t, set()):
            expanded.add(alt)
    return list(expanded)


def _singularize(token: str) -> str:
    """
    Singularización súper barata (MVP). Evita meter dependencias tipo nltk.
    """
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def compute_close_variants(seed: str, qs: Iterable[Any], limit: int = 200) -> List[Dict[str, Any]]:
    """
    qs: iterable de KeywordMetric (o similar) con atributos:
      keyword, avg_monthly_searches, cpc_micros, competition_level, source
    Devuelve lista de dicts con score.
    """
    seed_norm = _normalize_text(seed)
    seed_tokens = _tokenize(seed)
    if not seed_tokens:
        return []

    # tokens base + aliases + singularizados
    expanded = _expand_seed_tokens(seed_tokens)
    expanded = list({t for t in expanded if t})
    expanded_sing = set(_singularize(t) for t in expanded)

    results: List[Dict[str, Any]] = []

    for m in qs:
        kw_raw = getattr(m, "keyword", "") or ""
        kw_norm = _normalize_text(kw_raw)
        if not kw_norm:
            continue

        # No incluir el seed exacto como “variant”
        if kw_norm == seed_norm:
            continue

        kw_tokens = _tokenize(kw_norm)
        if not kw_tokens:
            continue

        kw_sing = set(_singularize(t) for t in kw_tokens)

        # Match: al menos 1 token (o alias) del seed presente en la kw
        matched = expanded_sing.intersection(kw_sing)
        if not matched:
            continue

        # ---- score (MVP pero útil) ----
        # base por cantidad de matches
        score = 10 * len(matched)

        # bonus si contiene el token principal del seed (primer token)
        main_tok = _singularize(seed_tokens[0])
        if main_tok in kw_sing:
            score += 8

        # bonus por volumen (suave) y CPC (suave)
        vol = getattr(m, "avg_monthly_searches", None) or 0
        cpc = getattr(m, "cpc_micros", None) or 0
        # log-like barato sin math.log
        if vol >= 10000:
            score += 8
        elif vol >= 1000:
            score += 5
        elif vol >= 100:
            score += 2

        if cpc >= 5_000_000:      # $5+
            score += 4
        elif cpc >= 1_000_000:    # $1+
            score += 2

        results.append({
            "keyword": kw_raw,
            "avg_monthly_searches": getattr(m, "avg_monthly_searches", None),
            "cpc_micros": getattr(m, "cpc_micros", None),
            "competition_level": getattr(m, "competition_level", None),
            "source": getattr(m, "source", None),
            "score": score,
        })

    # Orden: score desc, luego volumen desc
    results.sort(
        key=lambda x: (
            x.get("score", 0),
            x.get("avg_monthly_searches") or 0,
        ),
        reverse=True
    )

    return results[: max(0, int(limit or 200))]


def build_close_variants_run(
    *,
    project: Project,
    seed: str,
    source_run: Run,
    limit: int = 200,
) -> Run:
    """
    Crea un Run interno (run-based) que toma KeywordMetric del source_run (CSV import)
    y genera close variants como artifact JSON+CSV. Sin migraciones.
    """
    provider = Run.Provider.INTERNAL if hasattr(Run.Provider, "INTERNAL") else Run.Provider.ADS
    kind = "keyword_research.close_variants"

    inputs = {
        "project_id": project.id,
        "seed": seed,
        "source_run_id": str(source_run.id),
        "limit": limit,
        "source_kind": source_run.kind,
    }

    run = create_run(RunSpec(provider=provider, kind=kind, inputs=inputs, entity=project))
    mark_running(run)

    try:
        qs = KeywordMetric.objects.filter(project=project, run=source_run).only(
            "keyword",
            "avg_monthly_searches",
            "cpc_micros",
            "competition_level",
            "source",
            "source_confidence",
            "retrieved_at",
        )

        items = compute_close_variants(seed, qs, limit=limit)

        payload = {
            "seed": seed,
            "project_id": project.id,
            "source_run_id": str(source_run.id),
            "source_kind": source_run.kind,
            "created_at": timezone.now().isoformat(timespec="seconds"),
            "count": len(items),
            "items": items,
        }

        # ProviderResponse (tangible y auditable)
        attach_provider_response(
            run=run,
            provider=run.provider,
            endpoint="internal.close_variants",
            http_status=200,
            request_body=json.dumps({"seed": seed, "source_run_id": str(source_run.id)}, ensure_ascii=False, indent=2),
            response_body=json.dumps({"count": len(items)}, ensure_ascii=False, indent=2),
        )

        # Artifact JSON
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        write_run_artifact(
            run=run,
            filename=f"close_variants_{project.id}_{str(run.id)[:8]}.json",
            artifact_type=RunArtifact.ArtifactType.JSON,
            content_bytes=json_bytes,
        )

        # Artifact CSV
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["keyword", "avg_monthly_searches", "cpc_micros", "competition_level", "source", "score"])
        for it in items:
            w.writerow(
                [
                    it.get("keyword"),
                    it.get("avg_monthly_searches"),
                    it.get("cpc_micros"),
                    it.get("competition_level"),
                    it.get("source"),
                    it.get("score"),
                ]
            )
        csv_bytes = buf.getvalue().encode("utf-8")
        write_run_artifact(
            run=run,
            filename=f"close_variants_{project.id}_{str(run.id)[:8]}.csv",
            artifact_type=RunArtifact.ArtifactType.CSV,
            content_bytes=csv_bytes,
        )

        mark_success(run, outputs={"ok": True, "count": len(items), "source_run_id": str(source_run.id)})
        return run

    except Exception as e:
        mark_failed(run, "Error generando close variants", {"error": str(e)})
        return run
