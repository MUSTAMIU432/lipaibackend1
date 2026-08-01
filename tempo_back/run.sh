#!/usr/bin/env bash
#
# Start the Django dev server cleanly.
#   ./run.sh          → bind 0.0.0.0:8000 (reachable from Android / other devices)
#   ./run.sh 8001     → use a different port
#
# It ALWAYS frees the port first, so you never hit "That port is already in use".
# Stop the server with Ctrl-C as usual.

set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8000}"

# Kill anything currently bound to the port (stale/orphaned server, OOM leftovers, etc.)
if fuser -k "${PORT}/tcp" >/dev/null 2>&1; then
  echo "Freed port ${PORT} (killed a process that was still holding it)."
  sleep 1
fi

# Use the project's virtualenv python explicitly (works even if the venv isn't activated).
PY="./myenv/bin/python"
[ -x "$PY" ] || PY="python3"

echo "Starting Django on 0.0.0.0:${PORT} ..."
exec "$PY" manage.py runserver "0.0.0.0:${PORT}"
