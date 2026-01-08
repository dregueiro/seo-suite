from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.models import Run, RunArtifact, ProviderResponse

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.models import Run, RunArtifact


@admin.register(RunArtifact)
class RunArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "name", "artifact_type", "size_bytes", "created_at", "download")
    readonly_fields = ("download",)

    @admin.display(description="Download")
    def download(self, obj: RunArtifact):
        if not obj or not obj.pk:
            return "-"
        url = reverse("core_artifact_download", args=[obj.pk])
        return format_html('<a href="{}">Download</a>', url)


class RunArtifactInline(admin.TabularInline):
    model = RunArtifact
    extra = 0
    fields = ("name", "artifact_type", "size_bytes", "created_at", "download")
    readonly_fields = ("created_at", "download")

    @admin.display(description="Download")
    def download(self, obj: RunArtifact):
        # En inlines, Django puede renderizar formularios “vacíos” sin PK aún.
        if not obj or not obj.pk:
            return "-"
        url = reverse("core_artifact_download", args=[obj.pk])
        return format_html('<a href="{}">Download</a>', url)


@admin.action(description="Limpiar KeywordMetrics de los Runs seleccionados")
def action_delete_keyword_metrics(modeladmin, request, queryset):
    from keyword_research.models import KeywordMetric

    qs = KeywordMetric.objects.filter(run__in=queryset)
    count = qs.count()
    qs.delete()
    modeladmin.message_user(request, f"OK: borradas {count} KeywordMetric asociadas a los Runs seleccionados.")

@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "kind", "status", "cost_micros", "created_at", "finished_at")
    inlines = [RunArtifactInline]
    actions = [action_delete_keyword_metrics]




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

