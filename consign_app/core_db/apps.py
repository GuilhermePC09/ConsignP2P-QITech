# consign_app/core_db/apps.py
from django.apps import AppConfig

class CoreDbConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consign_app.core_db"
    label = "core_db"
