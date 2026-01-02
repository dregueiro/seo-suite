from django.db import models
from django.utils import timezone

class SerpKeywordSnapshot(models.Model):
    serp_run = models.ForeignKey("core.SerpRun", on_delete=models.CASCADE, related_name="snapshots")
    keyword = models.ForeignKey("core.Keyword", on_delete=models.CASCADE, related_name="snapshots")

    tracked_domain = models.CharField(max_length=255)  # dominio del proyecto normalizado
    tracked_position = models.PositiveIntegerField(null=True, blank=True)  # la mejor posición de tu dominio o None

    top_domain = models.CharField(max_length=255, blank=True, default="")
    top_position = models.PositiveIntegerField(null=True, blank=True)  # mejor posición en general
    top_url = models.URLField(max_length=600, blank=True, default="")
    top3_domains = models.JSONField(default=list, blank=True)
    top3_urls = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["serp_run", "keyword"], name="uniq_snapshot_per_run_keyword"),
        ]
        indexes = [
            models.Index(fields=["serp_run", "keyword"]),
            models.Index(fields=["tracked_domain"]),
        ]
        ordering = ["keyword_id"]

    def __str__(self) -> str:
        return f"{self.keyword.keyword} | {self.tracked_domain} | {self.tracked_position}"

class SerpRun(models.Model):
    class Provider(models.TextChoices):
        MOCK = "mock", "Mock"
        SERPAPI = "serpapi", "SerpAPI"
        DATAFORSEO = "dataforseo", "DataForSEO"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    raw = models.JSONField(null=True, blank=True)

    project = models.ForeignKey("core.Project", on_delete=models.CASCADE, related_name="serp_runs")

    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.MOCK)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)

    country = models.ForeignKey("core.Country", on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey("core.Language", on_delete=models.SET_NULL, null=True, blank=True)
    city = models.CharField(max_length=120, blank=True, default="")
    device = models.CharField(max_length=10, blank=True, default="")

    top_n = models.PositiveIntegerField(default=10)
    total_keywords = models.PositiveIntegerField(default=0)
    total_results = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SERP Run {self.id} | {self.project.name} | {self.provider} | {self.status}"


class SerpResult(models.Model):
    class ResultType(models.TextChoices):
        ORGANIC = "organic", "Organic"
        AD = "ad", "Ad"
        FEATURE = "feature", "Feature"

    serp_run = models.ForeignKey(SerpRun, on_delete=models.CASCADE, related_name="results")
    keyword = models.ForeignKey("core.Keyword", on_delete=models.CASCADE, related_name="serp_results")

    position = models.PositiveIntegerField()
    result_type = models.CharField(max_length=10, choices=ResultType.choices, default=ResultType.ORGANIC)

    title = models.CharField(max_length=512, blank=True, default="")
    url = models.URLField(max_length=600, blank=True, default="")
    domain = models.CharField(max_length=255, blank=True, default="")
    snippet = models.TextField(blank=True, default="")

    raw = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["serp_run", "keyword", "position", "result_type"],
                name="uniq_serpresult_position",
            ),
        ]
        indexes = [
            models.Index(fields=["serp_run", "keyword"]),
            models.Index(fields=["domain"]),
        ]
        ordering = ["keyword_id", "position"]

    def __str__(self) -> str:
        return f"{self.keyword.keyword} #{self.position} {self.domain}"



class Country(models.Model):
    code = models.CharField(max_length=2, unique=True)  # ISO-2
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Language(models.Model):
    code = models.CharField(max_length=10, unique=True)  # en, es, pt-BR
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Client(models.Model):
    name = models.CharField(max_length=120, unique=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Project(models.Model):
    class Device(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        MOBILE = "mobile", "Mobile"

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="projects")
    name = models.CharField(max_length=160)
    domain = models.CharField(max_length=255)  # ejemplo: voicesenglish.com
    is_active = models.BooleanField(default=True)

    city = models.CharField(max_length=120, blank=True, default="")
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True)
    device = models.CharField(max_length=10, choices=Device.choices, default=Device.DESKTOP)

    gsc_site_url = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Search Console property. Ejemplo: sc-domain:example.com o https://example.com/",
    )

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["client", "domain"], name="uniq_client_domain"),
        ]
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["is_active"]),
        ]
        ordering = ["client__name", "name"]

    def __str__(self) -> str:
        return f"{self.client.name} | {self.name}"


class Keyword(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="keywords")
    keyword = models.CharField(max_length=255)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True)

    city = models.CharField(max_length=120, blank=True, default="")
    device = models.CharField(max_length=10, blank=True, default="")

    target_url = models.URLField(blank=True, default="")
    intent = models.CharField(max_length=40, blank=True, default="")  # informativa, comercial, etc
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "keyword", "country", "city", "language", "device"],
                name="uniq_keyword_scope",
            ),

        ]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["keyword"]),
        ]
        ordering = ["project__client__name", "project__name", "keyword"]

    def __str__(self) -> str:
        return f"{self.project.name} | {self.keyword}"

