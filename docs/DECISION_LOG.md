# DECISION_LOG.md

**Purpose:** Chronological record of every decision that shapes the Medical Company System, with source. Later sessions check this before contradicting an earlier decision. Supersessions are marked.

## 2026-10-10 — Spec baseline
- **D1.** `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` is **authoritative**; V1 kept for reference. (V2 header)
- **D2.** Build a **custom system**; ERPNext and other open-source ERPs are **references only**, not the application base. (V2 §2)
- **D3.** **PostgreSQL** database; responsive web app / PWA (desktop + mobile). (V2 §2)
- **D4.** **Zero-cost / open-source-first** budget — non-negotiable unless Eli changes it. (V2 §2)
- **D5.** Host on the **existing always-on CEO-room PC**; must support users **outside the office network**; PostgreSQL never exposed publicly. (V2 §2, §8)
- **D6.** **Telegram before WhatsApp**; WhatsApp is a later phase and must not block the core. (V2 §2, §9)
- **D7.** Excel workbooks are the **operational source of truth**; full spreadsheet archaeology before any schema/feature design; no guessing. (V2 §1, §4)
- **D8.** Every discovered capability gets a status: KEEP / IMPROVE / REPLACE / DEPRECATE_PENDING_APPROVAL / UNKNOWN_NEEDS_INTERVIEW. (V2 §4)

## 2026-10-11 — Eli's answers (`C:\Users\emadg\CrossDevice\Desktop\Answers.txt`)
- **D9.** **Payroll = lightweight**: salary records/payments only. No HR/attendance/leave/taxes/payroll formulas unless the real workflow proves need.
- **D10.** **Private/Owner Accounts**: same PostgreSQL DB, **separate protected module/security boundary** — separate permissions, restricted queries, audit logs, ideally separate schema/tables. No second database.
- **D11.** **Purchasing/Raw Materials/Manufacturing**: include the **real existing data/workflows**, built progressively. No full MRP/BOM/PO/GRN systems until discovery proves they are used.
- **D12.** Modules **unused in Excel are not core migration scope** — but platform capabilities that Excel lacks (security, approvals, audit, settings, alerts, import validation, global search, integrations) **still belong in the system**.
- **D13.** **UOM**: box/pack/unit conversions only if real operations use them.
- **D14.** Module list additions to account for before Step 0: System Settings (fiscal year, VAT, company info, currency, numbering), Credit Management (limits, holds, aging, override), Simple Approvals (returns, discounts, price overrides, expenses, stock adjustments, transfers), Integration Settings (Telegram first), Private Accounts Security, Master Data (products, warehouses, territories, reps, districts, specialties, categories, payment methods), Posting Status (Draft→Posted→Voided), Reason Codes, Alerts (low stock, overstock, near expiry, overdue, credit-limit), Audit Timeline, Import Validation (preview, duplicates, rejected rows, reconciliation), Global Search.
- **D15.** Keep `MODULE_MAP.md` (high-level) and `EXCEL_TO_SYSTEM_MAPPING.md` (detailed) as **separate, cross-linked** documents; `IMPLEMENTATION_PLAN.md` = build order.

## 2026-10-12 — Discovery phase (Phase 0) completed
- **D16.** All 7 workbooks inventoried (361 sheets); SHA-256 baseline frozen in `docs/SOURCE_HASHES.txt` (immutable).
- **D17.** **Branch scoping**: 5 sales workbooks = 5 branches (6 أكتوبر، الدقهليه، الشرقية، الغربية، الفيوم). Same-named sheets are branch-scoped; key everything by `(workbook, sheet)`.
- **D18.** Business rules preserved as logic (not guessed): net price `E=C*(1-D)`; payroll net `E=B-C-D`; AR running balance `D=prev+E−F`; rollups via cross-sheet refs; `SUMIFS` cumulative-by-item.
- **D19.** Placeholders (53 unnamed sheets) **excluded from import unless confirmed** business-relevant.
- **D20.** Discovery-gated (not built until confirmed): deeper Payroll HR, Purchasing/Raw Materials/BOM/MRP depth, Budgeting, UOM beyond implicit.

## 2026-10-16 — Evidence resolutions (this session)
- **D21.** **External links resolved**: 15 links total. 14 point to the 6 sibling workbooks (all present in folder; stale `E:\حسابات جديده 2025\...` path). 1 points to `متابعة مبيعات المنصورة الجديده.xlsx` (**not provided**). Consolidation (`اجمالى الحسابات`) is **recomputed at import from local copies**; the Mansoura link is flagged broken and never blocks other modules.
- **D22.** **Placeholders resolved by sampling**: `ورقة1 (NN)`/`Sheet2` series are **duplicate copies** of transaction sheets (40/40 identical to each other; 3–4/40 vs named sheets) → excluded from MVP import, flagged as possible historical data. `Sheet1` in `حسابات خاصه` = **doctor/KOL list** (included as master data). `Sheet1` in `مبيعات الفيوم` = **warehouse withdrawal totals** (included).
- **D23.** **AR ledger decoded**: `العملاء` (47×747) = ~48 customer blocks × 6 columns (`الرصيد`, `مدين`, `دائن`, `البيان`, `المندوب`, `التاريخ`), transactions down rows; row-1 total 2,200,000. Model = **normalized AR entries**; the wide layout is a pivot.
- **D24.** **Budgeting = out of scope** (not a V2 confirmed feature; D12). P&L + Balance Sheet reporting (spec item 30) is the finance reporting scope.
- **D25.** **Source integrity verified**: all 7 SHA-256 hashes re-checked 2026-10-16 — identical to baseline. No source modification during discovery.
- **D26.** **All OPEN_QUESTIONS resolved** — Phase 0 gates cleared; project ready for Phase 1 (six planning documents).

## 2026-10-16 — OpenCode session context (recovered from `opencode.db`)
Source: OpenCode session `ses_ed7b1d6dfffeosaSErmAIeRpaf` ("Sufficient docs check for Huge system folder"), the session that produced the discovery docs. Recovered because OpenCode's own tracking was unreliable (stale todos, slow, little progress).

- **D27. Step 0 approval conditions (Eli, 4 final edits):** (1) Payroll = CONFIRMED lightweight, deeper discovery-gated; (2) Purchasing/Manufacturing = CONFIRMED activity exists, PO/GRN/BOM/MRP depth discovery-gated; (3) Finance = P&L + Balance Sheet reporting, Budgeting discovery-gated; (4) replace "No blockers remain" with "No known blockers remain. Any new ambiguity goes into OPEN_QUESTIONS.md and must not be guessed." Build order A→H confirmed.
- **D28. Per-module reporting rule (Eli):** basic reports/analytics are built **inside each module as it is completed** — never postponed to module H. H covers only cross-module executive analytics + Telegram.
- **D29. Verification directive (Eli, final message):** "Never assume something is done without verifying and making sure it really exists and fully implemented and finished. Make sure you are not creating things that don't exist in the main Excel sheets and the files in the project folder." → Every claim must be checked against the actual workbook evidence; no invented entities/features.
- **D30. Module status tags (from Step 0 plan):** A Platform (Auth/RBAC, Settings, Org structure, Posting, Reason Codes, Approvals, Audit, Private/Owner boundary, Integration, Search, Alerts, Import Validation, PWA) · B Master Data (Customers, Products/Catalog/Pricing, Reference sets, Batches & Expiry, UOM gated, Credit Management) · C Sales (Invoices/sell-in/print rules/VAT, Warehouse routing/transfers, Returns, Collections/Receivables/Statements, Sales targets, Stock visits + sell-through) · D Inventory (Stock ledger/balances, Stock cover/overstock/low-stock) · E Finance (Treasury/Cash + Bank, Expenses/Revenue, P&L+BS reporting, Payroll lightweight, Private/owner accounts isolated) · F Marketing (KOL/doctor spend, Product/brand spend + objective/KPI/ROI) · G Purchasing (Suppliers/material purchases/manufacturing costs/stock movements; PO/GRN/BOM/MRP gated) · H Analytics (Cross-module executive dashboard/KPIs + Telegram; WhatsApp later).

- **D31.** **Phase-1 planning package complete (2026-10-16).** All six core docs verified present and D29-clean: `PRD.md` (390), `TECHNICAL_REQUIREMENTS.md` (555), `APP_FLOW.md` (738), `DESIGN_BRIEF.md` (371), `DATABASE_SCHEMA.md` (308), `IMPLEMENTATION_PLAN.md` (422). Sources untouched (D25). Build-start gate is the next blocker: requires Eli's approval of all six docs + security model + stack (D21) + 9-role split (UQ-1) + backup/dependency policy/pilot scope/acceptance (V2 §20) before ANY Phase-2 code.
| **D32.** **Subagent reliability caveat:** 2/6 delegated docs failed on raw output — `APP_FLOW.md` was written to a wrong working directory (`Desktop/💻 Dev Corner/docs`, not the project) and `DATABASE_SCHEMA.md` aborted once on a dropped connection. Both recovered and relocated/rewritten, but this confirms the D29 rule: verify file existence before trusting a subagent's summary.
The latest implemented local-only slice is recorded in `docs/INVOICE_SLICE_1.md` (2026-10-17): draft invoice API plus audit and scope controls; real posting remains blocked. Earlier implementation/schema verification claims do not approve production or establish the still-unverified payroll and invoice-rounding rules.

**D38.** **AR ledger + atomic posting transaction (2026-10-17).** `finance.ar_entry` (balance = Σdebit − Σcredit, matching Excel العملاء) and `platform.user_branch` (minimum user→branch mapping; territories and warehouses stay distinct, shared warehouses are handled by branch scope) added in migrations `0006`/`0007`. `post_invoice_atomic` performs stock decrement + AR debit + Posted flip in one transaction and is covered by `tests/test_posting.py`, but `POST /invoices/{id}/post` still returns 409 — posting is enabled only by wiring the endpoint after sign-off. The "no Posted rows ever" DB constraint was replaced by `ck_invoice_posting_status` + `ck_invoice_posted_at` (a Posted row must carry `posted_at`). ERPNext remains reference-only (D2); no ERPNext code or dependency was introduced. See `docs/AR_SLICE.md`.

If a later decision contradicts an earlier one, the later entry wins and must reference the superseded decision ID. Eli's explicit instructions always override inferred ones.

## 2026-10-16 — Eli's UQ decisions (critical blockers resolved)
- **D34 (UQ-1 Roles).** Role list = **Owner, Admin, Finance, Sales Manager, District Manager, Medical Rep, Warehouse Staff, Read-Only Auditor**. Access restricted by **responsibility + assigned territory**. (Eli, 2026-10-16)
- **D35 (UQ-2 AR).** AR = **transaction-level ledger + monthly summaries**. **Preserve opening balances and historical transactions.** (Eli, 2026-10-16)
- **D36 (UQ-8 VAT).** Use the existing invoice's **14% VAT-inclusive** calculation for applicable products. **Tax rates configurable per product**; **verify exceptions before production**. (Eli, 2026-10-16)
- **D37 (UQ-11 Stack).** **FastAPI + PostgreSQL + psycopg3 + existing vanilla JS/PWA.** Do **not** rewrite the frontend in React unless complexity justifies it. **Hosting OS deferred** until the server PC is inspected — must not block local development. (Eli, 2026-10-16)

## 2026-10-18 — B Master Data slice (local-only)
- **D39. B Master Data slice.** Three master tables confirmed by the planning docs but absent from every migration are now implemented, with **no invented accounting or business policy**. Details in `docs/PROGRESS_CHECKLIST.md` and the stage report under `docs/evidence/invoice-cycle/`.
  - **D39a Suppliers** — `master_data.master_supplier` (PRD B-02 / G-01, D11: real purchasing activity exists; PO/GRN depth stays gated). The planning column `status` is realized as the implemented `is_active` soft-delete flag used by every other master table (DATABASE_SCHEMA §13).
  - **D39b Minimal chart of accounts** — `finance.coa_account` (PRD B-12 / E-05, D13). Only the five fundamental account types are constrained (`asset`/`liability`/`equity`/`revenue`/`expense`; AR, AP and Cash are accounts under those types). **No account codes or names are seeded**: the workbook evidence holds a P&L/BS structure, not a coded chart of accounts, so seeding one would invent accounting structure (D29). Which accounts to load, and whether the COA is branch-scoped, remain open business-policy questions.
  - **D39c Doctor/KOL list** — `marketing.marketing_kol` (PRD B-13, D22: `حسابات خاصه.xlsx::Sheet1`). Specialty stays an inline attribute because the authoritative schema defines no specialty master table; no specialty or area taxonomy was invented (`Sheet1`'s `المنطقة`/`التخصص` values are not yet mapped to branches/territories).
  - **D39d Access** — read-only `GET /master/suppliers|accounts|doctors`. Suppliers and the COA are limited to `owner`/`finance`/`read_only_auditor`; doctors to `owner`/`sales_manager`/`district_manager`/`medical_rep`/`read_only_auditor`, branch-scoped through `platform.user_branch` for non-global callers. Territory, branch and warehouse grants stay distinct; no purchasing or marketing role was invented (D34).
  - **D39e Gated / not built** — UOM conversion stays gated (D13/D20): no `master_uom` was created. No CRUD, import, or write endpoint, and no real supplier, doctor, or financial record was loaded (synthetic test rows only). `POSTING_ENABLED` stays OFF.
