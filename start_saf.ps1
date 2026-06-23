# start_saf.ps1 - starts the SAF API server + scoring worker
# Run from the project root: .\start_saf.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Escape-PSLiteral([string]$Value) {
  return $Value.Replace("'", "''")
}

$keyFile = Join-Path $root ".saf_api_key"
if (-not $env:SAF_API_KEY) {
  if (Test-Path $keyFile) {
    $env:SAF_API_KEY = (Get-Content -LiteralPath $keyFile -Raw).Trim()
  } else {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $env:SAF_API_KEY = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    Set-Content -LiteralPath $keyFile -Value $env:SAF_API_KEY -NoNewline
  }
}

$env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "postgresql://saf:saf_local@localhost:5432/saf_brain" }

if (-not ($env:GEMINI_API_KEY -or $env:GOOGLE_API_KEY)) {
  Write-Host "Cannot start the full SAF pipeline: scoring needs GEMINI_API_KEY or GOOGLE_API_KEY." -ForegroundColor Red
  Write-Host "Set one in this PowerShell session, then run .\start_saf.ps1 again." -ForegroundColor Yellow
  Write-Host 'Example: $env:GEMINI_API_KEY="your-key-here"' -ForegroundColor Yellow
  exit 1
}

$rootForCommand = Escape-PSLiteral $root
$databaseUrlForCommand = Escape-PSLiteral $env:DATABASE_URL
$apiKeyForCommand = Escape-PSLiteral $env:SAF_API_KEY
$judgeAssignments = ""
if ($env:GEMINI_API_KEY) {
  $judgeAssignments += "`$env:GEMINI_API_KEY='$(Escape-PSLiteral $env:GEMINI_API_KEY)'; "
}
if ($env:GOOGLE_API_KEY) {
  $judgeAssignments += "`$env:GOOGLE_API_KEY='$(Escape-PSLiteral $env:GOOGLE_API_KEY)'; "
}

Write-Host "Starting SAF API server on http://localhost:8000 ..." -ForegroundColor Cyan
$apiCommand = "cd '$rootForCommand'; `$env:SAF_API_KEY='$apiKeyForCommand'; `$env:DATABASE_URL='$databaseUrlForCommand'; $judgeAssignments uvicorn src.api.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  $apiCommand `
  -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting SAF scoring worker ..." -ForegroundColor Cyan
$workerCommand = "cd '$rootForCommand'; `$env:DATABASE_URL='$databaseUrlForCommand'; $judgeAssignments python -m src.worker.scorer"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  $workerCommand `
  -WindowStyle Normal

Write-Host ""
Write-Host "Both processes launched." -ForegroundColor Green
Write-Host "API  -> http://localhost:8000/v1/health"
Write-Host "Database -> $env:DATABASE_URL"
Write-Host "Extension settings: endpoint=http://localhost:8000"
Write-Host "Extension API key: $env:SAF_API_KEY"
