#!/usr/bin/env bash
#
# Start Celery for local development: one worker with the Beat scheduler
# embedded (-B), reading REDIS/CELERY settings from .env.
#   ./celery.sh
# Needs Redis running (systemctl --user status redis / redis-cli ping).
# Restart it after changing task code. In production run worker and beat as
# separate processes — see README.md → "Redis, caching and Celery".

set -euo pipefail
cd "$(dirname "$0")"

CELERY="./myenv/bin/celery"
[ -x "$CELERY" ] || CELERY="celery"

exec "$CELERY" -A lipaidox_backend worker -B --loglevel=info
