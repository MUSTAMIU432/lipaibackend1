from django.apps import AppConfig

class paymentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lipaidox.payment"
    label = "lipaidox_payment"

    def ready(self):
        from . import checks  # noqa: F401 — registers the payment startup checks
