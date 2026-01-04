from django.urls import path
from keyword_research import views

urlpatterns = [
    path("projects/<int:project_id>/overview/fetch/", views.fetch_overview_ads, name="kw_fetch_overview_ads"),
]
