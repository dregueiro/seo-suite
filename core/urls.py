from django.urls import path

from core.views.home import home
from core.views.keywords import keyword_import, keyword_list
from core.views.serp import serp_runs, serp_run_detail
from core.views.serp_actions import run_serp_mock, run_serp_serpapi
from core.views.rankings import rankings


urlpatterns = [
    path("", home, name="home"),

    path("keywords/import/", keyword_import, name="keyword_import"),
    path("keywords/", keyword_list, name="keyword_list"),

    path("serp/runs/", serp_runs, name="serp_runs"),
    path("serp/runs/<int:run_id>/", serp_run_detail, name="serp_run_detail"),
    path("serp/run/mock/<int:project_id>/", run_serp_mock, name="run_serp_mock"),
    path("serp/run/serpapi/<int:project_id>/", run_serp_serpapi, name="run_serp_serpapi"),
    path("rankings/", rankings, name="rankings"),

]
