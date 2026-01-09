from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),

    path("seo/", include("seo.urls")),
    path("keyword-research/", include("keyword_research.urls")),
    path("core/", include("core.urls")),
]
