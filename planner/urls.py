from django.urls import path

from planner.views.keyword_planner import keyword_planner_view

urlpatterns = [
    path("projects/<int:project_id>/keyword_planner/", keyword_planner_view, name="keyword_planner"),
]
