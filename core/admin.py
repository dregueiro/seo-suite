from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.models import Run, RunArtifact, ProviderResponse


@admin.register(ProviderResponse)
class ProviderResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "provider", "endpoint", "http_status", "received_at")
    search_fields = ("provider", "endpoint", "run__id")
    readonly_fields = ("received_at",)


class ProviderResponseInline(admin.TabularInline):
    model = ProviderResponse
    extra = 0
    fields = ("provider", "endpoint", "http_status", "received_at")
    readonly_fields = ("provider", "endpoint", "http_status", "received_at")


@admin.register(RunArtifact)
class RunArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "name", "artifact_type", "size_bytes", "created_at", "download")
    readonly_fields = ("download",)

    @admin.display(description="Download")
    def download(self, obj: RunArtifact):
        url = reverse("core_artifact_download", args=[obj.id])
        return format_html('<a href="{}">Download</a>', url)


class RunArtifactInline(admin.TabularInline):
    model = RunArtifact
    extra = 0
    fields = ("name", "artifact_type", "size_bytes", "created_at", "download")
    readonly_fields = ("created_at", "download")

    @admin.display(description="Download")
    def download(self, obj: RunArtifact):
        url = reverse("core_artifact_download", args=[obj.id])
        return format_html('<a href="{}">Download</a>', url)


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "kind", "status", "cost_micros", "created_at", "finished_at")
    inlines = [ProviderResponseInline, RunArtifactInline]
