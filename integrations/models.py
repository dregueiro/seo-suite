from django.db import models
from django.utils import timezone

from projects.models import Project
from core.models import Run


class IntegrationStatus(models.Model):
    class Provider(models.TextChoices):
        GSC = "gsc", "Google Search Console"
        GA4 = "ga4", "Google Analytics 4"
        ADS = "ads", "Google Ads"

    class Status(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"

    # ✅ NUEVO: modo Ads (direct-first)
    class AdsMode(models.TextChoices):
        DIRECT = "direct", "Direct account"
        MANAGER = "manager", "Manager (MCC)"

    project = models.ForeignKey(Project, related_name="integration_statuses", on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=Provider.choices)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNKNOWN)
    message = models.CharField(max_length=500, blank=True, default="")

    last_run = models.ForeignKey(Run, null=True, blank=True, on_delete=models.SET_NULL)
    checked_at = models.DateTimeField(null=True, blank=True)

    # ===== Ads specific (opcional, no rompe otros providers) =====
    ads_mode = models.CharField(
        max_length=16,
        choices=AdsMode.choices,
        default=AdsMode.DIRECT,
        help_text="Ads access mode. DIRECT uses project.ads_customer_id. MANAGER uses login_customer_id (MCC).",
    )
    login_customer_id = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Manager (MCC) customer id, required if ads_mode=manager.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("project", "provider")]
        indexes = [models.Index(fields=["project", "provider", "status"])]

    def mark(self, status: str, message: str = "", run: Run | None = None):
        self.status = status
        self.message = message or ""
        self.last_run = run
        self.checked_at = timezone.now()
        self.save(update_fields=["status", "message", "last_run", "checked_at", "updated_at"])
