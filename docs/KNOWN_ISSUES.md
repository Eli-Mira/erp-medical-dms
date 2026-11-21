# Known Issues, Pending Confirmations & Deferrals — ElsebaeyPharma ERP (RC2)

- **Updated:** `2026-11-21`
- **Alembic Head:** `0025_returns_accounting` (sequential single head; previous duplicate `0024_returns_accounting` filename cleanly renamed to `0025_returns_accounting` chaining onto `0024_perf_indexes`).

## 1. Pending Buyer / Accountant Confirmations (Safe Defaults Active Behind Flags)
1. **Accountant VAT-Basis Confirmation (`PENDING`, `VAT_INCLUSIVE=true`):** Both `app/sales/calc.py` and `app/returns/router.py` (`RC2-12b`) assume `14%` VAT-inclusive pricing (matching existing Excel workbooks, `D36`, Eli `A4`/`T6`). Final written confirmation from ElsebaeyPharma's accountant on VAT basis, exemptions, and invoice rounding is recorded as **PENDING** before live production posting (`POSTING_ENABLED=true`).
2. **Real Workbook Cutover (`C9`):** Official customer/warehouse code list, exact cutoff date, and `فرق التحصيل` mapping await buyer accountant sign‑off before running `scripts/c9_synthetic_reconcile.py` / real-data apply on the buyer PC (`Eli A3`/`T6`).
3. **RC3 Accountant-Gated Modules (`Eli T7`):** Cash/Expenses, GL/P&L/Balance Sheet, and Purchasing/AP start immediately after RC2 countersign using `D47a` defaults; Lightweight Payroll (`C9 Q7`), Fixed-Asset Revaluation (`C9 Q9`), and 4‑Tier Pricing (`C9 Q11`) remain behind feature flags until the accountant confirms exact workbook formulas.

## 2. Operational Constraints & Known Limitations
1. **Single-Worker Auth Rate Limiter (`IT_ENVIRONMENT.md`):** Login rate limiting (`10/account`, `50/IP` per `300s` rolling window) is process‑local. Production deployments MUST run `UVICORN_WORKERS=1` (`docker-compose.prod.yml`) and set `RATE_LIMIT_TRUSTED_PROXIES` ONLY to the exact Cloudflare/Nginx proxy CIDR when behind a reverse proxy.
2. **Dev-Only Dependency Advisory (`pytest==8.4.2`, `MODERATE`):** OSV scan reports `0` CVEs across all 36 runtime production packages and 1 `MODERATE` advisory (`GHSA-6w46-j5rx-g56g`, local `/tmp` race in `pytest==8.4.2`), which is never imported or executed by `uvicorn app.main:app` in the non‑root `uid=100(app)` container.
3. **Browser-Based Print/PDF (`D45`):** Invoices, customer statements, and receipts use A4 bilingual CSS print layouts (`@media print`, zero‑quantity lines hidden) via browser Save‑as‑PDF; server‑side WeasyPrint PDF remains deferred.
4. **Offline PWA Scope (`T10`):** RC2 ships a read‑only offline cache banner; queued offline stock‑visit sync ships in RC3 (`RC3-09`).
5. **Telegram Group Mode (`Eli A6`/`T1`):** Private‑chat allowlist + role mapping ships first (`TELEGRAM_GROUP_MODE_ENABLED=false`); group `@mention` mode activates only after live private‑chat smoke on the operator's throwaway bot.

## 3. Commercial License & Support Notice (`Eli T11`)
- **IP & License:** Eli retains reusable ERP core IP and grants ElsebaeyPharma a perpetual, non‑exclusive internal‑use license for company operations. Open‑source dependencies retain their respective permissive licenses (see `THIRD_PARTY_NOTICES.md`).
- **Support:** Includes 30‑day post‑go‑live stabilization support; ongoing feature work or hosting changes are governed separately.
