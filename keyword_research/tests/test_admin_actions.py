from django.test import TestCase

from clients.models import Client
from projects.models import Project
from keyword_research.models import Keyword, KeywordIdea, KeywordIdeaRun
from keyword_research.services.admin_actions import add_ideas_to_tracked_keywords


class AdminActionsTests(TestCase):
    def test_add_ideas_to_tracked_keywords_dedupes(self):
        client = Client.objects.create(name="Acme")
        project = Project.objects.create(client=client, name="Test", domain="example.com")

        run = KeywordIdeaRun.objects.create(
            project=project,
            seed_keyword="nike",
            location_code=2840,
            language_code="en",
            provider="dataforseo",
            status="completed",
            cache_key="x",
        )

        i1 = KeywordIdea.objects.create(run=run, keyword="nike shoes", search_volume=100)
        i2 = KeywordIdea.objects.create(run=run, keyword="nike shoes", search_volume=100)  # conflict ignored by model constraint? (si aplica)

        res = add_ideas_to_tracked_keywords(ideas=[i1])
        self.assertEqual(res.created, 1)

        # correr de nuevo no debe duplicar
        res2 = add_ideas_to_tracked_keywords(ideas=[i1])
        self.assertEqual(res2.created, 0)
        self.assertEqual(Keyword.objects.filter(project=project, keyword="nike shoes").count(), 1)
