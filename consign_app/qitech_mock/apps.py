# consign_app/core_db/apps.py
from django.apps import AppConfig

class QITechAPIMockConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consign_app.qitech_mock"
    label = "qitech_mock"
