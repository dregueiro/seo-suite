import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Run(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    class Provider(models.TextChoices):
        INTERNAL = "internal", "Internal"
        GSC = "gsc", "Google Search Console"
        GA4 = "ga4", "Google Analytics 4"
        ADS = "ads", "Google Ads"
        SERPAPI = "serpapi", "SerpAPI"
        DATAFORSEO = "dataforseo", "DataForSEO"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Trazabilidad: qué es y con qué proveedor
    kind = models.CharField(max_length=100)  # ej: "integrations.test_access.ads"
    provider = models.CharField(max_length=30, choices=Provider.choices, default=Provider.INTERNAL)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Inputs/outputs
    inputs = models.JSONField(default=dict, blank=True)
    outputs = models.JSONField(default=dict, blank=True)

    # Dedupe/caché
    input_hash = models.CharField(max_length=64, db_index=True)

    # Costos (micros para evitar floats: 1_000_000 micros = 1 unidad monetaria)
    cost_micros = models.BigIntegerField(default=0)

    # Errores
    error_message = models.TextField(blank=True, default="")
    error_details = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # Relación genérica a "dueño" (Project más adelante, u otros)
    entity_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    entity_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    entity = GenericForeignKey("entity_content_type", "entity_object_id")

    class Meta:
        indexes = [
            models.Index(fields=["provider", "kind", "input_hash"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind} [{self.provider}] {self.status} ({self.id})"


class ProviderResponse(models.Model):
    """
    Guardamos request/response crudos para auditoría y debug.
    """
    run = models.ForeignKey(Run, related_name="provider_responses", on_delete=models.CASCADE)

    provider = models.CharField(max_length=30, default=Run.Provider.INTERNAL)
    endpoint = models.CharField(max_length=255, blank=True, default="")

    http_status = models.IntegerField(null=True, blank=True)

    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.TextField(blank=True, default="")

    response_headers = models.JSONField(default=dict, blank=True)
    response_body = models.TextField(blank=True, default="")

    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.provider} {self.endpoint} ({self.http_status})"


class RunArtifact(models.Model):
    """
    Referencias a artefactos generados por un Run (CSV, PDF, JSON, etc).
    De momento guardamos ruta local/relativa. Más tarde lo movemos a storage si hace falta.
    """
    class ArtifactType(models.TextChoices):
        JSON = "json", "JSON"
        CSV = "csv", "CSV"
        PDF = "pdf", "PDF"
        TEXT = "text", "Text"
        OTHER = "other", "Other"

    run = models.ForeignKey(Run, related_name="artifacts", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    artifact_type = models.CharField(max_length=20, choices=ArtifactType.choices, default=ArtifactType.OTHER)

    storage_path = models.CharField(max_length=500, blank=True, default="")
    sha256 = models.CharField(max_length=64, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.artifact_type})"
