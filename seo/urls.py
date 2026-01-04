from django.urls import path
from seo import views

urlpatterns = [
    path("projects/<int:project_id>/setup/", views.project_setup, name="seo_project_setup"),
    path("projects/<int:project_id>/keywords/overview/", views.keyword_overview, name="seo_keyword_overview"),
]
