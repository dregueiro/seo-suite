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

    project = models.ForeignKey(Project, related_name="integration_statuses", on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=Provider.choices)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNKNOWN)
    message = models.CharField(max_length=500, blank=True, default="")

    last_run = models.ForeignKey(Run, null=True, blank=True, on_delete=models.SET_NULL)
    checked_at = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("project", "provider")]
        indexes = [models.Index(fields=["project", "provider", "status"])]

    def mark(self, status: str, message: str = "", run: Run | None = None):
        self.status = status
        self.message = message or ""
        self.last_run = run
        self.checked_at = timezone.now()
