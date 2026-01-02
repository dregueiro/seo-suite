import hashlib
from urllib.parse import quote

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from core.models import Keyword, SerpRun, SerpResult, Project
from core.services.serpapi_provider import SerpApiProvider
from core.services.rank_tracking import build_snapshots_for_run


from core.models import SerpRun, SerpResult, SerpFeature
from core.services.rank_tracking import get_provider


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--submit", action="store_true")
        parser.add_argument("--poll", action="store_true")
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        submit = options["submit"]
        poll = options["poll"]
        limit = options["limit"]

        if not submit and not poll:
            submit = True
            poll = True

        if submit:
            self._submit(limit)

        if poll:
            self._poll(limit)

    def _submit(self, limit: int):
        runs = SerpRun.objects.filter(status="created").order_by("id")[:limit]
        for run in runs:
            try:
                provider = get_provider(run.provider)

                if run.provider == "dataforseo":
                    project = run.keyword.project
                    language_code = getattr(project, "language_code", "en")

                    location_code = getattr(run.keyword, "location_code", None)
                    if not location_code:
                        location_code = getattr(project, "location_code", None)
                    if not location_code:
                        location_code = 2840  # US default, luego lo hacemos bien con seed_geo

                    device = getattr(run.keyword, "device", "") or getattr(project, "default_device", "mobile")

                    task_id = provider.submit_task(
                        keyword=run.keyword.keyword,
                        language_code=language_code,
                        location_code=int(location_code),
                        device=device,
                        depth=10,
                    )
                    run.task_id = task_id
                    run.status = "submitted"
                    run.save(update_fields=["task_id", "status"])
                else:
                    data = provider.fetch_serp(run)  # tu serpapi_provider ya lo tendrá, si no, lo adaptamos
                    self._save_results(run, data)
                    run.status = "done"
                    run.completed_at = timezone.now()
                    run.save(update_fields=["status", "completed_at"])

            except Exception as e:
                run.status = "error"
                run.error = str(e)
                run.save(update_fields=["status", "error"])

    def _poll(self, limit: int):
        runs = SerpRun.objects.filter(provider="dataforseo", status="submitted").exclude(task_id="").order_by("id")[:limit]
        for run in runs:
            try:
                provider = get_provider("dataforseo")
                resp = provider.poll_task(run.task_id)
                run.raw = resp
                run.save(update_fields=["raw"])

                if not provider.is_ready(resp):
                    continue

                parsed = provider.parse_top10(resp)
                self._save_results_from_parsed(run, parsed)

                run.status = "done"
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "completed_at"])

            except Exception as e:
                run.status = "error"
                run.error = str(e)
                run.save(update_fields=["status", "error"])

    def _save_results_from_parsed(self, run, parsed):
        SerpResult.objects.filter(serp_run=run).delete()
        SerpFeature.objects.filter(serp_run=run).delete()

        for r in parsed.results:
            SerpResult.objects.create(
                serp_run=run,
                position=r["position"],
                title=r["title"],
                url=r["url"],
                domain=r["domain"],
                snippet=r["snippet"],
                extra_json=r["raw"],
            )

        for f in parsed.features:
            SerpFeature.objects.create(
                serp_run=run,
                feature_type=f["type"],
                payload_json=f["raw"],
            )



def _stable_int(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _mock_results(keyword_text: str, top_n: int):
    base = _stable_int(keyword_text)
    results = []
    for pos in range(1, top_n + 1):
        bucket = (base + pos) % 7 + 1
        domain = f"site{bucket}.com"
        slug = slugify(keyword_text)[:60] or "keyword"
        url = f"https://{domain}/{slug}/{pos}?q={quote(keyword_text)}"
        results.append(
            {
                "position": pos,
                "result_type": SerpResult.ResultType.ORGANIC,
                "title": f"{keyword_text.title()} | Result {pos}",
                "url": url,
                "domain": domain,
                "snippet": f"Mock snippet for {keyword_text}, position {pos}.",
                "raw": {"provider": "mock", "pos": pos, "seed": base},
            }
        )
    return results


class Command(BaseCommand):
    help = "Run a SERP collection for a project. Providers: mock, serpapi."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True)
        parser.add_argument("--provider", type=str, default="mock")
        parser.add_argument("--top", type=int, default=10)
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        project_id = options["project"]
        provider = (options["provider"] or "mock").strip().lower()
        top_n = int(options["top"])
        limit = int(options["limit"])

        project = Project.objects.select_related("country", "language").get(id=project_id)

        run = SerpRun.objects.create(
            project=project,
            provider=provider,
            status=SerpRun.Status.RUNNING,
            country=project.country,
            language=project.language,
            city=project.city,
            device=project.device,
            top_n=top_n,
            total_keywords=0,
            total_results=0,
            started_at=timezone.now(),
        )

        try:
            kw_qs = (
                Keyword.objects.filter(project=project, status=Keyword.Status.ACTIVE)
                .select_related("country", "language")
                .order_by("id")[:limit]
            )

            keyword_ids = list(kw_qs.values_list("id", flat=True))
            total_keywords = len(keyword_ids)

            total_results = 0

            provider_obj = None
            if provider == "serpapi":
                provider_obj = SerpApiProvider()

            bulk = []
            for kw in kw_qs:
                if provider == "mock":
                    rows = _mock_results(kw.keyword, top_n)

                elif provider == "serpapi":
                    country = kw.country or project.country
                    language = kw.language or project.language
                    city = (kw.city or project.city or "").strip()

                    gl = (country.code.lower() if country else None)
                    hl = (language.code.lower() if language else None)

                    location = None
                    if city and country:
                        location = f"{city}, {country.name}"
                    elif country:
                        location = country.name

                    device = (kw.device or project.device or "desktop").strip().lower()
                    if device not in ("desktop", "mobile", "tablet"):
                        device = "desktop"

                    results, raw_response = provider_obj.fetch(
                        q=kw.keyword,
                        location=location,
                        gl=gl,
                        hl=hl,
                        device=device,
                        num=top_n,
                    )

                    # Save the full SERP response on the run (last keyword wins for now; OK for MVP)
                    run.raw = raw_response
                    run.save(update_fields=["raw"])

                    # Build rows for DB insert
                    rows = []
                    for idx, r in enumerate(results[:top_n], start=1):
                        rows.append(
                            {
                                "position": int(r.get("position") or idx) or idx,
                                "result_type": SerpResult.ResultType.ORGANIC,
                                "title": r.get("title", "") or "",
                                "url": r.get("url", "") or "",
                                "domain": r.get("domain", "") or "",
                                "snippet": r.get("snippet", "") or "",
                                "raw": r.get("raw"),
                            }
                        )

                else:
                    raise ValueError("Provider not implemented. Use --provider mock or --provider serpapi.")

                for r in rows:
                    bulk.append(
                        SerpResult(
                            serp_run=run,
                            keyword=kw,
                            position=r["position"],
                            result_type=r["result_type"],
                            title=r["title"],
                            url=r["url"],
                            domain=r["domain"],
                            snippet=r["snippet"],
                            raw=r["raw"],
                        )
                    )
                total_results += len(rows)

            if bulk:
                SerpResult.objects.bulk_create(bulk, batch_size=200)

            # Create snapshots for ALL keywords attempted (even if SERP returned 0 results)
            snapshot_count = build_snapshots_for_run(run, keyword_ids)
            self.stdout.write(self.style.SUCCESS(f"Snapshots created: {snapshot_count}"))

            run.total_keywords = total_keywords
            run.total_results = total_results
            run.status = SerpRun.Status.DONE
            run.finished_at = timezone.now()
            run.save(update_fields=["total_keywords", "total_results", "status", "finished_at"])

            self.stdout.write(self.style.SUCCESS(f"SERP run done. Run ID: {run.id}. Results: {total_results}"))

        except Exception as e:
            run.status = SerpRun.Status.FAILED
            run.error_message = str(e)
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error_message", "finished_at"])
            raise
