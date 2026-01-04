from django.contrib import admin

# Register your models here.
from django.contrib import admin, messages
from projects.models import Project
from integrations.services.test_access import test_gsc_access, test_ga4_access, test_ads_access


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "client", "domain", "country_code", "language_code", "is_active", "created_at")
    list_filter = ("is_active", "country_code", "language_code")
    search_fields = ("name", "domain", "client__name")
    actions = ["action_test_gsc", "action_test_ga4", "action_test_ads"]

    @admin.action(description="Test access: GSC (crea Run + raw response)")
    def action_test_gsc(self, request, queryset):
        for project in queryset:
            run = test_gsc_access(project)
            if run.status == "success":
                self.message_user(request, f"[GSC] OK {project} run={run.id}", level=messages.SUCCESS)
            else:
                self.message_user(request, f"[GSC] FAIL {project} run={run.id}: {run.error_message}", level=messages.ERROR)

    @admin.action(description="Test access: GA4 (crea Run + raw response)")
    def action_test_ga4(self, request, queryset):
        for project in queryset:
            run = test_ga4_access(project)
            if run.status == "success":
                self.message_user(request, f"[GA4] OK {project} run={run.id}", level=messages.SUCCESS)
            else:
                self.message_user(request, f"[GA4] FAIL {project} run={run.id}: {run.error_message}", level=messages.ERROR)

    @admin.action(description="Test access: Ads (crea Run + raw response)")
    def action_test_ads(self, request, queryset):
        for project in queryset:
            run = test_ads_access(project)
            if run.status == "success":
                self.message_user(request, f"[ADS] OK {project} run={run.id}", level=messages.SUCCESS)
            else:
                self.message_user(request, f"[ADS] FAIL {project} run={run.id}: {run.error_message}", level=messages.ERROR)
