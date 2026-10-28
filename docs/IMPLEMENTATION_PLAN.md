# IMPLEMENTATION PLAN — Medical Company System

> Authoritative references: `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`, `MODULE_MAP.md`, `MIGRATION_RECONCILIATION_PLAN.md`, `DECISION_LOG.md` (D1–D46), `OPEN_QUESTIONS.md`, `EXCEL_TO_SYSTEM_MAPPING.md`, `DATA_DICTIONARY.md`, `CURRENT_WORKFLOWS.md`, `docs/AUDIT_VS_WORKBOOKS.md`.
>
> Status: Phase 0 discovery complete. Phases 2–4 partially delivered (local API slices + PWA). Stack is FastAPI + PostgreSQL + psycopg3 + vanilla JS/PWA (D37, D46). No framework migration.
>
> Planning/documentation only in this revision. No feature implementation, framework migration, production change or workbook edit is performed here.

## 1. Current state (verified)

- **Implemented:** auth/sessions/RBAC, audit (write+read), PWA shell (RTL, i18n), invoice desk (draft), invoice list/search, inventory (stock/movements/batches/cover/overstock), AR balances/collections/ledger, transfers, returns, targets, marketing spend/objectives, settings (inventory policy), master data (branches/customers/products/warehouses/suppliers/COA/doctors), synthetic demo DB (`medical_demo`), real-browser Playwright verification (desktop 1440×900 + mobile 390×844 emulation).
- **Partial:** PWA screens for transfers/returns/marketing (REAL, consume live endpoints); print/PDF (browser print only); visits (PROTO); master reps/UOM/credit (PROTO, hidden from nav).
- **Missing:** reconciliation/import engine (V1 §12), HQ rollups, cross-workbook consolidation, BS/P&L/cash/expenses/assets reports, private accounts module (D40), global search (P2.10), reason codes (P2.9), dev fixture loader (P2.11), server-side PDF (D45).
- **Deferred (discovery-gated):** payroll depth, purchasing/PO/GRN, budgeting, UOM, credit terms (UQ-5/6/9).
- **Unapproved (Phase-4 scope decision):** cash/bank, expenses, P&L, payroll, POs beyond workbook evidence.
- **Gates:** `POSTING_ENABLED=False` (hard rule 1). `medical_dms` quarantined (hard rule 2). Source workbooks read-only (hard rule 3). Independent review held (NO_VERDICT) on invoice cycle.
- **Tests:** 383 passed via approved runner on disposable `dms_cycle_test_*` DBs; 1 inherited warning; ruff clean on changed files.

## 2. Phase plan

### Phase A — Daily workflows (already largely implemented; verify + close gaps)
Outcome: owner/rep can find customer, view invoices/collections/balance, create/save/reopen draft, view stock by warehouse, print invoice, all on desktop+mobile.

| # | Task | Priority | User outcome | Source / approved | Gap | Smallest change / deps | Acceptance check |
|---|---|---|---|---|---|---|---|
| A1 | Verify draft create/save/reopen in browser | P1 | Rep creates draft and reopens it | V2 §2B.4, D45 | UI not verified until Playwright pass | Playwright script (done) | Screenshot + POST 201 + GET reopen shows lines/totals |
| A2 | Verify customer→invoices→balance match by ID | P1 | No wrong-customer data | D29 | First-row assumption risk | Filter by customer_id (done) | Invoice list filtered by selected customer_id; balance row matched by id |
| A3 | Verify print layout + zero-qty exclusion | P1 | Printable invoice | V2 §2B.4, D45 | Visual check pending | Browser print emulation (done) | `@media print` hides zero-qty; totals correct |
| A4 | Consolidate nav to 5 task groups | P1 | Less clutter, mobile usable | D44, product simplicity | Proto screens cluttered nav | Hide proto nav items (done) | Only REAL screens visible; 5 groups |
| A5 | Lighthouse pass on REAL screens | P2 | Performance baseline | — | Not run | Run lighthouse (blocked: no Chrome) | Score recorded or blocker named |
| A6 | R-35 click-through evidence (all REAL screens) | P2 | Demo evidence | Client demo | Partial | Manual browser pass | Screenshots committed |

### Phase B — Data loading, isolated import dry runs and reconciliation
Outcome: master data and historical transactions imported from workbooks into a disposable DB with verified reconciliation; HQ rollups reproduced.

| # | Task | Priority | User outcome | Source / approved | Gap | Smallest change / deps | Acceptance check |
|---|---|---|---|---|---|---|---|
| B1 | Import dry run: branches/territories/warehouses/customers/products (P2) | P1 | Real master data in system | V1 §12 P2; workbooks (read-only) | No importer yet | Build read-only importer against `dms_cycle_test_*` only | Row counts match workbook; no source file writes |
| B2 | Import dry run: stock balances + movements | P1 | Stock matches Excel | V1 §12 P4 | No importer | Add opening movements with batch/expiry | Balance totals match per warehouse |
| B3 | Import dry run: posted invoices + lines (E=C*(1-D)) | P1 | Sales history | V1 §12 P4; Excel formulas | No importer | Preserve net-price formula | Header totals reconcile to lines |
| B4 | Import dry run: AR entries + receipts | P1 | Receivables match | V1 §12 P5; 747-col AR sheet | No importer; period mapping UNVERIFIED | Map customer blocks → entries | Debit-credit sums match |
| B5 | HQ rollup reproduction (`الرئيسية`) | P2 | Branch totals verified | V1 §12 P4 | Not implemented | Recompute from per-warehouse sheets; compare | Tolerance 0 on sampled rows |
| B6 | Cross-workbook consolidation (`اجمالى الحسابات`) | P2 | Consolidated view | V1 §12 P6 | Blocked on missing Mansoura workbook | Flag broken link; import others | Clear error logged; others imported |
| B7 | Sell-through import (`رصيد الارصدة المباعة`) | P2 | Sell-through visible | V2 §2B.9 | Not imported | Import customer-held stock | Formula preserved |
| B8 | BS/P&L/cash/expenses/assets reports | P2 | Finance reports | `الميزانية العمومية 2026` sheets | Not built | Build read views from imported data | Totals reconcile to Excel samples |

### Phase C — HQ rollups, consolidation and required reports
Outcome: management sees branch/consolidated totals and finance reports matching Excel samples.

| # | Task | Priority | User outcome | Source / approved | Gap | Smallest change / deps | Acceptance check |
|---|---|---|---|---|---|---|---|
| C1 | Reconciliation runner (isolated DB, hash checks) | P1 | Safe verification | Approved runner pattern | Extend runner for import checks | Runner creates/removes own DB; source hashes unchanged |
| C2 | Reconciliation report (row counts + totals) | P2 | Evidence of match | V1 §12 | Not built | Generate report doc | Tolerance 0 on formulas |

### Phase D — Remaining workbook finance workflows and approved additions (ordered by usefulness)
Outcome: cash, expenses, P&L, payroll (lightweight), purchasing depth — only where evidenced/approved.

| # | Task | Priority | User outcome | Source / approved | Gap | Smallest change / deps | Acceptance check |
|---|---|---|---|---|---|---|---|
| D1 | Cash ledger (from `النقديه`) | P2 | Track cash | Finance workbook | Not built | Read view + import | Balance checks pass |
| D2 | Expenses + revenue (from `المصروفات`/`الايرادات`) | P2 | Expense tracking | Finance workbook | Not built | Read view + import | Totals reconcile |
| D3 | P&L report (from `الارباح والخسائر`) | P2 | Profit view | Finance workbook | Not built | Read view | Reconciles to Excel |
| D4 | BS report (from `الموازنه العامه`/`الميزانيه`) | P2 | Balance sheet | Finance workbook | Not built | Read view | Reconciles to Excel |
| D5 | Fixed/variable assets (from `الاصول *`) | P3 | Asset view | Finance workbook | Not built | Read view | Reconciles |
| D6 | Payroll (lightweight salary records) | P3 | Salary tracking | Answers.txt (lightweight) | Discovery-gated | Only if confirmed required | Owner confirms depth |
| D7 | Purchasing depth (PO/GRN) | P3 | Procurement | Answers.txt (progressive) | Discovery-gated | Only if confirmed | Owner confirms depth |
| D8 | Private accounts module (D40) | P2 | Owner-only accounts | D40 | Approved, not built | Dedicated schema + owner-only + audit | Boundary tests pass |
| D9 | Global search (P2.10) | P2 | Fast lookup | Approved | Not built | Search across customers/products | Returns correct records |
| D10 | Reason codes (P2.9) | P2 | Void/return reasons | Approved | Not built | Reason code CRUD | Used in void/adjustment |
| D11 | Dev fixture loader (P2.11) | P3 | Demo data | Approved | Not built | Loader script | Seeds demo DB |
| D12 | Server-side PDF (D45) | P2 | PDF export | D45 | Blocked on protected file | Owner approves `requirements.txt` edit | PDF generated server-side |
| D13 | Independent review completion | P1 | Unlock held commit | Review gate | NO_VERDICT returned | Commission authorized reviewer | Review verdict recorded |
| D14 | R-35 browser click-through evidence | P2 | Demo evidence | Client demo | Partial | Manual browser pass | Screenshots committed |
| D15 | Lighthouse pass | P3 | Performance baseline | — | Not run | Run lighthouse (needs Chrome) | Score recorded or blocker named |

### Phase E — Approved additions and polish (only where evidenced/approved)
Outcome: complete approved additions without generic ERP expansion.

| # | Task | Priority | User outcome | Source / approved | Gap | Smallest change / deps | Acceptance check |
|---|---|---|---|---|---|---|---|
| E1 | Vertix borrow: skeleton reveal + Escape dialogs | P3 | Better UX | D44 | Partial | CSS/JS polish (done) | Reduced-motion safe |
| E2 | Vertix borrow: Blob CSV export (AR) | P3 | Export data | D44 | Done | Export button | CSV downloads |
| E3 | Count-up KPI tiles | P3 | Visual polish | D44 | Done | Helper in app.js | Animates, skips reduced motion |

## 3. Status legend
- **Implemented:** code + tests + evidence.
- **Partial:** code exists, verification or UI integration incomplete.
- **Missing:** not started.
- **Deferred:** discovery-gated, needs owner confirmation.
- **Unapproved:** Phase-4 scope decision (cash/bank, expenses, P&L, payroll, POs beyond evidence).

## 4. Immediate next task
**B1 — Import dry run: master data (branches/territories/warehouses/customers/products)** against a disposable `dms_cycle_test_*` DB, using the workbook as read-only source. Acceptance: row counts match workbook; source hashes unchanged; no writes to `*.xlsx`.

## 5. Essential owner questions (only)
1. **Independent review:** commission an authorized reviewer for the held invoice-cycle commit? (Rule: focused independent review for money/stock/migrations/auth.)
2. **Server-side PDF (D45):** approve editing protected `requirements.txt` to add a PDF library?
3. **Phase-4 scope:** approve cash/bank, expenses, P&L, payroll, POs as in-scope, and provide business rules?
4. **R-35 / Lighthouse:** will you run browser click-through + Lighthouse manually (no Chrome here)?

## 6. Blocker classification (corrected)
- **Browser tooling:** installed (Playwright + Chromium) — no longer a blocker; emulation done, physical device remains manual.
- **Independent review:** does not inherently require an external commission; an authorized reviewer (internal or external) can run the existing review gate. Blocked on commissioning, not on tooling.
- **Genuine blockers:** protected-file edits (hard rule 4), `medical_dms` access (hard rule 2), framework migration (D46), Phase-4 business rules (D29), source-workbook writes (hard rule 3).

## 7. Backlog linkage (no duplication)
Detailed specs, slices and evidence live in: `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`, `docs/DECISION_LOG.md`, `docs/SPEC_COVERAGE_MATRIX.md`, `docs/MIGRATION_RECONCILIATION_PLAN.md`, `docs/OPEN_QUESTIONS.md`, `docs/AUDIT_VS_WORKBOOKS.md`, `docs/MANUAL_TEST_CHECKLIST.md`. This plan links to them; it does not restate them.