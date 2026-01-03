from django.test import TestCase
from django.urls import reverse

from clients.models import Client
from projects.models import Project


class KeywordPlannerSmokeTests(TestCase):
    def test_keyword_planner_get_renders(self):
        client = Client.objects.create(name="Acme")
        project = Project.objects.create(client=client, name="Test Project", domain="example.com")
        url = reverse("keyword_planner", kwargs={"project_id": project.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
