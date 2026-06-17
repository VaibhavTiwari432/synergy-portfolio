# start_saf.ps1 — starts the SAF API server + scoring worker
# Run from the project root: .\start_saf.ps1

$env:SAF_API_KEY   = "saf_dev_2026"
$env:DATABASE_URL  = "postgresql://saf:saf_local@localhost:5432/saf_brain"
$env:GEMINI_API_KEY = $env:GEMINI_API_KEY  # inherit from shell if already set

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Starting SAF API server on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "cd '$root'; `$env:SAF_API_KEY='saf_dev_2026'; `$env:DATABASE_URL='postgresql://saf:saf_local@localhost:5432/saf_brain'; uvicorn src.api.main:app --port 8000" `
  -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting SAF scoring worker ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "cd '$root'; `$env:DATABASE_URL='postgresql://saf:saf_local@localhost:5432/saf_brain'; python -m src.worker.scorer" `
  -WindowStyle Normal

Write-Host ""
Write-Host "Both processes launched." -ForegroundColor Green
Write-Host "API  -> http://localhost:8000/v1/health"
Write-Host "Extension settings: endpoint=http://localhost:8000  key=saf_dev_2026"
