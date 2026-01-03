from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("projects.urls")),
    path("", include("serp.urls")),
    path("", include("keyword_research.urls")),
]
