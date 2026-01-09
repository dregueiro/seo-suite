from django.urls import path
from . import views
from . import views_integrations

app_name = "seo"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("projects/", views.projects_list, name="projects_list"),
    path("projects/<int:project_id>/setup/", views.project_setup, name="project_setup"),
    path("runs/", views.runs_list, name="runs_list"),
    path("runs/<uuid:run_id>/", views.run_detail, name="run_detail"),
    path("projects/<int:project_id>/keywords/overview/", views.keyword_overview, name="keyword_overview"),
    path("projects/<int:project_id>/keywords/magic/", views.keyword_magic, name="keyword_magic"),

    # ✅ frontend action equivalente al Admin Action
    path(
        "projects/<int:project_id>/integrations/test/<str:provider>/",
        views_integrations.test_access,
        name="test_access",
    ),
    path("projects/<int:project_id>/keywords/overview/export.pdf", views.keyword_overview_export_pdf, name="keyword_overview_export_pdf"),
    path("projects/<int:project_id>/keywords/overview/export.csv", views.keyword_overview_export_csv, name="keyword_overview_export_csv"),
    path("projects/<int:project_id>/keywords/magic/export.csv", views.keyword_magic_export_csv, name="keyword_magic_export_csv"),
    path("projects/<int:project_id>/keywords/metrics/", views.keyword_metrics, name="keyword_metrics"),

]
