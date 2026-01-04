from django.contrib import admin
from integrations.models import IntegrationStatus


@admin.register(IntegrationStatus)
class IntegrationStatusAdmin(admin.ModelAdmin):
    list_display = ("project", "provider", "status", "message", "checked_at", "last_run")
    list_filter = ("provider", "status")
    search_fields = ("project__name", "project__domain", "message", "last_run__id")
