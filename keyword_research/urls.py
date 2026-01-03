from django.urls import path

from keyword_research.views.keyword_planner import keyword_planner_view

urlpatterns = [
    path("projects/<int:project_id>/keyword_planner/", keyword_planner_view, name="keyword_planner"),
]
