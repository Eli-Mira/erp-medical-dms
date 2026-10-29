# Spec coverage matrix — current checkpoint 2026-10-21

## S8 online visit UI overlay — 2026-10-28

The existing AR/EN visit form is now an API-integrated candidate over accepted S7, not a replacement interface. For V2 2B.9–11 / APP_FLOW C7, create/read/delete, a latest unbatched opening-stock hint, exact server quantities, read-only/denied roles, paging, failure/retry and session teardown are exercised through the shipped PWA and real disposable PostgreSQL. The form records one product without a batch; historical batch-specific observations remain separate. Reported amounts do not post collections or change AR/company stock.

Local checkpoint acceptance is conditional on the exact-source native `s8_full_final` result, independent `FINAL_REVIEW.json`, and `COMMIT_RECEIPT.json` under `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/erp-visits-pwa-20261028/`. Counts come from its actual JUnit, not this note. Older localStorage-only statements below describe superseded snapshots, not the accepted checkpoint if its matching receipt exists.

Remaining: offline queue/conflict sync, installed-PWA/physical-device/staff UAT and batch selection in this form are not claimed. No financial-policy, import or production gate is closed here. Preserve the original device-only prototype data without automatic import. Existing global demo/network banner claims require their own scoped verification before staff readiness; a synthetic browser capture is not production acceptance.

## S7 backend overlay — 2026-10-27 (supersedes only the rows named here)

| Requirement | Current evidence-backed scope | Remaining product gap |
|---|---|---|
| V2 2B.9–11 / APP_FLOW C7 | Visits API, exact sell-through, scoped reads/writes, held-stock observations, audited atomic writes, and latest remaining visit projection are exercised by `s7_full_final` (803/0/0/0) and the included S7 API/durable controls. | Existing visit form is still a localStorage prototype. Persisted mobile UX and offline sync are NOT delivered. |
| V2 2B.7 | Scoped expiry-warning API: default/configured days, inclusive day 0/window end, excluded expired and out-of-window/zero-stock batches; existing batch API still exposes expiry records. | No new staff-facing expiry screen or physical-device acceptance in this checkpoint. |

Canonical private evidence and conditional local acceptance: `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/erp-s7-recovery-20261027T202217Z/{FULL_NATIVE_INTAKE.json,FINAL_REVIEW.json,COMMIT_RECEIPT.json}`. The full native run passed; acceptance requires matching final independent PASS and commit readback, never a commit subject or this note alone. Historical failed/uncontained attempts are not reclassified as accepted tests. All older missing/prototype statuses below remain historical where superseded; unrelated finance/import/production gates remain open.

Next dependency-ready gap after acceptance: connect the existing mobile-first visit form to these APIs and verify real persistence/session isolation in Arabic/English. Do not treat the confirmed backend slice as a completed employee workflow or select undefined accounting rules merely to keep coding.

## Execution-directive V2 checkpoint (supersedes stale status summaries below)

Inspection was resumed directly after the interrupted audit. Its retained trace (`deleg_cf6fc431/task-0.log`) ends with an explicit parent-requested interruption and no final artifact/verdict, not a diagnosed repository failure. Existing source, decisions and saved evidence were reused; no project restart, business-rule expansion or framework migration was undertaken.

Scope of VERIFIED here: the named local API/control and real PostgreSQL tests, not whole-product acceptance, fresh browser/device verification or production authorization. The first resumed full suite (`finite_full_final_20261021`) passed 429 cases with default posting OFF and its disposable database removed; exact final-source checkpoint evidence is recorded in the progress log after review. Older REAL/PROTO tables below are historical and must not be used as a current completion count.

| V2 # | Confirmed capability | Current classification | Concrete source / limit |
|---|---|---|---|
| 1 | Territory distinct from source warehouse | VERIFIED | `app/sales/router.py`, `tests/test_invoice_routing.py`; local API controls only |
| 2 | Approved warehouse-routing rules | VERIFIED | Same routing controls; fulfillment routes do not grant warehouse access |
| 3 | Warehouse transfers | PARTIAL | `app/transfers/router.py`, `tests/test_transfers.py`; live stock movements exist; destination-batch metadata conflict handling needs a targeted check |
| 4 | Zero-quantity print exclusion | UNVERIFIED | Existing PWA print implementation and prior browser evidence retained; no new print/browser pass in this checkpoint |
| 5 | Server-authoritative per-line VAT | VERIFIED | `app/sales/calc.py`, invoice/cycle tests; production rounding/tax-exception policy remains a separate gate |
| 6 | Batch tracking | VERIFIED | Inventory ledger/service and invoice batch validation; local synthetic tests |
| 7 | Expiry tracking and warnings | PARTIAL | `GET /inventory/batches` and invoice expiry checks exist; no new warning/print/device acceptance |
| 8 | Separate sell-in tracking | VERIFIED | Posted invoice quantities/stock/AR lifecycle in isolated tests; production posting remains OFF |
| 9 | Persisted sell-through tracking | MISSING | No backend sell-through storage/router found in `app/`; browser-only visit prototype is not persistence |
| 10 | Customer stock-visit workflow | PARTIAL | Existing PWA prototype; persisted, authorized backend workflow missing |
| 11 | Automatic sell-through calculation | PARTIAL | Existing prototype formula; server persistence/reconciliation remains missing |
| 12 | Explicit returns | PARTIAL | Owner-approved 1a: quarantined physical intake, no saleable restock; documented verified issue-cost snapshots and legacy `cost_unverified` flags. Native proof/receipt required by `docs/PROGRESS_CHECKLIST.md`. Approval, settlement, balanced journals and live VAT remain deferred/gated, not completed returns accounting. |
| 13 | Sales targets | VERIFIED | `app/sales/target_router.py`, `target_repo.py`, `tests/test_sales_targets.py`; existing approved monthly/unit scope |
| 14 | Stock cover | VERIFIED | `app/inventory/service.py::cover_report`, `tests/test_inventory_cover.py`; ledger-only computation |
| 15 | Overstock alerts | VERIFIED | Same cover report plus approved inventory-policy settings; no invented sales history |
| 16 | Doctor/KOL spend | PARTIAL | `app/marketing/router.py`, `tests/test_marketing.py`; spend API exists, not whole marketing acceptance |
| 17 | Product-linked spend | PARTIAL | Same API and `marketing_spend_product` join; no inferred product links |
| 18 | Objectives/results/KPIs | PARTIAL | `marketing_objective` API and tests exist; consolidated performance reporting remains incomplete |

| Cross-cutting capability | Classification | Evidence / remaining gate |
|---|---|---|
| Platform/auth/RBAC/audit/settings/search | PARTIAL | Actual routers and regression tests exist; no full-system security/release approval |
| Master data | PARTIAL | Real lookup APIs; complete approved CRUD/import/reconciliation not delivered |
| Finance/AR/collections | PARTIAL | Tested local atomic lifecycle; cash/BS/P&L/import depth and approved production policies remain open |
| Private/owner accounts | PARTIAL | `app/private_accounts/router.py`, owner-only tests; previous "missing backend" statements are stale |
| Durable production automation / OCR / Telegram | MISSING | No production job/receipt-ingestion subsystem accepted; do not use development agents as the job engine |
| WhatsApp business integration | BLOCKED | Separate feasibility/owner-approval gate; no real-chat access authorized |
| Hermes → OpenCode scoped coding proof | BLOCKED | Native v2.1.0 and three live text responses verified earlier. Isolated `.opencode/agents/lain-poc.md` was not discovered; bounded standalone diagnostic rejected its flag. No unsafe unrestricted coding fallback was launched |
| Project graph | UNVERIFIED | Existing `graphify-out/` retained unchanged; not rebuilt or counted as current evidence |
| Quarantined DB recovery / production posting | BLOCKED | `medical_dms` untouched; posting remains OFF |
| Publication/deployment/release | BLOCKED | No remote/push/merge/deployment; confidential-history cleanup, UAT, backup/restore and explicit release approval still required |

### Risk-ranked ready/backlog order

1. **Scoped source checkpoint committed:** non-finite numbers rejected by the four existing raw-dict quantity/money APIs; 20 exact 422/no-write regressions and full 429-case final-source suite passed. Commit `7b7bd64db4588bd6fc2dd7c7e10f6d72f2341c9f`; independent current-code judgment retained with explicit reviewer-method noncompliance in `FINITE_REVIEW_INTAKE.json`, not a whole-release or unqualified process approval.
2. **Next ready investigation:** prove that a transfer cannot silently merge conflicting source/destination batch expiry/manufacture metadata. Preserve all inventory/business rules; reject conflicts rather than silently overwriting batches.
3. **Core workflow:** persisted visit/sell-through and reconciliation/import slices require their complete approved data/period contracts before implementation. Do not infer accounting periods or duplicate sources.
4. **Harness:** resolve installed-version agent discovery/permission semantics before claiming scoped automatic coding. Continue independently authorized ERP work meanwhile.
5. **Approval-gated:** protected dependency changes for PDF/OCR/jobs, private-data ingestion, unresolved financial policy, quarantined-DB recovery, publication and deployment. Research references are not dependency or licensing approval.

---

## Historical coverage record (2026-10-18 onward)

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
| 3 | Warehouse→warehouse transfers (2B.3) | **REAL 2026-10-19** (`POST/GET /transfers`, two linked movements transfer_out/transfer_in, batch preserved in destination, no AR/revenue/territory side effects) | PROTO — principle text clean | COVERED (backend; PWA still PROTO) | — |
| 4 | Hide zero-qty invoice lines on print (2B.4) | n/a (presentation rule) | **REAL (presentation)** — print view on drafted invoice, zero-qty lines hidden in print, dimmed on screen; "Save as PDF" = real PDF file via browser (commit `08a4b11`, D45) | COVERED (browser print) | Server-side PDF library needs owner approval for protected `requirements.txt` (D45) |
| 5 | VAT per line, approved formula (2B.5) | REAL — `app/sales/calc.py` inclusive VAT, server-authoritative, snapshot on invoice | REAL — estimate tape + server totals | COVERED | — |
| 6 | Batch tracking (2B.6) | REAL-VALIDATION — batch locked/validated on invoice + movement lines; balances keyed by batch | REAL (stock/movements carry `batch_id`) | COVERED (no batch master read API — acceptable for prototype, note it) |
| 7 | Expiry tracking (2B.7) | **REAL 2026-10-19** (`expiry_date >= invoice_date` check + `GET /inventory/batches` FEFO read view) | PROTO — batches view shows expiry-sorted demo table with status column (expired blocked / near-expiry warning / fine), thresholds configurable | COVERED (backend read API; PWA still PROTO-consumes demo rows) | PWA batches screen can be switched to the real endpoint as a follow-up |
| 8 | Sell-in separate (2B.8) | REAL — invoiced quantities on invoices | REAL (home KPI derives ledger revenue) | COVERED | — |
| 9 | Sell-through separate (2B.9) | MISSING — no storage | PROTO-LOCAL (visits screen) | HOLE (backend) | Acceptable as labelled prototype |
| 10 | Customer stock-visit workflow (2B.10) | MISSING | **PROTO-LOCAL, interactive** — mobile form: per-product prev/delivered/returns/current + payment + notes | COVERED (as prototype) | Persistence is browser-only — must be labelled |
| 11 | Auto sell-through calc (2B.11) | n/a for prototype | REAL-in-prototype — exact formula `prev + delivered − returns − current`, live recompute, negative warnings | COVERED (formula must never change silently — V2 §2B.11) | — |
| 12 | Explicit returns (2B.12) | **REAL 2026-10-19** (`POST/GET /returns`, `sales.sales_return` + `return` movement increasing stock, never edits old invoice/balance) | PROTO — explicit-transaction principle stated | COVERED (backend; PWA still PROTO) | — |
| 13 | Sales targets (2B.13) | **REAL 2026-10-19** (`sales.sales_target` migration 0012; upsert endpoint + rep self-scoping; actuals from posted lines only) | PROTO — rep/territory/product/period vs actual, role-visible scoping stated | COVERED (frontend PROTO + backend model: rep + optional product + month, units; owner decision 2026-10-19) | Actuals read null until posting goes live (by design) |
| 14 | Stock cover (2B.14) | **REAL 2026-10-19** (`GET /inventory/cover`; openings + posted lines only; no_sales_history until posting goes live) | PROTO — 30-day rolling window default (D41) stated, per-product reorder threshold configurable (UQ-5) | COVERED (frontend PROTO + backend real-ledger computation) | Actual sales still empty while posting stays OFF (by design) |
| 15 | Overstock alerts (2B.15) | **REAL 2026-10-19** (same endpoint, `overstock` status = cover > configurable threshold) | PROTO — 180-day default threshold (D41), clearance-warehouse action stated | COVERED (same as 2B.14) | Same as 2B.14 |
| 16 | Doctor/KOL spend (2B.16) | **REAL 2026-10-19** (`POST/GET /marketing/spend`, `marketing.marketing_spend` + product join, no free-text product inference) + directory | PROTO — structured spend table bound to real directory | COVERED (backend; PWA still PROTO) | — |
| 17 | Product/brand-linked spend (2B.17) | **REAL 2026-10-19** (join table `marketing.marketing_spend_product`) | PROTO — structured table | COVERED (backend) | — |
| 18 | Marketing objective + result/KPI (2B.18) | **REAL 2026-10-19** (`POST/GET /marketing/objectives`) | PROTO — objectives/KPI/actual/follow-up table | COVERED (backend; PWA still PROTO) | — |

**Net §2B status (2026-10-19): 8 fully covered (1,2,4-presentation,5,6,8,10,11), 6 hole-as-backend-but-present-as-labelled-prototype (3,9,12,13,14,15), 4 partial (7,16,17,18) — remaining demo-visible work is backend slices; every presentation-level hole now has a company-correct labelled prototype.**

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
3. ~~Unverifiable coverage claims~~ RESOLVED 2026-10-18: `docs/evidence/invoice-cycle/client-proto-fix-20261018/` now exists with real artifacts (`pytest.log`: **345 passed, 1 warning**, disposable DB `dms_cycle_test_480…`, `POSTING_ENABLED=false` verified in `run.json`). Remaining ~~nit~~: pointer fixed 2026-10-19 — `docs/REQUIREMENTS_COVERAGE.md` now cites the real artifacts.
4. **Missing representative screen** while the owner's list explicitly requires it.

## 5. Recommended build order (client prototype completeness, one slice at a time)

1. Fix garbled/corrupt PROTON content + commit current prototype state to `feature/client-prototype`.
2. Upgrade §2B holes that are presentation-level: transfers (3), returns (12) principle, targets (13), stock cover (14) + overstock (15), brand spend (17), objectives/KPI (18), expiry view (7) — all as honest labelled prototypes with company-correct wording.
3. Add missing master-data screens: representatives & assignments; private accounts (flag security boundary first).
4. Print/PDF for invoices honoring zero-quantity hiding (2B.4).
5. ~~Backend slices~~ invoice list/search API **DONE 2026-10-19**: `GET /invoices` with customer/status/date filters + pagination, scoping mirroring single-fetch grants (territory `ANY`, rep own-created, auditor posted-only), header snapshots without lines; **351 passed** via the verified runner (`docs/evidence/invoice-cycle/invoice_list_search_20261019/`), and the PWA gained a REAL "Invoice list" screen consuming it. Batch/expiry read view **DONE 2026-10-19**: `GET /inventory/batches` FEFO-ordered with on-hand quantity (LEFT JOIN keeps zero-balance batches visible), branch scoping + 403 (`inventory_batches_read_b_20261019/`). Stock cover + overstock **DONE 2026-10-19**: `GET /inventory/cover` computes cover days from real ledgers only (openings + posted invoice lines), window/threshold from `platform_setting` via `GET/PUT /settings/inventory-policy` (D41 defaults 30/180), honest `no_sales_history` state while posting is off (`settings_policy_b_20261019/`, `cover_report_b_20261019/`); **365 passed**. Sales-targets model **DONE 2026-10-19**: migration `0012_sales_targets` (`sales.sales_target`, rep + optional product + month, partial unique indexes for whole-book vs product rows), `GET/POST /targets` with medical-rep self-scoping and actual-vs-target from posted lines; **371 passed** (`sales_targets_c_20261019/`). Owner decision 2026-10-19: monthly + units; territory/value roll-ups computable from rep assignments..
6. Reconciliation/import engine follows the approved migration plan (V1 §12) — never proto that.

**Rule for every step:** nothing moves from PROTO to REAL without: real POSTgreSQL slice test via the approved runner + posted evidence directory that actually exists.
