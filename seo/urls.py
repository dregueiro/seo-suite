from django.urls import path
from seo import views

urlpatterns = [
    path("", views.dashboard, name="seo_dashboard"),

    path("projects/<int:project_id>/setup/", views.project_setup, name="seo_project_setup"),

    path("projects/<int:project_id>/keywords/overview/", views.keyword_overview, name="seo_keyword_overview"),
    path("projects/<int:project_id>/keywords/overview/export.pdf", views.keyword_overview_export_pdf, name="seo_keyword_overview_export_pdf"),
    path("projects/<int:project_id>/keywords/overview/export.csv", views.keyword_overview_export_csv, name="seo_keyword_overview_export_csv"),

    path("projects/<int:project_id>/keywords/magic/", views.keyword_magic, name="seo_keyword_magic"),
    path("projects/<int:project_id>/keywords/magic/export.csv", views.keyword_magic_export_csv, name="seo_keyword_magic_export_csv"),
]
