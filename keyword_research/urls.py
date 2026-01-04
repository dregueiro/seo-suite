from django.urls import path
from keyword_research import views

urlpatterns = [
    path("projects/<int:project_id>/overview/fetch/", views.fetch_overview_ads, name="kw_fetch_overview_ads"),
    path("projects/<int:project_id>/overview/mock/", views.fetch_overview_mock, name="kw_fetch_overview_mock"),
    path("projects/<int:project_id>/magic/mock/", views.fetch_magic_mock, name="kw_fetch_magic_mock"),
    path("projects/<int:project_id>/magic/fetch/", views.fetch_magic_ads, name="kw_fetch_magic_ads"),

]
