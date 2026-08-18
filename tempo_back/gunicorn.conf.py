# Gunicorn configuration — auto-loaded when gunicorn starts from this directory
# (tempo_back) without an explicit `-c`.
#
# Why this exists: gunicorn's default worker timeout is 30 seconds. A media
# upload (a video over mobile data) routinely takes longer than that to stream
# in, so the arbiter kills the worker mid-request and the client sees a dropped
# connection — "Upload failed: could not reach the server." Large uploads need a
# worker timeout that fits the transfer, not the default request-handling one.
import os

# Time a worker may spend on a single request (seconds). Uploads dominate this.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "300"))

# A graceful shutdown window matching the timeout so in-flight uploads aren't cut
# during a deploy/restart.
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "300"))

# Keep idle connections open a little longer than a typical proxy keep-alive.
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "30"))

# Worker count — Render sets WEB_CONCURRENCY on most plans; default to 2.
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))

# `bind` is intentionally left to Render's start command ($PORT).
