# consign_app/core_db/apps.py
from django.apps import AppConfig

class OpenFinanceAPIMockConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consign_app.open_finance_mock"
    label = "open_finance_mock"
