# Release Notes — ElsebaeyPharma ERP RC2 (2026-11-21)

- **Release Baseline:** `rc1/20261119` (`939e91b9`) -> **RC2 Candidate (`agent/s1/rc2-candidate-local`, LOCAL-ONLY until Claude Opus 5.5 batch countersign)**
- **Alembic Head:** `0025_returns_accounting` (sequential single head, up/down/up tested)
- **Container Image:** `erp-rc2-candidate:local` (non-root `uid=100(app)`, `/livez` `HEALTHCHECK`, pinned runtime deps, `0` runtime CVEs)

## Highlights Shipped in RC2
1. **Invoice FEFO Batch Picker & Mobile A11y (`RC2-01`):** Earliest-expiry-first batch picker on invoice lines, `warehouse_staff` navigation hardened (zero JS crashes on restricted modules), mobile tap targets >= 44px, WCAG AA contrast & keyboard focus polish.
2. **Deadlock-Free Warehouse Transfers (`RC2-02`):** Canonical lock ordering on `batch_record` and `stock_balance` (proven `RC1` `40P01` fail vs `RC2` `0/120` deadlocks with exact stock conservation).
3. **Strict Tenant / Branch / Territory Isolation (`RC2-03`):** Closed `P3C-01/02/03` leaks across visits, held stock, targets, AR statements, and cross-branch warehouse returns (`Eli A9`); pre-lock `403` for `read_only_auditor`.
4. **Auth Hardening Behind Proxy (`RC2-04`):** `RATE_LIMIT_TRUSTED_PROXIES` CIDR validation, failed-login & `429` audit logging with IP + User-Agent and zero password leakage, pre-auth order fixed on `/auth/users`.
5. **Input Validation & Bounds (`RC2-05`):** Strict Pydantic validation, NUL-byte `422` guard (never `500`), bounded audit limits.
6. **Performance & Indexes (`RC2-06`):** Single-SQL `GET /collections` and `GET /ar/aging`, paginated AR/collections, `0024_perf_indexes`.
7. **Production Kit & Observability (`RC2-07`):** Non-root Dockerfile, `/livez` & `/readyz`, correlation `X-Request-ID` JSON logs, `docker-compose.prod.yml`, Cloudflare free-plan runbook.
8. **C9 Synthetic Import & Reconciliation (`RC2-08`):** Dry-run-first transactional idempotent importer with exact `Decimal` verification and reject-for-sign-off reporting.
9. **Complete Telegram Bot (`RC2-09` + Phase 1 `aiogram 3.33.0`):** Dedicated `requirements-telegram.txt` (MIT), fail-closed `BaseMiddleware` allowlists, ERP role & territory/branch scoping, bilingual AR/EN, rate limiting, `/alerts` daily digest behind flag, group `@mention` mode gated behind private live smoke, real PostgreSQL `telegram_reader` + local mock Bot API test suite.
10. **Full Returns Accounting (`RC2-12` + `RC2-12b`):** Quarantine -> `approved_restock` / `scrapped` state machine, double-settlement `409` guard, VAT-inclusive credit note extraction aligned with `app/sales/calc.py`, round-trip zero-AR conservation verified.
11. **Day-1 Accountant CSV Exports (`RC2-13`):** UTF-8 BOM formula-safe exports for invoices, sales report, stock balance, AR aging, and collections.
12. **Verified Backup/Restore & Ops Monitor:** `scripts/backup_and_restore_verified.py` (30d local / 90d offsite + disposable restore verification + corrupt-dump negative control) and `scripts/ops_health_monitor.py`.

## Pending Confirmations & RC3 Roadmap (`Eli T6`, `T7`, `T11`)
- **Accountant VAT-Basis Confirmation:** Recorded as **PENDING** (`VAT_INCLUSIVE=true` default behind config flag).
- **RC3 Queue (Starts Immediately After RC2 Countersign):** Cash/Expenses (`RC3-01`), GL/P&L/Balance Sheet (`RC3-02`), and Purchasing/AP (`RC3-03`) first using `D47a` defaults; Lightweight Payroll (`RC3-04`), Fixed-Asset Revaluation (`RC3-05`), and 4-Tier Pricing (`RC3-06`) held behind flags until accountant confirms workbook formulas; Private Accounts import (`RC3-07`) pending written owner authorization; Telegram Group Mode (`RC3-08`) after live private smoke; Offline Visit Sync (`RC3-09`).
- **License & Support (`Eli T11`):** Eli retains reusable ERP core IP and grants ElsebaeyPharma a perpetual, non-exclusive internal-use license + 30-day post-go-live stabilization support.
