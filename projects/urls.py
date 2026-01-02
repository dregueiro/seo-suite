from django.urls import path

from projects.views.keywords import keyword_import, keyword_list

urlpatterns = [
    path("keywords/import/", keyword_import, name="keyword_import"),
    path("keywords/", keyword_list, name="keyword_list"),
]
