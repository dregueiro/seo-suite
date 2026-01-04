from django.contrib import admin

# Register your models here.
from django.contrib import admin
from core.models import Run, ProviderResponse, RunArtifact


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "kind", "status", "cost_micros", "created_at", "finished_at")
    list_filter = ("provider", "status", "kind")
    search_fields = ("id", "kind", "input_hash")
    readonly_fields = ("created_at", "updated_at", "started_at", "finished_at", "input_hash")


@admin.register(ProviderResponse)
class ProviderResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "endpoint", "http_status", "received_at", "run")
    list_filter = ("provider",)
    search_fields = ("endpoint", "run__id")


@admin.register(RunArtifact)
class RunArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "artifact_type", "storage_path", "size_bytes", "created_at", "run")
    list_filter = ("artifact_type",)
    search_fields = ("name", "storage_path", "run__id")
