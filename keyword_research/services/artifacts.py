# keyword_research/services/artifacts.py
import hashlib
from pathlib import Path

from django.conf import settings

from core.models import Run, RunArtifact


def write_run_artifact(*, run: Run, filename: str, artifact_type: str, content_bytes: bytes) -> RunArtifact:
    """
    Guarda artifact en disco + crea RunArtifact (trazable).
    artifact_type debe matchear choices (csv/pdf/json/text/other).
    """
    base_dir = Path(settings.BASE_DIR) / "artifacts" / str(run.id)
    base_dir.mkdir(parents=True, exist_ok=True)

    path = base_dir / filename
    path.write_bytes(content_bytes)

    sha = hashlib.sha256(content_bytes).hexdigest()

    return RunArtifact.objects.create(
        run=run,
        name=filename,
        artifact_type=artifact_type,
        storage_path=str(path),
        sha256=sha,
        size_bytes=len(content_bytes),
    )
