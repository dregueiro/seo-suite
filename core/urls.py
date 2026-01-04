from django.urls import path
from core import views

urlpatterns = [
    path("artifacts/<int:artifact_id>/download/", views.artifact_download, name="core_artifact_download"),
]
