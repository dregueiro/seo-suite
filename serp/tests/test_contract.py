from django.test import TestCase

from serp.services.dataforseo_provider import DataForSEOProvider
from integrations.serp.types import SerpParsed, SerpResultItem


class SerpContractTests(TestCase):
    def test_dataforseo_parse_top10_returns_contract(self):
        # Raw mínimo estilo DataForSEO task_get
        raw = {
            "tasks": [
                {
                    "status_code": 20000,
                    "result": [
                        {
                            "items": [
                                {
                                    "type": "organic",
                                    "rank_group": 1,
                                    "title": "Example Title",
                                    "url": "https://example.com/page",
                                    "description": "Example snippet",
                                    "domain": "example.com",
                                },
                                {
                                    "type": "people_also_ask",
                                    "items": [],
                                },
                            ]
                        }
                    ],
                }
            ]
        }

        provider = DataForSEOProvider()
        parsed = provider.parse_top10(raw)

        self.assertIsInstance(parsed, SerpParsed)
        self.assertEqual(parsed.provider, "dataforseo")
        self.assertTrue(isinstance(parsed.results, list))
        self.assertGreaterEqual(len(parsed.results), 1)

        r0 = parsed.results[0]
        self.assertIsInstance(r0, SerpResultItem)
        self.assertEqual(r0.position, 1)
        self.assertEqual(r0.domain, "example.com")
        self.assertTrue(r0.url.startswith("https://"))
