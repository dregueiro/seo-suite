from django.test import TestCase

from serp.services.serpapi_provider import SerpApiProvider
from integrations.serp.types import SerpParsed, SerpResultItem


class SerpApiContractTests(TestCase):
    def test_serpapi_parse_raw_returns_contract(self):
        raw = {
            "organic_results": [
                {
                    "title": "Example",
                    "link": "https://example.com/a",
                    "snippet": "hello",
                    "displayed_link": "example.com",
                }
            ]
        }

        parsed = SerpApiProvider.parse_raw(raw)

        self.assertIsInstance(parsed, SerpParsed)
        self.assertEqual(parsed.provider, "serpapi")
        self.assertGreaterEqual(len(parsed.results), 1)

        r0 = parsed.results[0]
        self.assertIsInstance(r0, SerpResultItem)
        self.assertEqual(r0.domain, "example.com")
        self.assertTrue(r0.url.startswith("https://"))
