# Backup, Recovery, Ops Monitoring & Rollback Runbook | دليل النسخ الاحتياطي والمراقبة والاستعادة (AR / EN)

- **Governance Basis:** `RECOVERY_DRILL_INPUTS.md`, `IT_ENVIRONMENT.md`, Eli Phase 0 Decisions `T8` & `T9`.

---

## 1. Automated Backup & Offsite Sync Schedule (`Eli T9`) | جدول النسخ الاحتياطي

- **Local Backup (Company PC):** Daily encrypted/custom-format `pg_dump` retained for **`30` days**.
- **Offsite Copy:** Weekly sync to `BACKUP_OFFSITE_TARGET` (company-owned free cloud via `rclone:` Google Drive/OneDrive OR external encrypted USB/`D:` drive) retained for **`90` days**.
- **Command (Windows Task Scheduler — Daily 02:00 Cairo):**
  ```powershell
  python scripts/backup_and_restore_verified.py `
    --database-url "$env:DATABASE_URL" `
    --backup-dir "D:\ElsebaeyPharma-Backups\daily" `
    --local-retention-days 30 `
    --offsite-target "$env:BACKUP_OFFSITE_TARGET" `
    --docker-pg-container erp-prod-db
  ```
- **Monthly Verified Restore Drill (Safe Disposable DB Only):**
  ```powershell
  python scripts/backup_and_restore_verified.py `
    --database-url "$env:DATABASE_URL" `
    --backup-dir "D:\ElsebaeyPharma-Backups\drills" `
    --docker-pg-container erp-prod-db `
    --verify-restore-db "dms_cycle_test_20261121000000000000000000000099" `
    --run-corrupt-control
  ```
  Verifies matching `alembic_version` (`0025_returns_accounting`), exact row counts across 13 core tables, exact Decimal totals (stock, invoices, AR debit/credit), corrupt-dump rejection, and automatic disposable DB cleanup, writing `<stem>_receipt.json` + `.sha256`.

---

## 2. Ops Monitoring, Structured Logs & Resource Limits (`Eli T8`) | المراقبة والسجلات

- **Health Endpoints:**
  - `GET /livez` -> process liveness (`200 OK`, echoes clean `X-Request-ID` correlation ID)
  - `GET /readyz` -> PostgreSQL connectivity (`200 OK` or sanitized `503` without credential leakage)
  - `GET /docs`, `/redoc`, `/openapi.json` -> MUST return `404` in production
- **Structured JSON Logs:** Emitted to Docker stdout with `timestamp`, `level`, `request_id`, `method`, `path`, `status_code`, `duration_ms` (zero passwords or tokens).
- **Container Resource Limits (`docker-compose.prod.yml`):** Non-root `uid=100(app)`, single Uvicorn worker (`UVICORN_WORKERS=1`), explicit CPU/RAM limits, localhost-only port binding (`127.0.0.1:8000`) behind Cloudflare Tunnel (`docs/CLOUDFLARE_FREE_TUNNEL_RUNBOOK.md`).
- **Scheduled Health Check (Every 5 Minutes, Optional Telegram Ops Alert — Zero Paid Email/SMS):**
  ```powershell
  python scripts/ops_health_monitor.py `
    --base-url "http://127.0.0.1:8000" `
    --container "erp-prod-app" `
    --telegram-alert
  ```

---

## 3. Emergency Rollback Procedure (< 30s Non-Destructive Halt) | خطة الاستعادة الطارئة

### العربية
1. **إيقاف فوري للترحيل (أقل من 30 ثانية دون فقد بيانات):** غيّر `POSTING_ENABLED=false` في `.env.prod` وأعد تشغيل حاوية التطبيق فقط (`docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-deps app`). تظل كافة البيانات المرحّلة مقروءة ومدققة ويُمنع أي ترحيل جديد (`409`).
2. **لقطة جنائية قبل الاستعادة:** خذ نسخة `pg_dump` فورية قبل أي استرجاع.
3. **الاستعادة الكاملة (بموافقة المالك فقط):** أوقف التطبيق، استعد آخر نسخة موثقة بـ `pg_restore --exit-on-error --no-owner --no-privileges` في قاعدة جديدة، تحقق من `alembic current` ومطابقة الأعداد والإجماليات العشرية، ثم وجّه التطبيق إليها مع `POSTING_ENABLED=false`.

### English
1. **Immediate Posting Halt (< 30s, Zero Data Loss):** Set `POSTING_ENABLED=false` in `.env.prod` and recreate ONLY the app container (`up -d --no-deps app`). All committed data stays intact and auditable while writes return `409`.
2. **Forensic Snapshot First:** Take a `pg_dump` snapshot of the current DB before restoring anything.
3. **Full Restore (Owner Approval Required):** Stop app, restore last verified `.dump` into a fresh DB, verify `alembic_version`, row counts, and exact Decimal totals, switch `DATABASE_URL`, and start with `POSTING_ENABLED=false`.
