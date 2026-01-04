from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def health(_request):
    return JsonResponse({"ok": True})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("seo/", include("seo.urls")),
    path("kw/", include("keyword_research.urls")),
]
