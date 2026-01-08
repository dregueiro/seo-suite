from django.shortcuts import render

from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from core.models import RunArtifact


@staff_member_required
def download_run_artifact(request, artifact_id: int):
    art = RunArtifact.objects.filter(id=artifact_id).select_related("run").first()
    if not art:
        raise Http404("Artifact no encontrado")

    path = art.storage_path
    if not path or not os.path.exists(path):
        raise Http404("Archivo no encontrado en disco")

    return FileResponse(open(path, "rb"), as_attachment=True, filename=art.name)

def _artifact_mime(artifact_type: str) -> str:
    return {
        "json": "application/json",
        "csv": "text/csv",
        "pdf": "application/pdf",
        "text": "text/plain",
    }.get(artifact_type, "application/octet-stream")


@staff_member_required
def artifact_download(request, artifact_id: int):
    art = get_object_or_404(RunArtifact, id=artifact_id)

    base_dir = (Path(settings.BASE_DIR) / "artifacts").resolve(strict=False)
    file_path = Path(art.storage_path).resolve(strict=False)

    # Seguridad: el archivo debe estar dentro de BASE_DIR/artifacts
    if base_dir not in file_path.parents and file_path != base_dir:
        raise Http404("Artifact path not allowed")

    if not file_path.exists() or not file_path.is_file():
        raise Http404("Artifact file not found")

    resp = FileResponse(open(file_path, "rb"), content_type=_artifact_mime(art.artifact_type))
    resp["Content-Disposition"] = f'attachment; filename="{art.name}"'
    return resp
