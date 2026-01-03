from django.test import TestCase

from keyword_research.services.keyword_metrics_provider import DataForSEOKeywordMetricsProvider


class MetricsProviderParseTests(TestCase):
    def test_parse_rows_minimal(self):
        p = DataForSEOKeywordMetricsProvider()
        raw = {
            "tasks": [
                {
                    "status_code": 20000,
                    "cost": 0.01,
                    "result": [
                        {"keyword": "nike shoes", "search_volume": 1000, "cpc": 0.5},
                        {"keyword": "   ", "search_volume": 10},
                    ],
                }
            ],
            "status_code": 20000,
        }
        rows = p.parse_rows(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].keyword, "nike shoes")
        self.assertEqual(rows[0].search_volume, 1000)
