from django.urls import path

from serp.views.runs import serp_run_detail, serp_runs
from serp.views.actions import run_serp_mock, run_serp_serpapi
from serp.views.rankings import rankings

urlpatterns = [
    path("serp/runs/", serp_runs, name="serp_runs"),
    path("serp/runs/<int:run_id>/", serp_run_detail, name="serp_run_detail"),
    path("serp/run/mock/<int:project_id>/", run_serp_mock, name="run_serp_mock"),
    path("serp/run/serpapi/<int:project_id>/", run_serp_serpapi, name="run_serp_serpapi"),
    path("rankings/", rankings, name="rankings"),
]
