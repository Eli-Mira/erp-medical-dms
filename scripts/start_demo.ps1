<#
.SYNOPSIS
  Starts the client-demo stack: uvicorn (medical_demo, POSTING off) + optional
  Cloudflare quick tunnel, and prints the ephemeral public URL.

.DESCRIPTION
  Runbook so the public link survives console restarts:
      pwsh scripts\start_demo.ps1            # server + tunnel
      pwsh scripts\start_demo.ps1 -NoTunnel  # localhost only
  The quick-tunnel URL is regenerated on every run (ephemeral by design).
  Everything touches ONLY the `medical_demo` database (synthetic data);
  `medical_dms` production is never contacted.

.PARAMETER Port
  Uvicorn port (default 8018).

.NOTES
  Requires: uv (server), cloudflared.exe at %LOCALAPPDATA%\cloudflared (tunnel).
#>
[CmdletBinding()]
param(
  [int]$Port = 8018,
  [switch]$NoTunnel
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

Write-Host "== Medical Company System — demo launcher (client prototype) ==" -ForegroundColor Cyan
Write-Host "Repo: $repo"

# 1) Environment ------------------------------------------------------------
$env:DATABASE_URL = "postgresql+psycopg://dms:dms-dev@localhost:5432/medical_demo"
$env:POSTING_ENABLED = "false"
$env:DEMO_MODE = "1"
Write-Host "DB: medical_demo (synthetic) | POSTING_ENABLED=false | DEMO_MODE=1"

# 2) Server -----------------------------------------------------------------
$health = "http://127.0.0.1:$Port/health"
try {
  $existingOk = (Invoke-RestMethod -Uri $health -TimeoutSec 2 -ErrorAction SilentlyContinue)
  if ($existingOk) {
    Write-Host "Server already up on port $Port — reusing it." -ForegroundColor Yellow
    $serverStart = $false
  } else { $serverStart = $true }
} catch {
  $serverStart = $true
}

if ($serverStart) {
  $logDir = Join-Path $repo "logs"
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  $serverLog = Join-Path $logDir "demo-server.log"
  Write-Host "Starting uvicorn on port $Port (log: $serverLog)"
  $proc = Start-Process -FilePath "uv" -ArgumentList @(
    "--directory", $repo, "--with-requirements", (Join-Path $repo "requirements.txt"),
    "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port"
  ) -RedirectStandardOutput $serverLog -RedirectStandardError (Join-Path $logDir "demo-server.err.log") -PassThru -NoNewWindow
  Write-Host "Server PID: $($proc.Id)"
} else {
  $proc = $null
}

# 3) Health ------------------------------------------------------------------
$up = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try { Invoke-RestMethod -Uri $health -TimeoutSec 2 | Out-Null; $up = $true; break } catch { }
}
if (-not $up) {
  Write-Error "Server did not come up on $health in 30s. Check logs/ under the repo."
  if ($proc) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
  exit 1
}
Write-Host "Health OK: $health" -ForegroundColor Green

# 4) Demo database check (safe read) -----------------------------------------
# If the signup you need is empty rebuild it manually first:
#   uv run --with-requirements requirements.txt python scripts/make_demo.py
# The launcher does NOT rebuild the database automatically.

# 5) Tunnel -------------------------------------------------------------------
if ($NoTunnel) {
  Write-Host "`nLocal demo:  http://127.0.0.1:$Port/app/  (LAN + phone: same host at :$Port/app/)" -ForegroundColor Cyan
  Write-Host "LAN access needs the host bind; start uvicorn with --host 0.0.0.0 for phones (see docs/CLIENT_DEMO.md)."
  exit 0
}

$cloudflared = Join-Path $env:LOCALAPPDATA "cloudflared\cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
  Write-Warning "cloudflared not found at $cloudflared — skipping tunnel (local server is up)."
  exit 0
}

$tunnelLog = Join-Path $logDir "demo-tunnel.log"
Write-Host "Starting Cloudflare quick tunnel (log: $tunnelLog)…"
$tunnel = Start-Process -FilePath $cloudflared -ArgumentList @(
  "tunnel", "--url", "http://127.0.0.1:$Port", "--no-autoupdate"
) -RedirectStandardOutput $tunnelLog -RedirectStandardError (Join-Path $logDir "demo-tunnel.err.log") -PassThru -NoNewWindow

# Quick tunnels announce their URL on stderr; poll the log for it.
$publicUrl = $null
for ($i = 0; $i -lt 45; $i++) {
  Start-Sleep -Seconds 1
  if (Test-Path $tunnelLog) {
    $line = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -SimpleMatch:$false | Select-Object -First 1
    if ($line) { $publicUrl = ($line.Line -replace "^\s*\|\s*", "").Trim(); if ($publicUrl -match "https://[a-z0-9-]+\.trycloudflare\.com") { $publicUrl = $Matches[0]; break } }
  }
}

if ($publicUrl) {
  Write-Host ""
  Write-Host "PUBLIC DEMO URL:  $publicUrl/app/" -ForegroundColor Green
  Write-Host "Local demo URL:   http://127.0.0.1:$Port/app/"
  Write-Host "Demo login:  demo_owner / demo_rep / demo_finance — password: Demo-2026"
  Write-Host "(Quick-tunnel URLs are ephemeral; re-run this script to get a fresh one.)"
} else {
  Write-Warning "Tunnel URL not detected in 45s. Check logs\demo-tunnel.err.log."
}
