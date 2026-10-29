# DEPLOY_DEMO.md — ElsebaeyPharma ERP Demo Deployment

## Overview

Run the ERP on a local Windows/Linux machine and expose it securely via Cloudflare Tunnel
for demo purposes. No Vercel, no new Python dependencies, no OCI vendor lock-in.

The application is a standard FastAPI + PostgreSQL + PWA stack. The only Cloudflare-specific
component is the tunnel binary (`cloudflared`), which is a standalone executable — not a
dependency. To migrate to any other host, copy the DB dump + config + uploaded files +
deployment scripts and use any reverse proxy (nginx, Caddy, etc.).

## Prerequisites

1. Python 3.14+ with project dependencies installed (`pip install -r requirements.txt`)
2. PostgreSQL 15+ running locally (localhost only, port 5432)
3. `cloudflared` binary at `C:/Users/emadg/cloudflared.exe` (or `cloudflared` on PATH)
4. Seeded demo database (`medical_demo` or `dms_cycle_test_*`)
5. Environment variables set (see `.env.example`)

## Pre-Exposure Security Checklist

Complete ALL items before exposing the tunnel:

- [ ] **Auth on every endpoint**: All API routes require `get_current_user` dependency. Verify no unauthenticated endpoints exist.
- [ ] **Rate limiting on login**: Login endpoint (`/auth/login`) has rate limiting (max 5 attempts per minute per IP).
- [ ] **Postgres on localhost only**: PostgreSQL `listen_addresses = 'localhost'` in `postgresql.conf`. No external access.
- [ ] **POSTING_ENABLED=False**: Verify `app/sales/router.py` returns 409 on post/void/reverse. Default is OFF.
- [ ] **No real data**: Demo DB contains only seeded/synthetic data. No real customer records, no real invoices.
- [ ] **No workbooks**: The 7 source `.xlsx` files are NOT present on the demo machine. Only the DB dump.
- [ ] **No credentials in code**: Grep for hardcoded secrets, API keys, passwords in app/ and web/.
- [ ] **HTTPS only**: Cloudflare Tunnel provides TLS automatically. No HTTP-only access.
- [ ] **CORS restricted**: Only the tunnel domain is allowed in CORS origins.

## Quick Tunnel (Demo — no account needed)

```powershell
# 1. Start the ERP backend
cd C:\Projects\ERPWorktrees\erp-beta-clean-20261029
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. In a separate terminal, start the quick tunnel
C:\Users\emadg\cloudflared.exe tunnel --url http://localhost:8000
```

This gives an instant public HTTPS URL (e.g., `https://abc-xyz.trycloudflare.com`).
The URL changes on each restart. Suitable for demos only.

## Named Tunnel (Production — requires Cloudflare account + domain)

```powershell
# 1. Authenticate with Cloudflare
C:\Users\emadg\cloudflared.exe tunnel login

# 2. Create a named tunnel
C:\Users\emadg\cloudflared.exe tunnel create elsebaey-erp

# 3. Configure the tunnel (creates ~/.cloudflared/config.yml)
# Edit config.yml:
#   tunnel: <tunnel-id>
#   credentials-file: C:\Users\<user>\.cloudflared\<tunnel-id>.json
#   ingress:
#     - hostname: erp.yourdomain.com
#       service: http://localhost:8000
#     - service: http_status:404

# 4. Route DNS
C:\Users\emadg\cloudflared.exe tunnel route dns elsebaey-erp erp.yourdomain.com

# 5. Run the tunnel
C:\Users\emadg\cloudflared.exe tunnel run elsebaey-erp
```

## Database Backup & Restore

### Backup (before deployment)
```bash
pg_dump -U postgres -d medical_demo -F c -f medical_demo_backup.dump
```

### Restore (on new machine)
```bash
createdb -U postgres medical_demo
pg_restore -U postgres -d medical_demo medical_demo_backup.dump
```

## Migration to Local Server (Portability)

To move from Cloudflare Tunnel to a local server:

1. **Copy database dump** (`medical_demo_backup.dump`) to the new machine
2. **Copy environment config** (`.env` with DATABASE_URL, SECRET_KEY, etc.)
3. **Copy uploaded files** (if any — currently none in this build)
4. **Copy deployment scripts** (this file + start scripts)
5. **Install cloudflared** (or use nginx/Caddy as reverse proxy)
6. **Run the same start script** — no application code changes needed

The application is standard FastAPI + PostgreSQL. No Cloudflare-specific code exists in `app/`.
The only Cloudflare component is the tunnel binary, which is interchangeable with any
reverse proxy.

## Environment Variables

```
DATABASE_URL=postgresql://user:pass@localhost:5432/medical_demo
SECRET_KEY=<generate-with-openssl-rand-hex-32>
POSTING_ENABLED=False
ALLOWED_ORIGINS=https://your-tunnel-domain.com
```

## Troubleshooting

- **Tunnel won't start**: Check that port 8000 is free (`netstat -ano | findstr :8000`)
- **DB connection refused**: Verify PostgreSQL is running and listening on localhost
- **403 on all routes**: Check CORS origins include the tunnel domain
- **Login rate limited**: Wait 60 seconds, or restart the backend
