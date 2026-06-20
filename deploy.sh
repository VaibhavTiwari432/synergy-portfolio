#!/usr/bin/env bash
# deploy.sh — Scope-C deploy (Audit Track 4): validate env -> migrate -> restart -> smoke.
# Aborts on first failure. Set SAF_RESTART_CMD for non-interactive restarts.
set -euo pipefail

: "${SAF_API_KEY:?SAF_API_KEY must be set}"
: "${DATABASE_URL:=postgresql://saf:saf_local@localhost:5432/saf_brain}"
export DATABASE_URL
BASE_URL="${SAF_BASE_URL:-http://localhost:8000}"

echo "[deploy] 1/4 env validated (SAF_API_KEY set; DB host=${DATABASE_URL##*@})"

echo "[deploy] 2/4 migrating database -> head (011 -> 012 -> 013)"
python -m alembic upgrade head

echo "[deploy] 3/4 restart app + worker"
if [ -n "${SAF_RESTART_CMD:-}" ]; then
  echo "[deploy]   running SAF_RESTART_CMD"
  bash -c "$SAF_RESTART_CMD"
else
  echo "[deploy]   SAF_RESTART_CMD not set — restart the API app AND worker now"
  echo "[deploy]   (asyncpg statement cache must clear), then press Enter (Ctrl-C aborts)."
  read -r _
fi

echo "[deploy] 4/4 smoke tests against ${BASE_URL}"
bash "$(dirname "$0")/scripts/smoke_scope_c.sh" "${BASE_URL}" "${SAF_API_KEY}"

echo "[deploy] DONE — Scope-C deploy verified."
