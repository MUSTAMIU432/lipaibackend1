from django.apps import AppConfig

class LipaidoxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lipaidox"

    def ready(self):
        from lipaidox.cache import register_catalog_invalidation

        register_catalog_invalidation()
