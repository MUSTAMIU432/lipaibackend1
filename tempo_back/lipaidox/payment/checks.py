"""Startup checks: never let a production server quietly run fake payments."""
from django.conf import settings
from django.core.checks import Warning as CheckWarning, register


@register()
def payment_gateway_is_live(app_configs, **kwargs):
    if settings.DEBUG:
        return []  # simulation is the intended default while developing
    issues = []
    if (getattr(settings, "PAYMENT_GATEWAY_DEFAULT", "simulated") or "simulated") != "nbc":
        issues.append(
            CheckWarning(
                "Payments are running in SIMULATION mode on a non-debug server.",
                hint="Set PAYMENT_GATEWAY_DEFAULT=nbc and NBC_API_KEY. Verify with "
                     "`manage.py check_payment_gateway` or GET /payments/health/.",
                id="payment.W001",
            )
        )
    elif not getattr(settings, "NBC_API_KEY", ""):
        issues.append(
            CheckWarning(
                "PAYMENT_GATEWAY_DEFAULT=nbc but NBC_API_KEY is empty — every payment will fail.",
                hint="Set NBC_API_KEY in the server environment.",
                id="payment.W002",
            )
        )
    return issues
