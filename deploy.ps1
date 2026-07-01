# deploy.ps1 — Scope-C deploy (Audit Track 4): validate env -> migrate -> restart -> smoke.
# Aborts on first failure. Set $env:SAF_RESTART_CMD for non-interactive restarts.
param(
  [string]$BaseUrl    = $(if ($env:SAF_BASE_URL) { $env:SAF_BASE_URL } else { "http://localhost:8000" }),
  [string]$ApiKey     = $env:SAF_API_KEY,
  [string]$RestartCmd = $env:SAF_RESTART_CMD
)
$ErrorActionPreference = "Stop"

if (-not $ApiKey) { throw "SAF_API_KEY must be set (env or -ApiKey)." }
if (-not $env:DATABASE_URL) { Write-Host "[deploy] DATABASE_URL not set - using default local DSN." }

Write-Host "[deploy] 1/4 env validated (SAF_API_KEY set)"

Write-Host "[deploy] 2/4 migrating database -> head (011 -> 012 -> 013)"
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed (exit $LASTEXITCODE)" }

Write-Host "[deploy] 3/4 restart app + worker"
if ($RestartCmd) {
  Write-Host "[deploy]   running SAF_RESTART_CMD"
  Invoke-Expression $RestartCmd
} else {
  Read-Host "[deploy]   Restart the API app AND worker now (asyncpg cache clears), then press Enter (Ctrl-C aborts)" | Out-Null
}

Write-Host "[deploy] 4/4 smoke tests against $BaseUrl"
& "$PSScriptRoot\scripts\smoke_scope_c.ps1" -BaseUrl $BaseUrl -ApiKey $ApiKey

Write-Host "[deploy] DONE - Scope-C deploy verified."
