from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from integrations.serp.types import SerpRequest
from core.services.cache_keys import serp_cache_key
from integrations.serp.router import fetch_serp

from serp.models import SerpRun
from clients.models import Client
from projects.models import Project


class SerpRouterCacheTests(TestCase):
    def test_router_returns_cached_run(self):
        # 1) Crear datos mínimos requeridos por tu modelo
        client = Client.objects.create(name="Test Client")
        project = Project.objects.create(
            client=client,
            name="Test Project",
            domain="example.com",
        )

        # 2) Request
        req = SerpRequest(
            query="test",
            country_code="us",
            language_code="en",
            device="desktop",
            num_results=10,
        )

        # 3) Cache key coherente con el provider del router (si router usa serpapi)
        cache_key = serp_cache_key(req, "serpapi")

        # 4) Crear SerpRun cached (ajusta raw vs raw_json según tu modelo: aquí es raw)
        SerpRun.objects.create(
            project=project,
            provider="serpapi",
            run_type="rank_tracking",
            status="done",
            cache_key=cache_key,
            cache_expires_at=timezone.now() + timedelta(hours=1),
            raw={
                "organic_results": [
                    {"title": "X", "link": "https://example.com", "snippet": "S", "displayed_link": "example.com"}
                ]
            },
            response_status=200,
            cost_units=0,
        )

        # 5) Ejecutar router y validar cache hit
        parsed, run, from_cache = fetch_serp(project, req)



        self.assertTrue(from_cache)
        self.assertEqual(run.cache_key, cache_key)
        self.assertEqual(parsed.provider, "serpapi")
        self.assertGreaterEqual(len(parsed.results), 1)
        self.assertEqual(parsed.results[0].domain, "example.com")
