"""
Verify the payment gateway can take real money, without creating a charge.

    ./myenv/bin/python manage.py check_payment_gateway

Exits 0 when live, 1 when not — usable as a deploy gate. Run it on the server (e.g.
the Render shell) after setting the environment variables.
"""
from django.core.management.base import BaseCommand

from lipaidox.payment.health import gateway_health


def _mark(value):
    return "yes" if value is True else "NO" if value is False else "not checked"


class Command(BaseCommand):
    help = "Check the NBC payment gateway configuration and connectivity (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--no-probe", action="store_true", help="Skip the call to NBC; check configuration only.")

    def handle(self, *args, **options):
        h = gateway_health(probe=not options["no_probe"])
        self.stdout.write(f"Gateway in use       : {h['gateway']}")
        self.stdout.write(f"API key configured   : {_mark(h['keyConfigured'])}")
        self.stdout.write(f"NBC portal reachable : {_mark(h['reachable'])}")
        self.stdout.write(f"NBC accepts the key  : {_mark(h['authenticated'])}")
        self.stdout.write(f"Wallet currency      : {h['walletCurrency']}  →  settled in {h['settlementCurrency']}")
        self.stdout.write(f"Return URL set       : {_mark(h['redirectUrlConfigured'])}")
        for problem in h["problems"]:
            self.stdout.write(self.style.ERROR(f"  ✗ {problem}"))
        if h["live"]:
            self.stdout.write(self.style.SUCCESS("Payments are LIVE — real money can be taken."))
            return
        self.stdout.write(self.style.ERROR("Payments are NOT live."))
        raise SystemExit(1)
