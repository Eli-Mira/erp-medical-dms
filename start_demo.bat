@echo off
REM start_demo.bat — Start ElsebaeyPharma ERP for Cloudflare Tunnel demo
REM Usage: start_demo.bat [quick|named]
REM
REM quick: Uses Cloudflare quick tunnel (instant public URL, no account needed)
REM named: Uses named tunnel (requires Cloudflare account + domain configured)

setlocal enabledelayedexpansion

set "ERP_DIR=C:\Projects\ERPWorktrees\erp-beta-clean-20261029"
set "CLOUDFLARED=C:\Users\emadg\cloudflared.exe"
set "PORT=8000"

cd /d "%ERP_DIR%"

echo === ElsebaeyPharma ERP Demo ===
echo.

REM Check prerequisites
if not exist "%CLOUDFLARED%" (
    echo ERROR: cloudflared not found at %CLOUDFLARED%
    echo Download from: https://github.com/cloudflare/cloudflared/releases
    exit /b 1
)

if not exist ".env" (
    echo WARNING: .env file not found. Using defaults.
    echo Create .env from .env.example before production use.
)

REM Verify POSTING_ENABLED is OFF
findstr /C:"POSTING_ENABLED=False" .env >nul 2>&1
if errorlevel 1 (
    echo WARNING: POSTING_ENABLED may not be False. Check .env
)

echo Starting ERP backend on localhost:%PORT%...
start "ERP Backend" cmd /c "cd /d %ERP_DIR% && python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

echo.
echo Backend starting. Verify with: curl http://localhost:%PORT%/health
echo.

if "%1"=="named" (
    echo Starting named Cloudflare tunnel...
    "%CLOUDFLARED%" tunnel run elsebaey-erp
) else (
    echo Starting Cloudflare quick tunnel...
    echo (URL will be displayed below. Press Ctrl+C to stop.)
    "%CLOUDFLARED%" tunnel --url http://localhost:%PORT%
)

echo.
echo Demo stopped.