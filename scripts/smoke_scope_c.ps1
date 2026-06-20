param(
  [string]$BaseUrl = "http://localhost:8000",
  [string]$ApiKey = $env:SAF_API_KEY,
  [string]$UserRef = "saf-smoke"
)

$ErrorActionPreference = "Stop"

if (-not $ApiKey) {
  throw "SAF_API_KEY is required. Pass -ApiKey or set `$env:SAF_API_KEY."
}

$Headers = @{
  "X-API-Key" = $ApiKey
  "Content-Type" = "application/json"
}

function Invoke-Smoke {
  param(
    [string]$Name,
    [string]$Method,
    [string]$Path,
    [object]$Body = $null
  )

  $uri = "$BaseUrl$Path"
  Write-Host "SMOKE $Name -> $Method $Path"
  $args = @{
    Method = $Method
    Uri = $uri
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $args.Body = ($Body | ConvertTo-Json -Depth 8)
  }
  $result = Invoke-RestMethod @args
  Write-Host "PASS  $Name"
  return $result
}

Invoke-Smoke -Name "health" -Method "GET" -Path "/v1/health" | Out-Null
Invoke-Smoke -Name "settings get" -Method "GET" -Path "/v1/users/$UserRef/settings" | Out-Null
Invoke-Smoke -Name "settings patch" -Method "PATCH" -Path "/v1/users/$UserRef/settings" -Body @{
  auto_analyse = $false
  calibration_opt_in = $false
} | Out-Null
Invoke-Smoke -Name "chats list" -Method "GET" -Path "/v1/users/$UserRef/chats" | Out-Null
Invoke-Smoke -Name "portfolio" -Method "GET" -Path "/v1/users/$UserRef/portfolio" | Out-Null
Invoke-Smoke -Name "projects list" -Method "GET" -Path "/v1/users/$UserRef/projects?limit=5" | Out-Null

Write-Host "Scope-C smoke passed for user '$UserRef'."
