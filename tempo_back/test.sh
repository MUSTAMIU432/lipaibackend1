#!/usr/bin/env bash
# Run the backend test suites.
#
#   ./test.sh                 everything (DB-free suites, then the Postgres-backed ones)
#   ./test.sh --keepdb        reuse the migrated test schema — fast after the first run
#   ./test.sh quick           only the DB-free suites (no Postgres needed)
#   ./test.sh db [labels…]    only the Postgres-backed suites, or the labels you give
#
# The Postgres-backed suites run in an isolated schema (never the real tables) — see
# lipaidox_backend/test_runner.py. Extra arguments pass through to `manage.py test`.
set -euo pipefail
cd "$(dirname "$0")"
PY=./myenv/bin/python

# Suites that need no database (fakes and mocks only).
FAST=(lipaidox.creator_plans.tests lipaidox.payment.tests lipaidox.media_processor.tests)
# Suites that need the real schema.
DB=(lipaidox.credits.tests lipaidox.feedback.tests lipaidox.content.tests)

mode="${1:-all}"
case "$mode" in quick|db|all) shift || true ;; *) mode=all ;; esac

status=0
if [[ "$mode" == "quick" || "$mode" == "all" ]]; then
  echo "── DB-free suites ──"
  USE_SQLITE=True $PY manage.py test "${FAST[@]}" "$@" || status=1
fi
if [[ "$mode" == "db" || "$mode" == "all" ]]; then
  echo "── Postgres-backed suites (isolated schema) ──"
  labels=("${DB[@]}")
  # In `db` mode, any non-flag arguments replace the default suite list.
  if [[ "$mode" == "db" ]]; then
    extra=(); for a in "$@"; do [[ "$a" == -* ]] || extra+=("$a"); done
    [[ ${#extra[@]} -gt 0 ]] && labels=("${extra[@]}")
  fi
  flags=(); for a in "$@"; do [[ "$a" == -* ]] && flags+=("$a"); done
  $PY manage.py test --settings=lipaidox_backend.test_settings "${labels[@]}" "${flags[@]}" || status=1
fi
exit $status
