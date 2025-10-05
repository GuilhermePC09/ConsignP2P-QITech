from django.urls import path
from risk.views import score_view

urlpatterns = [
    path("score", score_view, name="score"),
]
