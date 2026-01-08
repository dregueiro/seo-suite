import csv
import hashlib
import io
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from core.models import Run, RunArtifact
from core.services.runs import (
    RunSpec,
    attach_provider_response,
    create_run,
    get_cached_success_run,
    mark_failed,
    mark_running,
    mark_success,
)
from projects.models import Project
from keyword_research.models import KeywordMetric


# -------------------------
# Helpers
# -------------------------
def _normalize_header(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _safe_decode(data: bytes) -> str:
    """
    Keyword Planner suele exportar en UTF-16 (Windows) + 2 líneas de título/rango.
    Probamos varios encodings.
    """
    for enc in ("utf-16", "utf-16-le", "utf-16-be", "utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    # Quita NULs típicos de utf-16 mal decodificado / mezclas raras
    return (text or "").replace("\x00", "")


def _find_header_start(lines: List[str]) -> int:
    """
    Busca la línea real de header (no el título "Keyword Stats ..." ni el rango de fechas).
    Condición: contiene "Keyword" y alguna otra columna típica.
    """
    for i, line in enumerate(lines):
        l = line.strip()
        if not l:
            continue
        if "Keyword" in l and ("Avg." in l or "monthly" in l or "Competition" in l or "Currency" in l):
            return i
    return 0


def _detect_delimiter(header_line: str) -> str:
    # Keyword Planner "Keyword Stats" normalmente es TSV (tab)
    if header_line.count("\t") >= 2:
        return "\t"
    # a veces exporta CSV con ; en configuraciones regionales
    if header_line.count(";") > header_line.count(","):
        return ";"
    return ","


def _parse_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    s = s.replace("\u00a0", " ").replace(",", "").replace(" ", "")
    try:
        return int(float(s))
    except Exception:
        return None


def _parse_money_to_micros(val: Any) -> Optional[int]:
    """
    Convierte "$1.23" o "1,23" a micros.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    s = s.replace("\u00a0", " ")
    s = re.sub(r"[^0-9,\.\-]", "", s)
    if not s:
        return None

    if "," in s and "." not in s:
        s = s.replace(",", ".")
    else:
        if "," in s and "." in s:
            s = s.replace(",", "")

    try:
        f = float(s)
        return int(round(f * 1_000_000))
    except Exception:
        return None


def _map_competition(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip().lower()
    if not s:
        return ""
    if s in ("low", "baja", "bajo"):
        return "LOW"
    if s in ("medium", "media", "medio"):
        return "MEDIUM"
    if s in ("high", "alta", "alto"):
        return "HIGH"
    # a veces viene "0.12" (index)
    try:
        f = float(s)
        if f < 0.34:
            return "LOW"
        if f < 0.67:
            return "MEDIUM"
        return "HIGH"
    except Exception:
        return str(val)[:20].upper()


def _find_col(headers: List[str], candidates: Iterable[str]) -> Optional[str]:
    hs = {_normalize_header(h): h for h in headers}
    for c in candidates:
        key = _normalize_header(c)
        if key in hs:
            return hs[key]
    return None


def _write_artifact(run: Run, name: str, content: bytes) -> RunArtifact:
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir is None:
        base_dir = os.getcwd()

    artifacts_root = os.path.join(str(base_dir), "artifacts", "runs", str(run.id))
    os.makedirs(artifacts_root, exist_ok=True)

    storage_path = os.path.join(artifacts_root, name)
    with open(storage_path, "wb") as f:
        f.write(content)

    sha = _sha256_bytes(content)
    size = len(content)

    return RunArtifact.objects.create(
        run=run,
        name=name,
        artifact_type=RunArtifact.ArtifactType.CSV,
        storage_path=storage_path,
        sha256=sha,
        size_bytes=size,
    )


def _json_text(obj: Any) -> str:
    try:
        import json
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)[:200000]
    except Exception:
        return str(obj)[:200000]


def import_keyword_planner_csv(
    project: Project,
    csv_bytes: bytes,
    *,
    keyword: str = "",
    seed: str = "",
    filename: str = "keyword_planner.csv",
    use_cache: bool = True,
) -> Run:
    provider = Run.Provider.ADS
    kind = "keyword_research.ads.keyword_planner_csv_import"

    file_sha = _sha256_bytes(csv_bytes)
    inputs: Dict[str, Any] = {
        "project_id": project.id,
        "ads_customer_id": project.ads_customer_id,
        "keyword": (keyword or "").strip(),
        "seed": (seed or "").strip(),
        "filename": filename,
        "file_sha256": file_sha,
        "country_code": project.country_code,
        "language_code": project.language_code,
    }

    if use_cache:
        cached = get_cached_success_run(provider=provider, kind=kind, inputs=inputs, max_age_days=365)
        if cached:
            return cached

    ct = ContentType.objects.get_for_model(Project)
    run = create_run(
        RunSpec(
            provider=provider,
            kind=kind,
            inputs=inputs,
            entity_content_type=ct,
            entity_object_id=project.id,
        )
    )
    mark_running(run)

    try:
        artifact = _write_artifact(run, filename, csv_bytes)

        raw_text = _clean_text(_safe_decode(csv_bytes))
        lines = raw_text.splitlines()
        start = _find_header_start(lines)

        # Re-arma texto desde el header real
        useful_lines = [ln for ln in lines[start:] if ln.strip() != ""]
        if not useful_lines:
            raise RuntimeError("CSV vacío o sin contenido usable.")

        header_line = useful_lines[0]
        delimiter = _detect_delimiter(header_line)

        text = "\n".join(useful_lines)
        f = io.StringIO(text)

        reader = csv.DictReader(f, delimiter=delimiter)
        headers = reader.fieldnames or []

        # Columnas típicas del export "Keyword Stats"
        col_kw = _find_col(headers, ["Keyword", "Keyword text", "Palabra clave", "Palabras clave"])

        col_avg = _find_col(
            headers,
            [
                "Avg. monthly searches",
                "Average monthly searches",
                "Promedio de búsquedas mensuales",
                "Promedio de busquedas mensuales",
            ],
        )

        col_comp = _find_col(
            headers,
            [
                "Competition",
                "Competencia",
                "Competition (indexed value)",
                "Competencia (valor indexado)",
            ],
        )

        col_cpc_low = _find_col(
            headers,
            [
                "Top of page bid (low range)",
                "Top of page bid low range",
                "Oferta de parte superior de la página (rango bajo)",
                "Oferta de la parte superior de la página (rango bajo)",
            ],
        )
        col_cpc_high = _find_col(
            headers,
            [
                "Top of page bid (high range)",
                "Top of page bid high range",
                "Oferta de parte superior de la página (rango alto)",
                "Oferta de la parte superior de la página (rango alto)",
            ],
        )

        if not col_kw:
            raise RuntimeError(f"No encuentro columna de keyword. Headers detectados: {headers}")

        rows: List[KeywordMetric] = []
        seen = set()
        dup_in_file = 0

        now = timezone.now()
        locale = f"{project.country_code}-{project.language_code}"
        geo = f"country:{project.country_code}"

        parsed_rows = 0
        for r in reader:
            parsed_rows += 1
            kw = (r.get(col_kw) or "").strip()
            if not kw:
                continue

            key = (kw.casefold(), locale)
            if key in seen:
                dup_in_file += 1
                continue
            seen.add(key)

            avg = _parse_int(r.get(col_avg)) if col_avg else None
            comp = _map_competition(r.get(col_comp)) if col_comp else ""

            cpc = None
            if col_cpc_low:
                cpc = _parse_money_to_micros(r.get(col_cpc_low))
            if cpc is None and col_cpc_high:
                cpc = _parse_money_to_micros(r.get(col_cpc_high))

            rows.append(
                KeywordMetric(
                    project=project,
                    run=run,
                    keyword=kw,
                    locale=locale,
                    language=project.language_code,
                    geo=geo,
                    avg_monthly_searches=avg,
                    cpc_micros=cpc,
                    competition_level=comp,
                    source="ads",
                    source_confidence=0.85,
                    retrieved_at=now,
                )
            )


        created = 0
        attempted = len(rows)
        if rows:
            KeywordMetric.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)
            # Como el Run es nuevo, created = attempted - dup_in_file
            created = max(0, attempted - dup_in_file)


        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="google_ads.keyword_planner_csv_import",
            http_status=200,
            request_body=_json_text(inputs),
            response_body=_json_text(
                {
                    "artifact_id": artifact.id,
                    "artifact_path": artifact.storage_path,
                    "headers": headers,
                    "delimiter": delimiter,
                    "header_start_line": start,
                    "parsed_rows": parsed_rows,
                    "created_metrics": created,
                    "attempted_metrics": attempted,
                    "duplicates_in_file": dup_in_file,
                }
            ),
        )

        mark_success(run, outputs={"ok": True, "created_metrics": created, "parsed_rows": parsed_rows}, cost_micros=0)
        return run

    except Exception as e:
        attach_provider_response(
            run=run,
            provider=provider,
            endpoint="google_ads.keyword_planner_csv_import",
            http_status=None,
            response_body=_json_text({"error": str(e)}),
        )
        mark_failed(run, "Error import_keyword_planner_csv", {"error": str(e)})
        return run
