from django.db import models
from django.utils import timezone

from core.models import Run
from projects.models import Project


class KeywordMetric(models.Model):
    """
    Keyword Metrics Contract (canónico):
      keyword, locale, language, geo,
      avg_monthly_searches, cpc_micros, competition_level,
      source, source_confidence, retrieved_at, run_id
    """

    project = models.ForeignKey(Project, related_name="keyword_metrics", on_delete=models.CASCADE)
    run = models.ForeignKey(Run, related_name="keyword_metrics", on_delete=models.CASCADE)

    keyword = models.CharField(max_length=255)
    locale = models.CharField(max_length=20, help_text="Ej: US-en")
    language = models.CharField(max_length=10, help_text="Ej: en")
    geo = models.CharField(max_length=255, help_text="Geo target (ej: country:US)")

    avg_monthly_searches = models.IntegerField(null=True, blank=True)

    # CPC en micros (Google Ads usa micros)
    cpc_micros = models.BigIntegerField(null=True, blank=True)

    competition_level = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="LOW/MEDIUM/HIGH/UNSPECIFIED (según provider)",
    )

    source = models.CharField(max_length=30, default="ads")
    source_confidence = models.FloatField(default=0.9)

    retrieved_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "keyword"]),
            models.Index(fields=["run", "keyword"]),
            models.Index(fields=["locale", "language"]),
        ]
        constraints = [
            # ✅ Dedupe fuerte dentro de un Run
            models.UniqueConstraint(
                fields=["run", "keyword", "locale"],
                name="uniq_kwmetric_run_keyword_locale",
            )
        ]

    def __str__(self) -> str:
        return f"{self.keyword} ({self.locale})"
