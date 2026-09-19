"""
Bill running live sessions and end the ones that shouldn't keep running.

Heartbeats from the creator's app do the normal billing. This is the safety net:
it bills sessions up to now, ends a stream whose credits ran out, and ends one
whose creator went quiet (billed only up to their last heartbeat).

    ./myenv/bin/python manage.py bill_live_sessions            # one pass (cron, every minute)
    ./myenv/bin/python manage.py bill_live_sessions --loop 10  # keep running, every 10 s
"""
import time

from django.core.management.base import BaseCommand

from lipaidox.credits import live_billing


class Command(BaseCommand):
    help = "Bill active live sessions; end exhausted or dropped ones."

    def add_arguments(self, parser):
        parser.add_argument("--loop", type=int, default=0, help="Repeat every N seconds instead of running once.")

    def handle(self, *args, **options):
        interval = options["loop"]
        while True:
            summary = live_billing.bill_active_sessions()
            self.stdout.write(f"billed={summary['billed']} exhausted={summary['ended_exhausted']} lost={summary['ended_lost']}")
            if not interval:
                return
            time.sleep(interval)
