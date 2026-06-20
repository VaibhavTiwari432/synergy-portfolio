#!/usr/bin/env bash
# smoke_scope_c.sh — Unix companion to smoke_scope_c.ps1 (Audit Track 4).
# Usage: scripts/smoke_scope_c.sh [BASE_URL] [API_KEY] [USER_REF]
set -euo pipefail

BASE_URL="${1:-${SAF_BASE_URL:-http://localhost:8000}}"
API_KEY="${2:-${SAF_API_KEY:-}}"
USER_REF="${3:-saf-smoke}"
[ -n "$API_KEY" ] || { echo "SAF_API_KEY required (arg 2 or env)"; exit 1; }

check() {  # name method path [json-body]
  local name="$1" method="$2" path="$3" body="${4:-}"
  echo "SMOKE ${name} -> ${method} ${path}"
  local args=(-sS -o /dev/null -w "%{http_code}" -X "$method"
              -H "X-API-Key: ${API_KEY}" -H "Content-Type: application/json"
              "${BASE_URL}${path}")
  [ -n "$body" ] && args+=(-d "$body")
  local code; code="$(curl "${args[@]}")"
  case "$code" in
    2*) echo "PASS  ${name} (${code})" ;;
    *)  echo "FAIL  ${name} (${code})"; exit 1 ;;
  esac
}

check "health"         GET   "/v1/health"
check "settings get"   GET   "/v1/users/${USER_REF}/settings"
check "settings patch" PATCH "/v1/users/${USER_REF}/settings" '{"auto_analyse":false,"calibration_opt_in":false}'
check "chats list"     GET   "/v1/users/${USER_REF}/chats"
check "portfolio"      GET   "/v1/users/${USER_REF}/portfolio"
check "projects list"  GET   "/v1/users/${USER_REF}/projects?limit=5"

echo "Scope-C smoke passed for user '${USER_REF}'."
