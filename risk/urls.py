from django.urls import path
from . import views

app_name = "risk"
urlpatterns = [
    path("score", views.score_view, name="score"),
]