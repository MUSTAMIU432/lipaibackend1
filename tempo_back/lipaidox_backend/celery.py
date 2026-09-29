"""
Celery application for the Lipaidox backend.

Workers run as their own processes, never inside Django:

    celery -A lipaidox_backend worker --loglevel=info
    celery -A lipaidox_backend beat --loglevel=info

Configuration comes from the ``CELERY_*`` names in ``settings.py``. Without
``CELERY_BROKER_URL`` tasks run eagerly (inline), so nothing needs a worker.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lipaidox_backend.settings")

app = Celery("lipaidox_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
# Finds `tasks.py` in every INSTALLED_APPS module (lipaidox/tasks.py,
# lipaidox/notifications/tasks.py, lipaidox/credits/tasks.py, ...).
app.autodiscover_tasks()
