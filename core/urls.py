from django.urls import path

from core.views.home import home

urlpatterns = [
    path("", home, name="home"),
]
