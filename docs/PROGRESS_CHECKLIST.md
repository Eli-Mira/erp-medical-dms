# Progress Checklist — Medical Company System

## Current checkpoint — 2026-10-17 (supersedes older gate/stack summaries below)

- [x] Eli authorized Invoice Slice 1 and continued Piece 2. Approved stack: **FastAPI + PostgreSQL + psycopg3 + existing vanilla JS/PWA** (D34–D37). Hosting OS remains deferred; no React rewrite.
- [x] Piece 1 schema/calculation baseline: commit `5cb375a` (25 tests then). This is not the complete Invoice Module.
- [x] Piece 2 create/view/replace Draft/void Draft API, territory/role controls, audit and duplicate/version/input validation: `app/sales/{router,repo,schemas}.py`; `tests/test_invoice_api.py` and `tests/test_invoice_boundaries.py`. Committed as `6b6f628`.
- [x] Applied additive migration `0004_invoice_drafts`; minimal territory/warehouse/batch references and API + database posting block. No stock/AR module was built.
- [x] **Inventory Slice 1 (Module D)**: migration `0005_inventory_stock` adds the append-only `inventory.stock_movement` ledger and `inventory.stock_balance` running total per warehouse/product/batch, with atomic movement application and role-gated API (`app/inventory/`). 41 new controls; details in `docs/INVENTORY_SLICE.md`.
- [x] **Receivables (AR) Slice 1 (Module E, AR half)**: migrations `0006` (`platform.user_branch` mapping; posting gates relaxed to require `posted_at`; `posted_by`) and `0007` (`finance.ar_entry` ledger); AR service + role-gated API; and `app/sales/service.py::post_invoice_atomic` — the tested Invoice → Stock → AR transaction. Details in `docs/AR_SLICE.md`.
- [x] Parent native full-suite run: **162 passed**, no failed/skipped cases; raw log/JUnit/runtime/source-hash bindings under `docs/evidence/ar-slice1/final-run/`. Fresh empty database migrated `0001→0007`, downgraded to `0005`, re-applied, then passed the suite: disposable DB removed and absence verified.
- [x] Strict application-vs-Excel comparison: **133 numeric rows** across two complete named transaction sheets, no mismatch skipping; all 7 workbook hashes preserved. Exact coverage/limits: `docs/INVOICE_SLICE_1.md`.
- [x] Scoped inventory review delivered: no blocking code findings. Parent revalidated final hashes/cases and accepted the inventory repair. Reviewer read-only/budget deviations are preserved and its unqualified method certification is **not accepted**; terminal disposition in `docs/evidence/inventory-authorization/VERIFICATION.md` (not a pending re-review loop). Full-system security/release approval remains open.
- [x] Sales routing prerequisite: decoupled invoice sales branch from source-warehouse owner branch. Migration `alembic/versions/0009_sales_source_warehouse.py` (renames `invoice_prepare`/`fk_invoice_warehouse_branch` composite FK), router `_prepare` scope/route guard, `tests/test_invoice_routing.py` (Sharqia/Gharbia source-warehouse scoping). Commit `c50bb02` [skip-ci]; verification evidence committed `2b46e6f`; disposable FK chain: 0009 accepts cross-branch invoice, 0008 rejects; 189/189 tests pass on disposable DB, sources unchanged, DB dropped. Reviewer method deviations preserved, unqualified certification not accepted.
- [x] Posting gate: default-OFF flag `POSTING_ENABLED` (`app/config.py`), `POST /invoices/{id}/post` returns HTTP 409 while OFF and delegates to `app.sales.service.post_invoice_atomic` while ON; committed `ac596eb`. Activation needs explicit approval. **Posting is still HTTP 409 every day; no flag enabled.**
- [x] Inventory authorization repair: `platform.user_branch` resolves actual active warehouse IDs via ownership; managers read only; invoice-backed movement details require invoice branch + territory grants. Shared-route mappings never confer whole-warehouse permission. Native **182 passed** (20 new authorization cases); disposable chain `0001→0008`, down/up, **182 passed**, DB removed. RED/GREEN/final bindings: `docs/evidence/inventory-authorization/`. This corrects the false `893a0d9` completion report; see `docs/INVENTORY_SLICE.md`.
- [ ] Private GitHub preparation: no remote configured; repository-wide secrets/history/confidential Excel-data sweep remains required before any push. Not performed in this authorization-only task.
- [ ] Payroll formula remains **UNVERIFIED**; the header-structure test is not salary-formula validation. Stock thresholds and other deferred UQs stay deferred.

The older phase items below are historical records, not renewed claims that the complete platform, mapping, schema or production gate has passed.


> **D29 rule (Eli):** a task is ✅ only when evidence is attached — a file path,
> terminal output, or hash. No empty checkmarks. We never assume something is
> done without verifying it really exists and is fully implemented.

Legend: ⬜ todo · 🔄 in progress · ✅ done · ⛔ blocked · ⏭️ gated/delayed

---

## Phase 0 — Discovery  [gate: ✅ complete per D26]
- [✅] Inventory 7 workbooks + sources → `docs/SOURCE_WORKBOOK_INVENTORY.md`
- [✅] SHA-256 verify sources immutable (2026-10-16, all 7 match baseline) → `docs/SOURCE_HASHES.txt` + `sha256sum *.xlsx`
- [✅] Resolve open questions Q1–Q3 → `docs/OPEN_QUESTIONS.md`
- [✅] Sheet→system mapping with citations → `docs/EXCEL_TO_SYSTEM_MAPPING.md`
- [✅] Current workflows from formulas → `docs/CURRENT_WORKFLOWS.md`
- [✅] Reconciliation approach → `docs/MIGRATION_RECONCILIATION_PLAN.md`
- [✅] Cross-workbook sheet-name duplicates report (86) + placeholders (53) → `docs/ENTITY_DUPLICATE_REPORT.md`
- [✅] Data dictionary → `docs/DATA_DICTIONARY.md`
- [✅] Excel feature catalog → `docs/EXCEL_FEATURE_CATALOG.md`
- [✅] Migration map (sheet→module) → `docs/MODULE_MAP.md`
- [✅] Decisions + evidence resolutions D1–D26 → `docs/DECISION_LOG.md`
- [✅] Phase 0 gate cleared — sources untouched, all questions resolved against evidence.

## Phase 1 — Planning & Architecture  [gate: ✅ build-start approved 2026-10-16]
- [✅] `docs/PRD.md` (390 lines) — roles, BR-01–BR-25, 15 open Qs
- [✅] `docs/TECHNICAL_REQUIREMENTS.md` (555 lines) — stack pending approval (D21)
- [✅] `docs/APP_FLOW.md` (738 lines) — flows A–H, 9 roles, mobile stock-visit
- [✅] `docs/DESIGN_BRIEF.md` (371 lines) — bilingual RTL, print rules
- [✅] `docs/DATABASE_SCHEMA.md` (308 lines) — 25 entities, E=C×(1−D), AR normalized, 40-row mapping
- [✅] `docs/IMPLEMENTATION_PLAN.md` (422 lines) — 8 phases, 7 gates, 11-stage migration
- [✅] Build-start gate: Eli approved 2026-10-16; stack = FastAPI/React/PostgreSQL/CF (pending swap).

## Phase 2 — Platform Foundation  [gate: 🔒 platform readiness]
- [✅] P2.1 Initialize git repo → commits `c5feebb`, `bd7b067`, `1fc5e97` (7 workbooks excluded from git)
- [✅] P2.2 docker-compose.yml (postgres:16 + app) + Dockerfile + .env.dev → committed
- [✅] P2.2b App boots: FastAPI `/health` → HTTP 200 {status:ok, phase:platform-foundation} (TestClient smoke)
- [✅] P2.2c DB reachable: `med_dms_db` healthy; `pg_isready` accepting connections
- [✅] P2.2d Initial platform schema applied: alembic rev `0001_platform` (head); tables `platform_user`/`platform_session`/`platform_setting` verified via `psql \d platform.platform_user` (uuid PK gen_random_uuid(), username UNIQUE, is_owner/is_active, timestamptz now()) — matches DATABASE_SCHEMA §2
- [✅] P2.3 Alembic scaffold + initial schema → `alembic/`, `alembic.ini`, `alembic/versions/0001_platform.py`
- [✅] P2.12 README local-dev setup → `README.md` (committed)
- [✅] P2.4 Auth module: login/me/logout + bearer sessions (24h TTL), INET-validated IP (TestClient "testclient"→NULL). 4/4 tests pass (438205b). app/auth/{router,repo,security,db}.py + tests/test_auth.py
- [✅] P2.5 RBAC: private/owner boundary — /owner/panel via require_owner; non-owner → 403, owner → 200. 6/6 tests pass. app/auth/rbac.py + tests/test_auth.py (D10).
- [✅] P2.6 Audit logger: immutable audit_log + log_audit(); login/logout audited. psql \dt audit.* → audit_log,reason_code; 2 rows (login+logout) verified (438205b). repo.log_audit; alembic 0002_audit_log
- [✅] P2.7 PWA shell: static shell served at /app (manifest+icon+sw.js cache-first), RTL index (dir=rtl/lang=ar), ar/en i18n key parity. 10/10 tests pass. web/ + tests/test_pwa.py (React SPA deferred).
- [⬜] P2.8 System settings scaffold (fiscal year, VAT, currency, numbering)
- [🔄] P2.9 Reason codes: audit.reason_code scaffold created + verified (psql \dt audit.* → reason_code; 438205b). Posting-status enum + import-validation scaffold deferred to Module C (sales_invoice).
- [⬜] P2.10 Global search scaffold
- [⬜] P2.11 Dev fixture loader (seed data matching Excel structure)
- [⬜] P2.12 README with local-dev setup → `README.md`
- Gate: CI green, platform tests pass, security model implemented, backup tested locally, login with RBAC works.

## Phase 3 — Business Modules A→H  [gate: 🔒 per-module]
- [⬜] Module A — Platform (continued): finalize cross-cutting concerns
- [⬜] Module B — Master Data (~2w): Customers, suppliers, employees(min), products, warehouses/branches, UOM(gated), agents, partners, COA, territories. Reconciliation vs source counts.
- [⬘] Module C — Sales (~3w): invoices/sell-in/VAT, HQ rollup (الرئيسية), sold balances (رصيد الارصدة المباعة), price lists (كامل الكمية), under-disposal (تحت التصريف), returns, credit. Net price `E=C×(1-D)` test. Pilot: Dakahlia branch.
- [⬜] Module D — Inventory (~2w): stock by warehouse, movements, batch+expiry, transfers. Reconcile per-warehouse stock.
- [⬜] Module E — Finance (~3w): Cash(النقديه), AR(العملاء 47×747), AP, GL, P&L(الارباح والخسائر), BS(الميزانيه/الموازنه العامه), assets. AR total 2,200,000 test.
- [⬜] Module F — Marketing (~1–2w): KOL/doctor spend, product/brand spend, objective/KPI, sales targets, overstock alerts.
- [⬘] Module G — Purchasing (~2w, discovery-gated): suppliers, PO/GRN; no MRP/BOM until D11 confirmed.
- [⬜] Module H — Analytics + Telegram (~3w): executive KPIs + Telegram bot (read-only first, whitelist). Pilot branch only.

## Phase 4 — Telegram  [gate: 🔒 Telegram functional]
- [⬜] T4.1 Whitelist/authorize Telegram users
- [⬜] T4.2 Read-only commands: balance, stock alerts, daily summary, app links
- [⬜] T4.3 Optional write actions only after security review + explicit approval
- [⬜] T4.4 Audit log all bot actions
- Gate: bot secure, authorized users only.

## Phase 5 — Production Migration  [gate: 🔒 migration sign-off]
- [⬜] M1–M11: 11-stage migration (see IMPLEMENTATION_PLAN §3) with reconciliation at each stage. Precision rule: no rounding financial values.
- Gate: all reconciliations pass; Eli signs off.

## Phase 6 — Go-Live  [gate: 🔒 go-live approval]
- [⬜] Production deploy to CEO-room PC host
- [⬜] DNS/tunnel (CF Tunnel), monitoring, training
- Gate: UAT signed off, remote access verified, Eli sign-off.

## Phase 7 — WhatsApp  [gate: ⏭️ future]
- [⏭️] Deferred — explicit cost/risk decision after production stable.

---

Progress updates: tick items with concrete evidence as work lands. This file is the single source of truth for "what's done" — check here before any assumption.
