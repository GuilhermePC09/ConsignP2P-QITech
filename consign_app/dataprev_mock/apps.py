# consign_app/core_db/apps.py
from django.apps import AppConfig

class DataprevAPIMockConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consign_app.dataprev_mock"
    label = "dataprev_mock"
