# Spec coverage matrix — verified 2026-10-18

**Purpose:** an honest, evidence-backed matrix of the ENTIRE spec (`MEDICAL_COMPANY_SYSTEM_MASTER_SPEC.md` V1
+ `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`) against this system, merged with the owner's own missing-coverage
list (master data / collections / finance / reporting / data & integrations / application).

**Method (D29 — verify, never assume):** every status below was checked against real code on
2026-10-18, branch `feature/client-prototype` (HEAD `f0f1ed8`, plus uncommitted working tree):
backend = all 26 registered routes enumerated from `app/` routers; frontend = screen-by-screen audit of
`web/index.html` + `web/app.js`. Nothing here is taken from a prior agent's summary.

**Reminder this doc exists for:** V1 §5 — "Never silently omit something because it looks redundant",
and V2 §2B — all 18 confirmed features are CONFIRMED FROM REAL WORKFLOW. A client-facing prototype must
not ship while any §2B item is absent or misrepresented.

## Legend

| Status | Meaning |
|---|---|
| **REAL** | Live backend endpoint wired to real PostgreSQL tables |
| **REAL-VALIDATION** | Server enforces the rule during posting/validation (no separate read UI) |
| **PROTO** | Labelled prototype screen ("نموذج أولي / Prototype"), no API |
| **PROTO-LOCAL** | Interactive prototype, state in browser localStorage only |
| **GATED** | Backend exists and works, intentionally blocked by `POSTING_ENABLED=OFF` (HTTP 409) — by design, not a gap |
| **MISSING** | No code on server or client — honest gap |
| **DEFERRED** | Postponed by a recorded decision (D6: Telegram/WhatsApp after core) |

## Status sources verified on 2026-10-18

- Backend: 26 routes across `auth`, `rbac`, `invoices` (6), `inventory` (3), `ar` (3), `collections` (4), `master` (7). `POSTING_ENABLED` gates: invoice post, invoice reverse, collections create, receipt void → 409 while OFF.
- Frontend: 14 REAL screens (home, invoice, draft, inventory, ledger, balances, collections, customers, products, warehouses, suppliers, accounts, doctors, PWA/auth) + interactive visits screen + 20+ PROTON prototype views.
- Batch/expiry server validation exists: `inventory.batch_record` locked with `FOR SHARE` in `sales/router.py:158-176` (product/warehouse match, `expiry_date >= invoice_date`); stock balances keyed `(warehouse, product, batch)` in `inventory/service.py`.
- Missing backend confirmed explicitly for: batch master list, sell-through storage, returns, transfers, targets, stock-cover, overstock, marketing spend, cash/bank, expenses, P&L, payroll, POs, settings, audit read, alerts, invoice list/search.

---

## 1. V2 confirmed features (§2B.1–2B.18) — the client-demo contract

| # | Feature (V2 §2B) | Backend | Frontend | Demo status | Honest gap |
|---|---|---|---|---|---|
| 1 | Territory ≠ source warehouse (2B.1) | REAL — separate fields enforced server-side (sales routing slice `c50bb02`) | REAL — invoice form collects both | COVERED | — |
| 2 | Warehouse-routing rules (2B.2) | REAL — routing decoupled from territory, grants via `platform.user_branch` | REAL — warehouse options re-fetched per customer branch | COVERED | — |
| 3 | Warehouse→warehouse transfers (2B.3) | MISSING (only generic `POST /inventory/movements`) | PROTO (garbled text — see §5) | HOLE | Needs PROTO upgrade + future endpoint; must keep transfer≠sale |
| 4 | Hide zero-qty invoice lines on print (2B.4) | n/a (presentation rule) | **MISSING — no print/PDF path at all** | HOLE | Needs print view honoring the rule |
| 5 | VAT per line, approved formula (2B.5) | REAL — `app/sales/calc.py` inclusive VAT, server-authoritative, snapshot on invoice | REAL — estimate tape + server totals | COVERED | — |
| 6 | Batch tracking (2B.6) | REAL-VALIDATION — batch locked/validated on invoice + movement lines; balances keyed by batch | REAL (stock/movements carry `batch_id`) | COVERED (no batch master read API — acceptable for prototype, note it) |
| 7 | Expiry tracking (2B.7) | REAL-VALIDATION — `expiry_date >= invoice_date` check | PARTIAL — expiry not surfaced in views | HOLE (small) | Expiry view / warning screen |
| 8 | Sell-in separate (2B.8) | REAL — invoiced quantities on invoices | REAL (home KPI derives ledger revenue) | COVERED | — |
| 9 | Sell-through separate (2B.9) | MISSING — no storage | PROTO-LOCAL (visits screen) | HOLE (backend) | Acceptable as labelled prototype |
| 10 | Customer stock-visit workflow (2B.10) | MISSING | **PROTO-LOCAL, interactive** — mobile form: per-product prev/delivered/returns/current + payment + notes | COVERED (as prototype) | Persistence is browser-only — must be labelled |
| 11 | Auto sell-through calc (2B.11) | n/a for prototype | REAL-in-prototype — exact formula `prev + delivered − returns − current`, live recompute, negative warnings | COVERED (formula must never change silently — V2 §2B.11) | — |
| 12 | Explicit returns (2B.12) | MISSING | PROTO only | HOLE | Needs PROTO upgrade to show the explicit-transaction principle (never edit old invoices) |
| 13 | Sales targets (2B.13) | MISSING | PROTO only | HOLE | Rep/territory/product/period target vs actual |
| 14 | Stock cover (2B.14) | MISSING | PROTO sample row | HOLE | `stock ÷ recent avg sales rate`, configurable window |
| 15 | Overstock alerts (2B.15) | MISSING | PROTO sample row | HOLE | Configurable threshold, never hardcoded |
| 16 | Doctor/KOL spend (2B.16) | REAL (directory `/master/doctors`), spend ledger MISSING | PROTO preview inline in doctors screen | PARTIAL | Spend linking (specialty/area/date/amount/activity) |
| 17 | Product/brand-linked spend (2B.17) | MISSING | PROTO screen | HOLE | Explicit product/brand link, no free-text inference |
| 18 | Marketing objective + result/KPI (2B.18) | MISSING | PROTO screen | HOLE | Objective/KPI/actual/follow-up fields |

**Net §2B status: 7 fully covered, 6 hole-as-backend-but-present-as-labelled-prototype, 5 real holes (3 transfers, 4 print, 16/17/18 marketing spine).**

## 2. Owner's missing-coverage list (merged with evidence)

| Area | Item | Verified status |
|---|---|---|
| Master data | Customers, products | REAL (read-only directories with search); create/edit MISSING backend |
| Master data | Representatives & assignments | PROTO — `representatives` screen added 2026-10-18 (`web/app.js` `PROTON.representatives`); backend still MISSING |
| Master data | Pricing & discount rules | PARTIAL — invoice lines accept discount %; no pricing tiers (B2) |
| Collections | Payment recording | GATED — backend complete, 409 while `POSTING_ENABLED=OFF` (by design) |
| Collections | Outstanding balances | REAL — `/ar/balances` + aging strip (0-30/31-60/61-90/90+) |
| Collections | Customer statements | REAL (live ledger card from `/ar/entries`); export/PDF MISSING |
| Finance | Cash/bank, expenses, revenue | PROTO screens only; backend MISSING |
| Finance | Accounting reports (P&L, balance sheet) | PROTO screens only; backend MISSING |
| Finance | Payroll | PROTO sample row; backend MISSING |
| Finance | Private accounts (`حسابات خاصه`) | PROTO — `privateaccounts` screen added 2026-10-18, view-only, owner-only. **Boundary decision recorded as D40** (same PostgreSQL DB, separate protected module/schema). Backend slice intentionally unstarted; must deliver schema+permissions+audit before any real row |
| Reporting | Consolidated sales, territory/rep/product performance | PARTIAL — Home KPIs from real ledgers; per-territory/rep/product aggregates MISSING |
| Reporting | Low-stock alerts | PROTO screen; backend MISSING |
| Data | Excel import/export | PROTO import screen only; real import/extract engine MISSING (discovery tooling only) |
| Data | Reconciliation | Plan + hashes exist (`SOURCE_HASHES.txt`, spec §12); runnable reconciliation MISSING |
| Data | Telegram | PROTO screen; DEFERRED backend (D6: after core modules) |
| Application | Role permissions | REAL — RBAC server-side (9 roles, D34) + client-side `data-roles` nav gating |
| Application | Audit history | WRITE-side REAL (audit rows bound to actor in same transaction); read API + PROTO screen = MISSING backend |
| Application | Desktop/mobile usability | REAL responsive (`@media`, 44px targets, card fallback); no physical-device test pass recorded |
| Application | Remote access | PARTIAL — Cloudflare quick tunnel committed (`f0f1ed8`); explicitly temporary (V1 §8: not production hostname) |

## 3. §2C critical distinctions — where each is enforced

| Distinction | Enforced where |
|---|---|
| Territory ≠ Warehouse | REAL — separate columns, routing tests, invoice UI |
| Warehouse stock ≠ Customer-held stock | REAL in model (separate ledgers); sell-present only as prototype visitor fields |
| Sell-in ≠ Sell-through | NAME only — no sell-through storage yet (proto labels it) |
| Sale ≠ Collection | REAL — separate frozen tables; `_entry_type='invoice'` AR link |
| Transfer ≠ Sale | Not enforceable yet — no transfer entity (must land with the transfer module) |
| Invoice ≠ Payment | REAL — separate tables + trigger-immutability |
| Product ≠ Batch | REAL — `batch_record` separate, balances keyed by batch |

## 4. §5 client-demo blockers (found during audit — must fix before giving anything to the client)

1. **Uncommitted work:** ~2,900 lines across `web/app.js`, `web/index.html`, `web/styles.css`, `scripts/make_demo.py` uncommitted on `feature/client-prototype`. Commit to the feature branch (never `master`, never push) so nothing is lost.
2. ~~Corrupted PROTON strings~~ FIXED 2026-10-18: five garbled Arabic strings corrected and mixed-script leftovers swept (`grep -nP "\p{Arabic}\p{Ll}"` clean); `representatives` + `privateaccounts` prototype screens added; `node --check` + JSON validation pass.
3. ~~Unverifiable coverage claims~~ RESOLVED 2026-10-18: `docs/evidence/invoice-cycle/client-proto-fix-20261018/` now exists with real artifacts (`pytest.log`: **345 passed, 1 warning**, disposable DB `dms_cycle_test_480…`, `POSTING_ENABLED=false` verified in `run.json`). Remaining nit: `docs/REQUIREMENTS_COVERAGE.md` cites a `SUMMARY.md` in that directory that was never written — cite `pytest.log`/`run.json` instead.
4. **Missing representative screen** while the owner's list explicitly requires it.

## 5. Recommended build order (client prototype completeness, one slice at a time)

1. Fix garbled/corrupt PROTON content + commit current prototype state to `feature/client-prototype`.
2. Upgrade §2B holes that are presentation-level: transfers (3), returns (12) principle, targets (13), stock cover (14) + overstock (15), brand spend (17), objectives/KPI (18), expiry view (7) — all as honest labelled prototypes with company-correct wording.
3. Add missing master-data screens: representatives & assignments; private accounts (flag security boundary first).
4. Print/PDF for invoices honoring zero-quantity hiding (2B.4).
5. Backend slices (not prototype scope): invoice list/search API, batch/expiry read views, then targets/cover/overstock from real ledgers — each behind its own verified slice + disposable-DB tests.
6. Reconciliation/import engine follows the approved migration plan (V1 §12) — never proto that.

**Rule for every step:** nothing moves from PROTO to REAL without: real POSTgreSQL slice test via the approved runner + posted evidence directory that actually exists.
