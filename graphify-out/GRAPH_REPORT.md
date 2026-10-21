# Graph Report - Huge system  (2026-10-18)

## Corpus Check
- 272 files · ~1,210,182 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2498 nodes · 3881 edges · 218 communities (183 shown, 13 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 74 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f0f1ed8c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- context/app/sales/router.py
- app/inventory/router.py
- invoice_totals
- context
- files
- DESIGN_BRIEF.md — Medical Company System (ERP-Lite / DMS)
- الميزانية العمومية 2026.xlsx
- api-review-input/app/auth/router.py
- files/tests/test_invoice_cycle_safety.py
- tests/test_invoice_cycle_safety.py
- customer_balance
- app/sales/router.py
- files/app/sales/router.py
- Product Requirements Document (PRD)
- context
- InsufficientStock
- files/tests/test_inventory_api.py
- IMPLEMENTATION PLAN — Medical Company System
- tests/test_inventory_api.py
- record_entry
- reverse_invoice_atomic
- app/auth/router.py
- api-review-input/tests/test_invoice_api.py
- tests/test_invoice_api.py
- Medical Company System - Master Planning / Lain Handoff — V2
- context/app/finance/router.py
- app/finance/router.py
- app/db.py
- app/finance/payment_router.py
- DATABASE_SCHEMA.md — Medical Company System
- 2B. Confirmed company-specific business features
- worker-delivered/app/finance/payment_router.py
- files/app/finance/payment_router.py
- get_db
- test_ar_ledger.py
- tests/test_collections.py
- app/auth/repo.py
- inventory-authorization/review-input/context/app/auth/router.py
- Files Changed / Created
- invoice-cycle/review-input/context/app/auth/router.py
- Files Changed / Created
- EXCEL_FEATURE_CATALOG.md
- Medical Company System - Master Planning / Lain Handoff
- test_reconciliation.py
- app/auth/rbac.py
- inventory-authorization/review-input/files/app/inventory/service.py
- invoice-cycle/review-input/files/app/inventory/service.py
- protected_unchanged
- worker-delivered/manifest.json
- app/finance/payments.py
- test_pwa.py
- DATA_DICTIONARY.md
- context/app/sales/calc.py
- counts
- Medical Company System — Application Flows
- files
- Controls mapped (per `docs/INVOICE_SLICE_1.md` security table)
- MIGRATION_RECONCILIATION_PLAN.md
- test_invoice_routing.py
- files/app/finance/ar.py
- files/app/finance/schemas.py
- files/tests/test_invoice_cycle.py
- files/tests/test_invoice_reversal.py
- worker-delivered/app/finance/schemas.py
- worker-delivered/tests/test_invoice_cycle.py
- OPEN_QUESTIONS.md
- Progress Checklist — Medical Company System
- SOURCE_WORKBOOK_INVENTORY.md
- test_invoice_boundaries.py
- tests/test_invoice_cycle.py
- 2. Module A — Platform
- files/tests/test_inventory_authorization.py
- context/app/sales/schemas.py
- api-review-input/app/sales/schemas.py
- docs/README.md
- Excel Structural Inventory (raw)
- Pre-Coding Verification — First Milestone
- tests/test_inventory_authorization.py
- 10. Role-Specific Flows
- Receivables (AR) Slice 1 — ledger + atomic posting transaction
- CURRENT_WORKFLOWS.md
- Inventory Slice 1 — stock ledger and balances
- Inventory Slice 1 — stock ledger and balances
- Invoice Slice 1 — Piece 2: draft API
- Module Definitions
- Technical Requirements
- app.js
- 4. Module C — Sales
- 5. Finance - Balance Sheet/P&L (`الميزانية العمومية 2026.xlsx`)
- DECISION_LOG.md
- Invoice → Stock → AR → Collection milestone
- post_invoice_atomic
- alembic/versions/0010_invoice_collections.py
- app/finance/ar.py
- app/finance/payment_router.py
- app/finance/payments.py
- app/finance/schemas.py
- app/inventory/service.py
- app/main.py
- app/sales/router.py
- app/sales/service.py
- scripts/verify_invoice_cycle.py
- tests/conftest.py
- tests/test_collections.py
- tests/test_invoice_cycle_controls.py
- tests/test_invoice_cycle.py
- tests/test_invoice_cycle_safety.py
- tests/test_invoice_reversal.py
- tests/test_posting_flag.py
- master/router.py
- EXCEL_TO_SYSTEM_MAPPING.md
- Invoice → Stock → AR → Collection milestone
- MEDICAL COMPANY SYSTEM - Excel Discovery Handoff
- 17. Suggested implementation phase model
- 17. Suggested implementation phase model
- Medical Company System
- Agent Handoff — Hermes → OpenCode
- inventory_excel.py
- 3. Module B — Master Data
- ENTITY_DUPLICATE_REPORT.md
- Invoice/Collection milestone — current code PASS; deployment NOT READY
- Parent intake and current milestone report
- context/app/sales/repo.py
- Parent intake and current milestone report
- api-review-input/app/sales/repo.py
- UQ PROPOSED ANSWERS — Draft for Eli's Approval
- 14. Six core planning documents
- 14. Six core planning documents
- 5. Module D — Inventory
- 6. Module E — Finance
- Inventory authorization — verification and review intake
- files/app/main.py
- worker-delivered/app/sales/router.py
- disposable-chain.py
- Invoice → Stock → AR → Collection — test-only API slice
- 12. Observability & Logging
- 2. Recommended Tech Stack (PROPOSAL)
- 4. PostgreSQL Strategy
- env.py
- Independent current-code financial milestone review
- 11. Performance & Reliability Targets
- 5. Hosting & Server Details
- 8. Architecture direction
- 8. Architecture direction
- app/config.py
- 12. Validation States
- 7. Module F — Marketing
- 9. Module H — Analytics
- context/app/config.py
- 6. Remote Access & HTTPS Comparison
- 7. Backup & Recovery
- 8. Supported Devices & Browsers
- 8. Module G — Purchasing
- 10. Telegram & WhatsApp Integration
- 12. Migration and reconciliation requirements
- 15. Open-source reference projects
- 3. Source Excel workbooks
- 6. Product requirements - planning scope
- 9. Telegram first, WhatsApp later
- 12. Migration and reconciliation requirements
- 15. Open-source reference projects
- 3. Source Excel workbooks
- 6. Product requirements - planning scope
- 9. Telegram first, WhatsApp later
- app/__init__.py
- inventory-authorization/REVIEW_BRIEF.md
- LEDGER.md
- 13. Testing / release gates
- 2. Current decisions / working baseline
- analyze_inventory.py
- extract_summary.py
- sw.js
- test_master_data_b.py
- make_demo.py
- test_pwa_invoice_ui.py
- worker-delivered/app/finance/payments.py
- test_master_api.py
- Client Prototype — Demo Guide
- B Master Data slice — verified evidence (2026-10-18)
- record_movement
- test_invoice_excel.py
- Evidence — client prototype stage `client-proto-20261018`
- tests/test_posting.py
- AGENTS.md — ElsebaeyPharma / Medical Company System
- record_sale
- app/main.py
- ElsebaeyPharma ERP — review unblock and recovery boundary
- worker-delivered/app/sales/service.py
- Sales UI slice — verified evidence (2026-10-18)
- Final local code acceptance — PASS
- Parent intake — current-code review accepted; release not approved
- Final current-code acceptance — invoice-collection-20261017
- GitHub first-push gate — BLOCKED
- native_record_validation.py
- master/__init__.py
- preflight.py

## God Nodes (most connected - your core abstractions)
1. `get_db()` - 55 edges
2. `customer_balance()` - 32 edges
3. `log_audit()` - 28 edges
4. `line_calc()` - 27 edges
5. `invoice_totals()` - 27 edges
6. `Medical Company System - Master Planning / Lain Handoff — V2` - 26 edges
7. `post_invoice_atomic()` - 23 edges
8. `Medical Company System - Master Planning / Lain Handoff` - 23 edges
9. `get_current_user()` - 20 edges
10. `_invoice()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `create_user()` --calls--> `hash_password()`  [INFERRED]
  docs/evidence/invoice-piece2/api-review-input/app/auth/repo.py → app/auth/security.py
- `login()` --calls--> `verify_password()`  [INFERRED]
  docs/evidence/inventory-authorization/review-input/context/app/auth/router.py → app/auth/security.py
- `login()` --calls--> `verify_password()`  [INFERRED]
  docs/evidence/invoice-cycle/review-input/context/app/auth/router.py → app/auth/security.py
- `login()` --calls--> `verify_password()`  [INFERRED]
  docs/evidence/invoice-piece2/api-review-input/app/auth/router.py → app/auth/security.py
- `posting_env()` --indirect_call--> `get_db()`  [INFERRED]
  docs/evidence/inventory-authorization/review-input/context/tests/test_posting.py → app/db.py

## Import Cycles
- None detected.

## Communities (218 total, 13 thin omitted)

### Community 0 - "context/app/sales/router.py"
Cohesion: 0.07
Nodes (58): Parameterized invoice persistence; commits belong to the API transaction., DraftIn, DraftUpdate, InputModel, InvoiceOut, LineIn, LineOut, BaseModel (+50 more)

### Community 1 - "app/inventory/router.py"
Cohesion: 0.09
Nodes (44): _host(), list_movements(), list_stock(), CurrentUser, datetime, Db, get, post (+36 more)

### Community 2 - "invoice_totals"
Cohesion: 0.18
Nodes (21): invoice_totals(), line_calc(), net_price(), Decimal, _r2(), Invoice calculation — pure functions, no DB. Business rules (D18 net price, D36…, Round a Decimal to 2 places, half-up (money)., E = C × (1 − D). Per-unit net after discount (VAT-inclusive). (+13 more)

### Community 3 - "context"
Cohesion: 0.04
Nodes (48): bytes, diff_sha256, hunks, normalized_replay, raw_sha256, bytes, diff_sha256, hunks (+40 more)

### Community 4 - "files"
Cohesion: 0.04
Nodes (44): bytes, sha256, bytes, sha256, bytes, sha256, bytes, sha256 (+36 more)

### Community 5 - "DESIGN_BRIEF.md — Medical Company System (ERP-Lite / DMS)"
Cohesion: 0.05
Nodes (41): 10. Anti-Patterns — Examples of What the UI Must NOT Look Like, 11. Printable & PDF Document Design Rules, 12. Verification & Design Review Checklist, 1. Executive Summary & Design Mission, 1. ❌ The Raw Spreadsheet Clone, 2.1 Brand Identity Profile, 2.2 Visual Tone & Atmosphere, 2. Company Branding Direction (Working Identity: Name TBD) (+33 more)

### Community 6 - "الميزانية العمومية 2026.xlsx"
Cohesion: 0.05
Nodes (39): Summary-sheet extraction (business-rule archaeology), `اجمالى الحسابات`  (70 x 23), `الارباح والخسائر`  (21 x 10), `الايرادات`  (40 x 5), `التكاليف`  (40 x 5), `الحاج علاء`  (97 x 8), `الرئيسية`  (129 x 34), `الرئيسية`  (147 x 34) (+31 more)

### Community 7 - "api-review-input/app/auth/router.py"
Cohesion: 0.07
Nodes (27): owner_panel(), get, RBAC: role matrix + private/owner boundary (D10, P2.5). Imports…, Dependency factory: 403 unless the current user's role is allowed., D10 private/owner boundary: only is_owner accounts may proceed., require_owner(), require_role(), create_user() (+19 more)

### Community 8 - "files/tests/test_invoice_cycle_safety.py"
Cohesion: 0.16
Nodes (31): life(), fixture, Real committed lifecycle controls; refuses every non-disposable database., scalar(), sql(), state(), test_collection_list_respects_territory_revocation(), test_posted_invoice_rejects_raw_snapshot_mutation() (+23 more)

### Community 9 - "tests/test_invoice_cycle_safety.py"
Cohesion: 0.16
Nodes (31): life(), fixture, Real committed lifecycle controls; refuses every non-disposable database., scalar(), sql(), state(), test_collection_list_respects_territory_revocation(), test_posted_invoice_rejects_raw_snapshot_mutation() (+23 more)

### Community 10 - "customer_balance"
Cohesion: 0.08
Nodes (17): customer_balance(), Customer receivables ledger (finance.ar) + user->warehouse access scope.…, Warehouses a user may touch via branch assignment. Owner is not special-cased…, Σ(debit) - Σ(credit). Matches Excel الرصيد = مدين - دائن., warehouses_for_user(), Payment receipt (collections) tests: create, void, list, overpayment guards., test_create_receipt_final_payment(), test_create_receipt_partial_payment() (+9 more)

### Community 11 - "app/sales/router.py"
Cohesion: 0.20
Nodes (29): _audit(), create_invoice(), _editable(), _integrity_error(), _invoice(), post_invoice(), _posting_references(), _prepare() (+21 more)

### Community 12 - "files/app/sales/router.py"
Cohesion: 0.20
Nodes (29): _audit(), create_invoice(), _editable(), _integrity_error(), _invoice(), post_invoice(), _posting_references(), _prepare() (+21 more)

### Community 13 - "Product Requirements Document (PRD)"
Cohesion: 0.07
Nodes (29): 10. Unresolved Questions, 11. References, 1. Project Goal, 2. Users & Roles, 3. Feature List, 4. User Goals, 5. Business Rules (Cited to Evidence), 6. Edge Cases (+21 more)

### Community 14 - "context"
Cohesion: 0.07
Nodes (28): path, sha256, path, sha256, path, sha256, path, sha256 (+20 more)

### Community 15 - "InsufficientStock"
Cohesion: 0.18
Nodes (12): _apply_balance(), InsufficientStock, Exception, A movement would drive a stock balance below zero., Add `delta` to one balance row atomically; return the new quantity., posting_env(), fixture, Atomic Invoice -> Stock -> AR posting transaction (called directly). The HTTP… (+4 more)

### Community 16 - "files/tests/test_inventory_api.py"
Cohesion: 0.09
Nodes (11): fixture, parametrize, Inventory API integration tests: real PostgreSQL, no repository mocks., Every request uses real SQL; API commits are contained in an outer rollback., stock_env(), test_branch_scoped_roles_without_assignment_are_denied(), test_invalid_quantities_rejected(), test_other_roles_cannot_record_movements() (+3 more)

### Community 17 - "IMPLEMENTATION PLAN — Medical Company System"
Cohesion: 0.08
Nodes (25): 1. Overview, 2. Phase Model, 3. Stages & Dependencies, 4. Approval Gates Summary, 5. Rollback Approach, 6. Go-Live Plan, 7. Post-Launch Stabilization, 8. Risk Register (+17 more)

### Community 18 - "tests/test_inventory_api.py"
Cohesion: 0.09
Nodes (11): fixture, parametrize, Inventory API integration tests: real PostgreSQL, no repository mocks., Every request uses real SQL; API commits are contained in an outer rollback., stock_env(), test_branch_scoped_roles_without_assignment_are_denied(), test_invalid_quantities_rejected(), test_other_roles_cannot_record_movements() (+3 more)

### Community 19 - "record_entry"
Cohesion: 0.23
Nodes (11): record_entry(), create_receipt(), fetch_receipt(), _lock_invoice(), _lock_receipt(), Payment receipt service: create, void, and list receipts linked to invoices.…, Void a receipt: append AR adjustment debit, flip status to Voided., Sum of Active receipt amounts for an invoice. (+3 more)

### Community 20 - "reverse_invoice_atomic"
Cohesion: 0.09
Nodes (22): create_receipt(), Insert a receipt and its AR payment credit entry. Returns receipt_id., Reverse a Posted invoice atomically (append-only compensating entries): 1.…, reverse_invoice_atomic(), test_reversal_preserves_original_vat_and_line_snapshots(), test_reversal_refused_when_active_receipts_exist(), fixture, Posted invoice reversal tests: exact stock+AR compensation, append-only. (+14 more)

### Community 21 - "app/auth/router.py"
Cohesion: 0.14
Nodes (20): create_session(), delete_session(), get_session(), get_user_by_id(), get_user_by_username(), get_current_user(), login(), LoginIn (+12 more)

### Community 22 - "api-review-input/tests/test_invoice_api.py"
Cohesion: 0.10
Nodes (11): invoice_env(), fixture, parametrize, Invoice API integration tests: real PostgreSQL, no repository mocks., Every request uses real SQL; API commits are contained in an outer rollback., test_assigned_business_roles_can_create_and_edit_own_drafts(), test_invalid_or_server_owned_header_fields_rejected(), test_invalid_or_server_owned_line_fields_rejected() (+3 more)

### Community 23 - "tests/test_invoice_api.py"
Cohesion: 0.10
Nodes (11): invoice_env(), fixture, parametrize, Invoice API integration tests: real PostgreSQL, no repository mocks., Every request uses real SQL; API commits are contained in an outer rollback., test_assigned_business_roles_can_create_and_edit_own_drafts(), test_invalid_or_server_owned_header_fields_rejected(), test_invalid_or_server_owned_line_fields_rejected() (+3 more)

### Community 24 - "Medical Company System - Master Planning / Lain Handoff — V2"
Cohesion: 0.09
Nodes (21): 10. Security baseline, 11. Database/schema principles, 13. Testing / release gates, 16. Proposed project repository documentation structure, 18. Rules for Lain, 19. Decisions still intentionally open, 1. Project intent, 20. Build-start gate (+13 more)

### Community 25 - "context/app/finance/router.py"
Cohesion: 0.18
Nodes (19): list_entries(), Column names are fixed literals; values are bound parameters., EntryOut, _branch_customers(), _host(), list_balances(), list_entries(), CurrentUser (+11 more)

### Community 26 - "app/finance/router.py"
Cohesion: 0.18
Nodes (18): _branch_customers(), _host(), list_balances(), list_entries(), CurrentUser, date, Db, get (+10 more)

### Community 27 - "app/db.py"
Cohesion: 0.12
Nodes (10): Shared database wiring for the Medical Company System API. Reads DATABASE_URL…, Exercise migrations only on a newly created, task-owned disposable database., bindings(), main(), Run invoice-cycle tests only on a fresh synthetic PostgreSQL database., Real-PostgreSQL invoice persistence constraints (not SQLite approximations)., bindings(), main() (+2 more)

### Community 28 - "app/finance/payment_router.py"
Cohesion: 0.20
Nodes (20): log_audit(), Immutable audit row (audit.audit_log — NO DELETE per §10)., _audit(), create_receipt(), get_receipt(), _host(), list_receipts(), CurrentUser (+12 more)

### Community 29 - "DATABASE_SCHEMA.md — Medical Company System"
Cohesion: 0.11
Nodes (18): 10. Audit & Reference Module (schema: `audit`), 11. Calculated / Snapshot Fields, 12. Access Rules & RLS, 13. Deletion / Void / Reversal Policy, 14. Migration Mapping (Excel Sheet → Table), 15. Key Constraints Summary, 1. ER Diagram (Mermaid — 25 core entities), 2. Platform Module (schema: `platform`) (+10 more)

### Community 30 - "2B. Confirmed company-specific business features"
Cohesion: 0.11
Nodes (19): 2B.10 Customer stock-visit workflow, 2B.11 Automatic sell-through calculation, 2B.12 Customer/product returns, 2B.13 Sales targets, 2B.14 Stock cover, 2B.15 Overstock alerts, 2B.16 Doctor/KOL marketing-spend tracking, 2B.17 Product/brand-linked marketing spend (+11 more)

### Community 31 - "worker-delivered/app/finance/payment_router.py"
Cohesion: 0.20
Nodes (22): InputModel, BaseModel, AR entry and payment receipt input/output models., ReceiptIn, ReceiptOut, ReceiptVoidIn, _audit(), create_receipt() (+14 more)

### Community 32 - "files/app/finance/payment_router.py"
Cohesion: 0.25
Nodes (17): _audit(), create_receipt(), get_receipt(), _host(), list_receipts(), CurrentUser, date, Db (+9 more)

### Community 33 - "get_db"
Cohesion: 0.15
Nodes (15): get_db(), isolated_financial_database(), posting_env(), fixture, Shared pytest fixtures for the posting tests. `posting_env` lives here (rather…, collections_env(), fixture, Fresh DB with a Posted invoice ready for collections. (+7 more)

### Community 34 - "test_ar_ledger.py"
Cohesion: 0.14
Nodes (8): ar_env(), fixture, parametrize, Customer receivables ledger tests: real PostgreSQL, no mocks., test_non_ar_roles_cannot_view_balances(), test_other_roles_cannot_record_entries(), test_read_roles_can_view_balances(), test_write_roles_can_record_entries()

### Community 35 - "tests/test_collections.py"
Cohesion: 0.12
Nodes (9): collections_env(), fixture, Payment receipt (collections) tests: create, void, list, overpayment guards., Fresh DB with a Posted invoice ready for collections., test_create_receipt_final_payment(), test_create_receipt_partial_payment(), test_overpayment_rejected(), test_partial_then_final_sum_rejects_overpayment() (+1 more)

### Community 36 - "app/auth/repo.py"
Cohesion: 0.21
Nodes (12): create_user(), Data access for platform users, sessions, and the audit log. All column sets…, hash_password(), Password hashing (stdlib PBKDF2-HMAC-SHA256, 200k iterations). Zero external…, _cleanup(), Auth + session integration tests (P2.4 / P2.6). Runs against the dev DB…, _seed(), _seed_owner() (+4 more)

### Community 37 - "inventory-authorization/review-input/context/app/auth/router.py"
Cohesion: 0.23
Nodes (14): get_current_user(), login(), LoginIn, LoginOut, logout(), me(), MeOut, _parse_uuid() (+6 more)

### Community 38 - "Files Changed / Created"
Cohesion: 0.13
Nodes (14): API Schema, App Wiring, Collections API Router, Critical Controls Preserved, Database Migration, Files Changed / Created, Invoice→Stock→AR→Collection Milestone: Implementer Report, Key Test Coverage (+6 more)

### Community 39 - "invoice-cycle/review-input/context/app/auth/router.py"
Cohesion: 0.23
Nodes (14): get_current_user(), login(), LoginIn, LoginOut, logout(), me(), MeOut, _parse_uuid() (+6 more)

### Community 40 - "Files Changed / Created"
Cohesion: 0.13
Nodes (14): API Schema, App Wiring, Collections API Router, Critical Controls Preserved, Database Migration, Files Changed / Created, Invoice→Stock→AR→Collection Milestone: Implementer Report, Key Test Coverage (+6 more)

### Community 41 - "EXCEL_FEATURE_CATALOG.md"
Cohesion: 0.13
Nodes (13): Balance Sheet / P&L (`الميزانية العمومية 2026.xlsx`), Data Validations, External Links (Cross-Workbook), Formula Density (Notable), Key Business Features (from `summary_extract.md`), Merged Cells, Payroll (`المرتبات`), Private Accounts (`حسابات خاصه.xlsx`) (+5 more)

### Community 42 - "Medical Company System - Master Planning / Lain Handoff"
Cohesion: 0.13
Nodes (14): 10. Security baseline, 11. Database/schema principles, 16. Proposed project repository documentation structure, 18. Rules for Lain, 19. Decisions still intentionally open, 1. Project intent, 20. Build-start gate, 21. One-paragraph mission statement for Lain (+6 more)

### Community 43 - "test_reconciliation.py"
Cohesion: 0.25
Nodes (12): _nums(), Reconciliation tests (Option C, rule 1): verify documented business rules…, # NOTE: the mapping's payroll formula "E=B-C-D" does NOT match this layout, _sheet(), test_ar_balance_opening_and_running(), test_ar_customer_balance_is_debits_minus_credits(), test_ar_row1_total_is_2_200_000(), test_hq_rollup_balance_is_sales_minus_collection() (+4 more)

### Community 44 - "app/auth/rbac.py"
Cohesion: 0.11
Nodes (17): owner_panel(), get, RBAC: role matrix + private/owner boundary (D10, P2.5). Imports…, Dependency factory: 403 unless the current user's role is allowed., D10 private/owner boundary: only is_owner accounts may proceed., require_owner(), require_role(), health() (+9 more)

### Community 45 - "inventory-authorization/review-input/files/app/inventory/service.py"
Cohesion: 0.19
Nodes (12): _apply_balance(), _filters(), InsufficientStock, list_balances(), list_movements(), Exception, Inventory stock ledger and balances. A movement is an append-only ledger row;…, A movement would drive a stock balance below zero. (+4 more)

### Community 46 - "invoice-cycle/review-input/files/app/inventory/service.py"
Cohesion: 0.19
Nodes (12): _apply_balance(), _filters(), InsufficientStock, list_balances(), list_movements(), Exception, Inventory stock ledger and balances. A movement is an append-only ledger row;…, Build a WHERE clause from bound values; column names are fixed literals. (+4 more)

### Community 47 - "protected_unchanged"
Cohesion: 0.14
Nodes (14): protected_unchanged, app/config.py, app/db.py, docker-compose.yml, Dockerfile, .env.dev, requirements.txt, \u0627\u0644\u0645\u064a\u0632\u0627\u0646\u064a\u0629 \u0627\u0644\u0639\u0645\u0648\u0645\u064a\u0629 2026.xlsx (+6 more)

### Community 48 - "worker-delivered/manifest.json"
Cohesion: 0.14
Nodes (13): alembic/versions/0010_invoice_collections.py, app/finance/payment_router.py, app/finance/payments.py, app/finance/schemas.py, app/main.py, app/sales/router.py, app/sales/service.py, docs/evidence/invoice-cycle/IMPLEMENTER.md (+5 more)

### Community 49 - "app/finance/payments.py"
Cohesion: 0.31
Nodes (8): fetch_receipt(), _lock_invoice(), _lock_receipt(), Payment receipt service: create, void, and list receipts linked to invoices.…, Void a receipt: append AR adjustment debit, flip status to Voided., Sum of Active receipt amounts for an invoice., _sum_active_receipts(), void_receipt()

### Community 50 - "test_pwa.py"
Cohesion: 0.38
Nodes (4): _json(), P2.7 PWA shell: manifest installability, RTL + service-worker wiring, i18n key…, test_i18n_key_parity(), test_manifest_is_installable()

### Community 51 - "DATA_DICTIONARY.md"
Cohesion: 0.15
Nodes (11): 1. Sales - `الرئيسية` (HQ Summary/Rollups), 2. Sales - `رصيد الارصدة المباعة` (Sold Balances), 3. Sales - `كامل الكمية` / `تحت التصريف`, 4. Payroll - `المرتبات`, 6. Private Accounts - `حسابات خاصه.xlsx`, Monthly tabs, Notes, `اجمالى الحسابات` (70×23, 76 formulas) (+3 more)

### Community 52 - "context/app/sales/calc.py"
Cohesion: 0.28
Nodes (12): invoice_totals(), line_calc(), net_price(), Decimal, _r2(), Invoice calculation — pure functions, no DB. Business rules (D18 net price, D36…, Round a Decimal to 2 places, half-up (money)., E = C × (1 − D). Per-unit net after discount (VAT-inclusive). (+4 more)

### Community 53 - "counts"
Cohesion: 0.21
Nodes (13): error, failed, passed, skipped, counts, run, sha256, counts (+5 more)

### Community 54 - "Medical Company System — Application Flows"
Cohesion: 0.17
Nodes (11): 11. Approval / Override Paths, 13. Mobile-Specific Flows, 14. Sales Rollup (from CURRENT_WORKFLOWS), 15. Sold Balances (from CURRENT_WORKFLOWS), 16. Stock Lists (from CURRENT_WORKFLOWS), 17. Error Handling & Edge Cases, 18. Logout & Session Security, 1. Navigation Map (+3 more)

### Community 55 - "files"
Cohesion: 0.17
Nodes (11): base, files, lint, baseline_count, counts, exit_code, new_findings, raw_trace (+3 more)

### Community 56 - "Controls mapped (per `docs/INVOICE_SLICE_1.md` security table)"
Cohesion: 0.17
Nodes (11): 1. Forged totals, VAT, status, actor — ✅ enforced, 2. Cross-territory / other-rep access — ✅ enforced, 3. Duplicate / stale edits — ✅ enforced, 4. Partial invoice / audit write — ✅ atomic, 5. Accidental real posting — ✅ blocked (both layers), 6. Authentication / sessions — ✅ (inherited, verified), Controls mapped (per `docs/INVOICE_SLICE_1.md` security table), Edge cases observed (acceptable, not defects) (+3 more)

### Community 57 - "MIGRATION_RECONCILIATION_PLAN.md"
Cohesion: 0.17
Nodes (10): Aggregates, Finance, Gating Criteria (Go/No-Go for gated areas), Goals, Migration Phases, Reconciliation Checks (Minimum), References, Security/Boundary (+2 more)

### Community 58 - "test_invoice_routing.py"
Cohesion: 0.30
Nodes (11): Sales source-warehouse routing: cross-branch sourcing via…, Create Dakahlia/Sharqia/Gharbia branches, shared warehouses and routes., Regression: same-branch sourcing still 201 (existing invoice_env data)., sales_manager caller on the route territory; grants the needed branches., _setup_branches(), _sharqia_caller(), _sharqia_payload(), test_own_branch_warehouse_still_allowed() (+3 more)

### Community 59 - "files/app/finance/ar.py"
Cohesion: 0.20
Nodes (10): customer_balance(), list_entries(), Customer receivables ledger (finance.ar) + user->warehouse access scope.…, Warehouses a user may touch via branch assignment. Owner is not special-cased…, One debit entry per posted invoice (amount = grand_total)., Σ(debit) - Σ(credit). Matches Excel الرصيد = مدين - دائن., Column names are fixed literals; values are bound parameters., record_entry() (+2 more)

### Community 60 - "files/app/finance/schemas.py"
Cohesion: 0.27
Nodes (9): EntryIn, EntryOut, InputModel, BaseModel, model_validator, AR entry and payment receipt input/output models., ReceiptIn, ReceiptOut (+1 more)

### Community 61 - "files/tests/test_invoice_cycle.py"
Cohesion: 0.18
Nodes (10): cycle_env(), fixture, Full Invoice → Stock → AR → Collection → Payment Void → Invoice Reversal cycle.…, Full cycle: Post → Partial Collect → Full Collect → Void Receipt → Reverse…, Fresh DB with all fixtures for full cycle test., A second sequential receipt cannot exceed the remaining balance., All four mutation types have independent coverage in cycle_safety., test_flag_off_blocks_posting() (+2 more)

### Community 62 - "files/tests/test_invoice_reversal.py"
Cohesion: 0.22
Nodes (6): fixture, Posted invoice reversal tests: exact stock+AR compensation, append-only., Fresh DB connection with a posted invoice ready for reversal., reversal_env(), _stock(), test_reverse_invoice_atomic_restores_stock_and_ar()

### Community 63 - "worker-delivered/app/finance/schemas.py"
Cohesion: 0.27
Nodes (9): EntryIn, EntryOut, InputModel, BaseModel, model_validator, AR entry and payment receipt input/output models., ReceiptIn, ReceiptOut (+1 more)

### Community 64 - "worker-delivered/tests/test_invoice_cycle.py"
Cohesion: 0.18
Nodes (10): cycle_env(), fixture, Full Invoice → Stock → AR → Collection → Payment Void → Invoice Reversal cycle.…, Fresh DB with all fixtures for full cycle test., Two independent DB sessions trying to collect concurrently., With POSTING_ENABLED=false, post, reverse, collect, void-collect all return 409., Full cycle: Post → Partial Collect → Full Collect → Void Receipt → Reverse…, test_concurrent_collection_rejects_overpayment() (+2 more)

### Community 65 - "OPEN_QUESTIONS.md"
Cohesion: 0.18
Nodes (9): 1. External Links (resolved 2026-10-16), 2. Source Integrity (resolved 2026-10-16), 3. Placeholders (resolved 2026-10-16), 6a. AR Ledger (resolved 2026-10-16), Evidence Detail, Purpose, References, Resolution Policy (retained) (+1 more)

### Community 66 - "Progress Checklist — Medical Company System"
Cohesion: 0.18
Nodes (10): Current checkpoint — 2026-10-17 (supersedes older gate/stack summaries below), Phase 0 — Discovery  [gate: ✅ complete per D26], Phase 1 — Planning & Architecture  [gate: ✅ build-start approved 2026-10-16], Phase 2 — Platform Foundation  [gate: 🔒 platform readiness], Phase 3 — Business Modules A→H  [gate: 🔒 per-module], Phase 4 — Telegram  [gate: 🔒 Telegram functional], Phase 5 — Production Migration  [gate: 🔒 migration sign-off], Phase 6 — Go-Live  [gate: 🔒 go-live approval] (+2 more)

### Community 67 - "SOURCE_WORKBOOK_INVENTORY.md"
Cohesion: 0.18
Nodes (10): 1. الميزانية العمومية 2026.xlsx, 2. حسابات خاصه.xlsx, 3. مبيعات 6 اكتوبر 2026.xlsx, 4. مبيعات الدقهليه 2026.xlsx, 5. مبيعات الشرقية 2026.xlsx, 6. مبيعات الغربية  2026.xlsx, 7. مبيعات الفيوم 2026.xlsx, Overview (+2 more)

### Community 68 - "test_invoice_boundaries.py"
Cohesion: 0.18
Nodes (3): parametrize, Boundary controls beyond the main real-Postgres draft-flow tests., test_inactive_reference_rejected()

### Community 69 - "tests/test_invoice_cycle.py"
Cohesion: 0.18
Nodes (10): cycle_env(), fixture, Full Invoice → Stock → AR → Collection → Payment Void → Invoice Reversal cycle.…, Full cycle: Post → Partial Collect → Full Collect → Void Receipt → Reverse…, Fresh DB with all fixtures for full cycle test., A second sequential receipt cannot exceed the remaining balance., All four mutation types have independent coverage in cycle_safety., test_flag_off_blocks_posting() (+2 more)

### Community 70 - "2. Module A — Platform"
Cohesion: 0.20
Nodes (10): 2. Module A — Platform, A1. Authentication Flow, A2. System Settings, A3. Org Structure, A4. Posting Draft / Posted / Voided, A5. Reason Codes, A6. Simple Approvals, A7. Audit Log (+2 more)

### Community 71 - "files/tests/test_inventory_authorization.py"
Cohesion: 0.31
Nodes (8): parametrize, Real-PostgreSQL controls for explicit branch grants, not fulfillment routes., test_assigned_branch_resolves_real_warehouse_ids(), test_branch_assignment_is_not_a_role_or_active_user_bypass(), test_branch_read_grant_does_not_grant_manual_stock_writes(), test_foreign_warehouse_cannot_be_queried_or_leak_through_filters(), test_fulfillment_routes_and_territory_do_not_grant_shared_stock(), test_shared_warehouse_movements_do_not_leak_other_territories()

### Community 72 - "context/app/sales/schemas.py"
Cohesion: 0.33
Nodes (9): DraftIn, DraftUpdate, InputModel, InvoiceOut, LineIn, LineOut, BaseModel, Validated draft inputs and exact-decimal public invoice snapshots. (+1 more)

### Community 73 - "api-review-input/app/sales/schemas.py"
Cohesion: 0.33
Nodes (9): DraftIn, DraftUpdate, InputModel, InvoiceOut, LineIn, LineOut, BaseModel, Validated draft inputs and exact-decimal public invoice snapshots. (+1 more)

### Community 74 - "docs/README.md"
Cohesion: 0.22
Nodes (4): Build Order (A→H), Cross-cutting: Private/Owner Accounts, References, Relationships (High-Level)

### Community 75 - "Excel Structural Inventory (raw)"
Cohesion: 0.20
Nodes (10): Cross-workbook sheet-name duplicates, Excel Structural Inventory (raw), Placeholder / unnamed sheets, الميزانية العمومية 2026.xlsx, حسابات خاصه.xlsx, مبيعات 6 اكتوبر 2026.xlsx, مبيعات الدقهليه 2026.xlsx, مبيعات الشرقية 2026.xlsx (+2 more)

### Community 76 - "Pre-Coding Verification — First Milestone"
Cohesion: 0.20
Nodes (9): Current status correction — 2026-10-17, Discrepancies found (reconciliation surfaced these), Historical report (superseded where it conflicts with the correction above), MVP blockers vs future decisions, Next action, Pre-Coding Verification — First Milestone, Reconciliation results (evidence), The 5 checks (+1 more)

### Community 77 - "tests/test_inventory_authorization.py"
Cohesion: 0.31
Nodes (8): parametrize, Real-PostgreSQL controls for explicit branch grants, not fulfillment routes., test_assigned_branch_resolves_real_warehouse_ids(), test_branch_assignment_is_not_a_role_or_active_user_bypass(), test_branch_read_grant_does_not_grant_manual_stock_writes(), test_foreign_warehouse_cannot_be_queried_or_leak_through_filters(), test_fulfillment_routes_and_territory_do_not_grant_shared_stock(), test_shared_warehouse_movements_do_not_leak_other_territories()

### Community 78 - "10. Role-Specific Flows"
Cohesion: 0.22
Nodes (9): 10. Role-Specific Flows, Branch / Area Manager, CEO / Owner, Finance / Accounting, Read-Only / Auditor, Sales Manager, Sales Representative, System Administrator (+1 more)

### Community 79 - "Receivables (AR) Slice 1 — ledger + atomic posting transaction"
Cohesion: 0.22
Nodes (8): API contract, Authorization (PRD §2), Delivery and evidence, Excel reconciliation (real data), Receivables (AR) Slice 1 — ledger + atomic posting transaction, Run locally (existing PostgreSQL must be available), The atomic posting transaction (tested; endpoint disabled), What is deliberately not here

### Community 80 - "CURRENT_WORKFLOWS.md"
Cohesion: 0.22
Nodes (7): 1. Sales Rollup Workflow (HQ Summary), 2. Sold Balances Workflow (`رصيد الارصدة المباعة`), 3. Stock/Item Lists Workflow (`كامل الكمية` / `تحت التصريف`), 4. Payroll Workflow (`المرتبات`), 5. Finance Workflow (Balance Sheet/P&L), 6. Private Accounts Workflow (`حسابات خاصه.xlsx`), Cross-cutting Notes

### Community 81 - "Inventory Slice 1 — stock ledger and balances"
Cohesion: 0.22
Nodes (8): API contract, Authorization (PRD §2), Current authorization checkpoint — 2026-10-17, Delivery and evidence, Historical first-slice report (superseded where noted above), Inventory Slice 1 — stock ledger and balances, Run locally (existing PostgreSQL must be available), What is deliberately not here

### Community 82 - "Inventory Slice 1 — stock ledger and balances"
Cohesion: 0.22
Nodes (8): API contract, Authorization (PRD §2), Current authorization checkpoint — 2026-10-17, Delivery and evidence, Historical first-slice report (superseded where noted above), Inventory Slice 1 — stock ledger and balances, Run locally (existing PostgreSQL must be available), What is deliberately not here

### Community 83 - "Invoice Slice 1 — Piece 2: draft API"
Cohesion: 0.22
Nodes (8): API contract, Authorization: implemented conservative interpretation, Delivery and evidence, Excel evidence: exact scope, not whole-migration approval, Financial behavior and boundaries, Invoice Slice 1 — Piece 2: draft API, Run locally (existing PostgreSQL must be available), Security evidence and production gate

### Community 84 - "Module Definitions"
Cohesion: 0.22
Nodes (9): A. Platform (Foundation), B. Master Data, C. Sales, D. Inventory, E. Finance, F. Marketing, G. Purchasing, H. Executive Analytics/Telegram (+1 more)

### Community 85 - "Technical Requirements"
Cohesion: 0.22
Nodes (8): 13. Internationalization (i18n) & RTL, 14. Open Items Requiring Eli's Input, 15. Next Action, 1. Approved Constraints (Do Not Override), 3. Architecture Overview, 9. Dependency & License Policy, Approved Dependency License Summary (for proposed stack), Technical Requirements

### Community 86 - "app.js"
Cohesion: 0.12
Nodes (56): addLine(), api(), applyI18n(), badgeClass(), badgeNode(), boot(), branchLabel(), cacheElements() (+48 more)

### Community 87 - "4. Module C — Sales"
Cohesion: 0.25
Nodes (8): 4. Module C — Sales, C1. Invoices (Sell-In), C2. Warehouse Routing, C3. Warehouse-to-Warehouse Transfers, C4. Returns, C5. Receivables / Statements, C6. Sales Targets, C7. Stock Visits (Mobile-First)

### Community 88 - "5. Finance - Balance Sheet/P&L (`الميزانية العمومية 2026.xlsx`)"
Cohesion: 0.25
Nodes (8): 5. Finance - Balance Sheet/P&L (`الميزانية العمومية 2026.xlsx`), `الارباح والخسائر` (21×10, 45 formulas), `الاصول الثابته` / `الاصول المتغيره` (Fixed/Current Assets), `الايرادات` / `التكاليف` / `المصروفات` (40×5 each, ~41–44 formulas), `العملاء` (47×747, 342 formulas, 124 merged), `الموازنه العامه` (18×15, 26 formulas), `الميزانيه` (46×19, 93 formulas), `النقديه` (40×24, 272 formulas)

### Community 89 - "DECISION_LOG.md"
Cohesion: 0.22
Nodes (7): 2026-10-10 — Spec baseline, 2026-10-11 — Eli's answers (`C:\Users\emadg\CrossDevice\Desktop\Answers.txt`), 2026-10-12 — Discovery phase (Phase 0) completed, 2026-10-16 — Eli's UQ decisions (critical blockers resolved), 2026-10-16 — Evidence resolutions (this session), 2026-10-16 — OpenCode session context (recovered from `opencode.db`), 2026-10-18 — B Master Data slice (local-only)

### Community 90 - "Invoice → Stock → AR → Collection milestone"
Cohesion: 0.25
Nodes (7): Global constraints, Invoice → Stock → AR → Collection milestone, Preflight interface/conflict scan, Scope and conservative decisions, Task 1 — Implement and exercise the complete API lifecycle (sole worker), Task 2 — Parent verification and independent review, Task 3 — Evidence and verified commit

### Community 91 - "post_invoice_atomic"
Cohesion: 0.08
Nodes (26): _lines(), _lock_invoice(), post_invoice_atomic(), Atomic invoice posting and reversal: stock + AR in one transaction. Kept as…, Post a draft invoice atomically: 1. decrement stock for each line…, Feature-flag gate for the invoice posting endpoint. The flag POSTING_ENABLED…, Without POSTING_ENABLED the endpoint stays 409 with the old message., With the flag ON the endpoint delegates to post_invoice_atomic once. (+18 more)

### Community 92 - "alembic/versions/0010_invoice_collections.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, alembic/versions/0010_invoice_collections.py

### Community 93 - "app/finance/ar.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, app/finance/ar.py

### Community 94 - "app/finance/payment_router.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, app/finance/payment_router.py

### Community 95 - "app/finance/payments.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, app/finance/payments.py

### Community 96 - "app/finance/schemas.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, app/finance/schemas.py

### Community 97 - "app/inventory/service.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, app/inventory/service.py

### Community 98 - "app/main.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, app/main.py

### Community 99 - "app/sales/router.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, app/sales/router.py

### Community 100 - "app/sales/service.py"
Cohesion: 0.25
Nodes (8): bytes, diff, diff_sha256, hunks, replay_verified, sha256, source, app/sales/service.py

### Community 101 - "scripts/verify_invoice_cycle.py"
Cohesion: 0.25
Nodes (8): scripts/verify_invoice_cycle.py, bytes, diff, diff_sha256, hunks, replay_verified, sha256, source

### Community 102 - "tests/conftest.py"
Cohesion: 0.25
Nodes (8): tests/conftest.py, bytes, diff, diff_sha256, hunks, replay_verified, sha256, source

### Community 103 - "tests/test_collections.py"
Cohesion: 0.25
Nodes (8): tests/test_collections.py, bytes, diff, diff_sha256, hunks, replay_verified, sha256, source

### Community 104 - "tests/test_invoice_cycle_controls.py"
Cohesion: 0.25
Nodes (8): tests/test_invoice_cycle_controls.py, bytes, diff, diff_sha256, hunks, replay_verified, sha256, source

### Community 105 - "tests/test_invoice_cycle.py"
Cohesion: 0.25
Nodes (8): tests/test_invoice_cycle.py, bytes, diff, diff_sha256, hunks, replay_verified, sha256, source

### Community 106 - "tests/test_invoice_cycle_safety.py"
Cohesion: 0.25
Nodes (8): tests/test_invoice_cycle_safety.py, bytes, diff, diff_sha256, hunks, replay_verified, sha256, source

### Community 107 - "tests/test_invoice_reversal.py"
Cohesion: 0.25
Nodes (8): tests/test_invoice_reversal.py, bytes, diff, diff_sha256, hunks, replay_verified, sha256, source

### Community 108 - "tests/test_posting_flag.py"
Cohesion: 0.25
Nodes (8): tests/test_posting_flag.py, bytes, diff, diff_sha256, hunks, replay_verified, sha256, source

### Community 109 - "master/router.py"
Cohesion: 0.16
Nodes (33): AccountType, _branches(), _like(), _limit(), list_accounts(), list_branches(), list_customers(), list_doctors() (+25 more)

### Community 110 - "EXCEL_TO_SYSTEM_MAPPING.md"
Cohesion: 0.22
Nodes (7): A. Sales → C.Sales, B. Payroll → B.MasterData/Platform (lightweight) + related, C. Finance → E.Finance, D. Private Accounts → Private/Owner Accounts (same DB, protected boundary), E. Cross-cutting Notes, Mapping Rules, References

### Community 111 - "Invoice → Stock → AR → Collection milestone"
Cohesion: 0.25
Nodes (7): Global constraints, Invoice → Stock → AR → Collection milestone, Preflight interface/conflict scan, Scope and conservative decisions, Task 1 — Implement and exercise the complete API lifecycle (sole worker), Task 2 — Parent verification and independent review, Task 3 — Evidence and verified commit

### Community 112 - "MEDICAL COMPANY SYSTEM - Excel Discovery Handoff"
Cohesion: 0.25
Nodes (8): Build Order (A→H), Discovery Documents (Index), Evidence Artifacts (Mechanical), Handoff Instructions, Key Findings (Summary), MEDICAL COMPANY SYSTEM - Excel Discovery Handoff, Purpose, Source of Truth

### Community 113 - "17. Suggested implementation phase model"
Cohesion: 0.25
Nodes (8): 17. Suggested implementation phase model, Phase 0 - Discovery, Phase 1 - Planning / architecture, Phase 2 - Platform foundation, Phase 3+ - Business modules, Production migration / go-live, Telegram phase, WhatsApp phase

### Community 114 - "17. Suggested implementation phase model"
Cohesion: 0.25
Nodes (8): 17. Suggested implementation phase model, Phase 0 - Discovery, Phase 1 - Planning / architecture, Phase 2 - Platform foundation, Phase 3+ - Business modules, Production migration / go-live, Telegram phase, WhatsApp phase

### Community 115 - "Medical Company System"
Cohesion: 0.25
Nodes (7): Inventory Slice 1 — stock ledger and balances, Invoice Slice 1 — draft API, Local dev setup, Medical Company System, Phases, Receivables (AR) Slice 1 — ledger + atomic posting transaction, Sources of truth

### Community 116 - "Agent Handoff — Hermes → OpenCode"
Cohesion: 0.06
Nodes (30): 1. Repository state, 2. Completed functionality and architecture, 3. Key business decisions and specifications, 4. Exact commands to reproduce tests and verification, 5. Remaining tasks, priorities and unresolved risks, 6. Local `medical_dms` database recovery — requirements and restrictions, 7. GitHub security issue — credentials and Excel-derived samples, 8. Safe instructions for continuing development in OpenCode (+22 more)

### Community 117 - "inventory_excel.py"
Cohesion: 0.39
Nodes (7): cell_kind(), main(), Phase 0 - Excel structural inventory for the Medical Company System. READ-ONLY.…, Aggregate a sheet without storing all values (memory-bounded)., scan_sheet(), scan_workbook(), sha256()

### Community 118 - "3. Module B — Master Data"
Cohesion: 0.29
Nodes (7): 3. Module B — Master Data, B1. Customers, B2. Products / Catalog / Pricing, B3. Reference Sets, B4. Batches & Expiry, B5. UOM (Unit of Measure), B6. Credit Management

### Community 119 - "ENTITY_DUPLICATE_REPORT.md"
Cohesion: 0.29
Nodes (5): Action Required, Cross-workbook sheet-name duplicates (86), Placeholder / unnamed sheets (53), References, Summary

### Community 120 - "Invoice/Collection milestone — current code PASS; deployment NOT READY"
Cohesion: 0.25
Nodes (7): Current authority and snapshot, Historical pre-finalization handoff — superseded below, Independent-review delivery: NO VERDICT, Invoice/Collection milestone — current code PASS; deployment NOT READY, Isolation incident and default local DB recovery gate, Requested work and supported results, Resume once authorized

### Community 121 - "Parent intake and current milestone report"
Cohesion: 0.29
Nodes (6): Conservative decisions / release boundaries, Consumer path now exercised, Current native verification, Delivery and chronology disposition, Open acceptance, Parent intake and current milestone report

### Community 123 - "Parent intake and current milestone report"
Cohesion: 0.29
Nodes (6): Conservative decisions / release boundaries, Consumer path now exercised, Current native verification, Delivery and chronology disposition, Open acceptance, Parent intake and current milestone report

### Community 125 - "UQ PROPOSED ANSWERS — Draft for Eli's Approval"
Cohesion: 0.29
Nodes (6): Decided by Eli (2026-10-16), Deferred UQs with Target Phase, MVP Blockers Summary — RESOLVED (2026-10-16), Proposed Answers Table, Review notes (Lain, 2026-10-16), UQ PROPOSED ANSWERS — Draft for Eli's Approval

### Community 126 - "14. Six core planning documents"
Cohesion: 0.29
Nodes (7): 14.1 `PRD.md` - Product Requirements Document, 14.2 `TECHNICAL_REQUIREMENTS.md`, 14.3 `APP_FLOW.md`, 14.4 `DESIGN_BRIEF.md`, 14.5 `DATABASE_SCHEMA.md`, 14.6 `IMPLEMENTATION_PLAN.md`, 14. Six core planning documents

### Community 127 - "14. Six core planning documents"
Cohesion: 0.29
Nodes (7): 14.1 `PRD.md` - Product Requirements Document, 14.2 `TECHNICAL_REQUIREMENTS.md`, 14.3 `APP_FLOW.md`, 14.4 `DESIGN_BRIEF.md`, 14.5 `DATABASE_SCHEMA.md`, 14.6 `IMPLEMENTATION_PLAN.md`, 14. Six core planning documents

### Community 128 - "5. Module D — Inventory"
Cohesion: 0.33
Nodes (6): 5. Module D — Inventory, D1. Stock Ledger, D2. Stock Balances, D3. Stock Cover, D4. Overstock Alerts, D5. Low-Stock Alerts

### Community 129 - "6. Module E — Finance"
Cohesion: 0.33
Nodes (6): 6. Module E — Finance, E1. Cash & Bank, E2. Expenses & Revenue, E3. P&L & Balance Sheet, E4. Payroll (Lightweight), E5. Private / Owner Accounts

### Community 130 - "Inventory authorization — verification and review intake"
Cohesion: 0.33
Nodes (5): Inventory authorization — verification and review intake, Native evidence, Posting and next task, Result, Review and method disposition

### Community 131 - "files/app/main.py"
Cohesion: 0.40
Nodes (5): health(), get, Medical Company System API (Phase 2 — Platform Foundation). Current scope:…, Readiness probe: used by Docker + CI to confirm the API boots., root()

### Community 132 - "worker-delivered/app/sales/router.py"
Cohesion: 0.22
Nodes (27): _audit(), create_invoice(), _editable(), _integrity_error(), _invoice(), post_invoice(), _prepare(), CurrentUser (+19 more)

### Community 133 - "disposable-chain.py"
Cohesion: 0.33
Nodes (5): insert_cross_branch_invoice(), Exercise migrations only on a newly created, task-owned disposable database.…, Branches, routed warehouse, customer in branch X; no FKs on invoice yet., Cross-branch invoice: invoice X, warehouse owned by Y (fulfillment routed)., seed()

### Community 134 - "Invoice → Stock → AR → Collection — test-only API slice"
Cohesion: 0.33
Nodes (5): API workflow, Boundaries, Current state, Invoice → Stock → AR → Collection — test-only API slice, Repeat verification safely

### Community 135 - "12. Observability & Logging"
Cohesion: 0.33
Nodes (6): 12.1 Application Logging, 12.2 Audit Trail, 12.3 Health Checks, 12.4 Metrics (Lightweight — No External Service), 12.5 Error Alerting, 12. Observability & Logging

### Community 136 - "2. Recommended Tech Stack (PROPOSAL)"
Cohesion: 0.33
Nodes (6): 2.1 Backend, 2.2 Frontend, 2.3 ORM & Migrations, 2.4 Authentication & Authorization, 2.5 PWA Tooling, 2. Recommended Tech Stack (PROPOSAL)

### Community 137 - "4. PostgreSQL Strategy"
Cohesion: 0.33
Nodes (6): 4.1 Version & Hosting, 4.2 Schema Organization, 4.3 Key Data Types, 4.4 Indexing Strategy, 4.5 Row-Level Security (RLS), 4. PostgreSQL Strategy

### Community 138 - "env.py"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode. This configures the context with just a URL…, Run migrations in 'online' mode. In this scenario we need to create an Engine…, run_migrations_offline(), run_migrations_online()

### Community 139 - "Independent current-code financial milestone review"
Cohesion: 0.40
Nodes (4): Envelope / budget, Exact inputs, Independent current-code financial milestone review, Review judgment

### Community 140 - "11. Performance & Reliability Targets"
Cohesion: 0.40
Nodes (5): 11.1 Response Time Targets, 11.2 Concurrency, 11.3 Availability, 11.4 Data Integrity, 11. Performance & Reliability Targets

### Community 141 - "5. Hosting & Server Details"
Cohesion: 0.40
Nodes (5): 5.1 Host Machine, 5.2 Server OS Recommendation, 5.3 Service Architecture (Production), 5.4 Local Development, 5. Hosting & Server Details

### Community 142 - "8. Architecture direction"
Cohesion: 0.40
Nodes (5): 8. Architecture direction, Architecture requirements, High-level target, Hosting situation, Zero-cost remote-access requirement

### Community 143 - "8. Architecture direction"
Cohesion: 0.40
Nodes (5): 8. Architecture direction, Architecture requirements, High-level target, Hosting situation, Zero-cost remote-access requirement

### Community 144 - "app/config.py"
Cohesion: 0.50
Nodes (3): _env_flag(), Feature flags driven by environment variables., Return True if the env var is a truthy literal, else default.

### Community 145 - "12. Validation States"
Cohesion: 0.50
Nodes (4): 12. Validation States, Business Rule Validation, Form-Level Validation, Real-Time Validation

### Community 146 - "7. Module F — Marketing"
Cohesion: 0.50
Nodes (4): 7. Module F — Marketing, F1. KOL / Doctor Spend, F2. Product / Brand Spend, F3. Objectives & KPIs

### Community 147 - "9. Module H — Analytics"
Cohesion: 0.50
Nodes (4): 9. Module H — Analytics, H1. Cross-Module Dashboard, H2. Telegram Integration, H3. WhatsApp (Future)

### Community 148 - "context/app/config.py"
Cohesion: 0.50
Nodes (3): _env_flag(), Feature flags driven by environment variables., Return True if the env var is a truthy literal, else default.

### Community 149 - "6. Remote Access & HTTPS Comparison"
Cohesion: 0.50
Nodes (4): 6.1 Candidate Comparison, 6.2 Recommendation, 6.3 DNS & Hostname, 6. Remote Access & HTTPS Comparison

### Community 150 - "7. Backup & Recovery"
Cohesion: 0.50
Nodes (4): 7.1 Backup Strategy, 7.2 Recovery Procedures, 7.3 Disaster Recovery, 7. Backup & Recovery

### Community 151 - "8. Supported Devices & Browsers"
Cohesion: 0.50
Nodes (4): 8.1 Browsers (minimum supported), 8.2 Devices, 8.3 PWA Install, 8. Supported Devices & Browsers

### Community 162 - "8. Module G — Purchasing"
Cohesion: 0.67
Nodes (3): 8. Module G — Purchasing, G1. Suppliers, G2. Material Purchases

### Community 170 - "10. Telegram & WhatsApp Integration"
Cohesion: 0.67
Nodes (3): 10.1 Telegram (Phase: Before Core Modules Complete), 10.2 WhatsApp (Later Phase), 10. Telegram & WhatsApp Integration

### Community 171 - "12. Migration and reconciliation requirements"
Cohesion: 0.67
Nodes (3): 12. Migration and reconciliation requirements, Migration stages, Precision rule

### Community 172 - "15. Open-source reference projects"
Cohesion: 0.67
Nodes (3): 15. Open-source reference projects, Additional references, Primary reference discussed

### Community 173 - "3. Source Excel workbooks"
Cohesion: 0.67
Nodes (3): 3. Source Excel workbooks, Current uploaded workbook names, Source preservation rules

### Community 174 - "6. Product requirements - planning scope"
Cohesion: 0.67
Nodes (3): 6. Product requirements - planning scope, Candidate business areas discovered/expected, Users / roles

### Community 175 - "9. Telegram first, WhatsApp later"
Cohesion: 0.67
Nodes (3): 9. Telegram first, WhatsApp later, Telegram, WhatsApp

### Community 176 - "12. Migration and reconciliation requirements"
Cohesion: 0.67
Nodes (3): 12. Migration and reconciliation requirements, Migration stages, Precision rule

### Community 177 - "15. Open-source reference projects"
Cohesion: 0.67
Nodes (3): 15. Open-source reference projects, Additional references, Primary reference discussed

### Community 178 - "3. Source Excel workbooks"
Cohesion: 0.67
Nodes (3): 3. Source Excel workbooks, Current uploaded workbook names, Source preservation rules

### Community 179 - "6. Product requirements - planning scope"
Cohesion: 0.67
Nodes (3): 6. Product requirements - planning scope, Candidate business areas discovered/expected, Users / roles

### Community 180 - "9. Telegram first, WhatsApp later"
Cohesion: 0.67
Nodes (3): 9. Telegram first, WhatsApp later, Telegram, WhatsApp

### Community 193 - "test_master_data_b.py"
Cohesion: 0.23
Nodes (18): _login_as(), _make_user(), B Master Data slice: read-only lookups for suppliers, chart of accounts,…, ``q`` is a literal substring search: % and _ must not act as wildcards., _seed_account(), _seed_branch(), _seed_doctor(), _seed_supplier() (+10 more)

### Community 194 - "make_demo.py"
Cohesion: 0.29
Nodes (13): Engine, apply_migrations(), build_demo_url(), create_database(), _fail(), int_to_datetime(), main(), date (+5 more)

### Community 195 - "test_pwa_invoice_ui.py"
Cohesion: 0.27
Nodes (11): Frontend wiring for the invoice desk. The PWA is framework-free vanilla JS…, _read(), test_app_never_injects_server_values_as_html(), test_app_validates_incomplete_lines_and_read_only_role(), test_app_wires_master_data_and_invoice_endpoints(), test_frontend_stays_framework_free(), test_i18n_keys_match_and_cover_the_screen(), test_index_has_invoice_screen_controls() (+3 more)

### Community 196 - "worker-delivered/app/finance/payments.py"
Cohesion: 0.18
Nodes (8): create_receipt(), _lock_receipt(), Payment receipt service: create, void, and list receipts linked to invoices.…, Void a receipt: append AR adjustment debit, flip status to Voided., Sum of Active receipt amounts for an invoice., Insert a receipt and its AR payment credit entry. Returns receipt_id., _sum_active_receipts(), void_receipt()

### Community 197 - "test_master_api.py"
Cohesion: 0.21
Nodes (5): _login_as(), Master-data lookup API that feeds the invoice screen. Scope must mirror invoice…, test_read_only_auditor_can_read_but_not_create(), test_rep_sees_only_granted_territories(), test_roles_outside_the_read_set_are_denied()

### Community 198 - "Client Prototype — Demo Guide"
Cohesion: 0.18
Nodes (10): Client Prototype — Demo Guide, Demo credentials (all synthetic), Device support & verification status, Five-minute walkthrough (as demo_owner), Known limitations, Showing it on a phone (same Wi-Fi), Startup (two commands, PowerShell), Temporary public link (Cloudflare quick tunnel) (+2 more)

### Community 199 - "B Master Data slice — verified evidence (2026-10-18)"
Cohesion: 0.18
Nodes (10): B Master Data slice — verified evidence (2026-10-18), Delivered, Files changed, Independent review, Next recommended task, Open business-policy questions, Regression found and fixed, Remaining risks (+2 more)

### Community 200 - "record_movement"
Cohesion: 0.31
Nodes (9): Append a movement and update its balance in the caller's transaction., record_movement(), _lines(), _lock_invoice(), post_invoice_atomic(), Atomic invoice posting and reversal: stock + AR in one transaction. Kept as…, Reverse a Posted invoice atomically (append-only compensating entries): 1.…, Post a draft invoice atomically: 1. decrement stock for each line… (+1 more)

### Community 201 - "test_invoice_excel.py"
Cohesion: 0.27
Nodes (9): Real-Excel reconciliation tests: invoke actual app calc (not re-derived…, App-level VAT extraction: total_net + vat_amount == grand_total. No assertion…, True if ws looks like a per-warehouse transaction sheet., Compare app net price AND line total against every numeric source row., Aggregate rows from transaction sheets across the first two workbooks and…, test_invoice_totals_invariant_on_real_rows(), test_line_total_matches_excel_cached_value(), test_vat_invariant_holds_but_not_excel_reconciled() (+1 more)

### Community 202 - "Evidence — client prototype stage `client-proto-20261018`"
Cohesion: 0.22
Nodes (8): 1. Scope delivered, 2. Seed verification (script self-check, zero constraint failures), 3. Regression (approved runner), 4. Actual browser flow (Chromium via built-in browser control), 5. Safety posture, Caught & fixed during browser testing, Evidence — client prototype stage `client-proto-20261018`, Evidence limitations

### Community 203 - "tests/test_posting.py"
Cohesion: 0.28
Nodes (7): posting_env(), fixture, Atomic Invoice -> Stock -> AR posting transaction (called directly). The HTTP…, _stock(), test_post_insufficient_stock_rolls_back_everything(), test_post_invoice_atomic_decrements_stock_creates_ar_and_posts(), test_post_rejects_non_draft_invoice()

### Community 204 - "AGENTS.md — ElsebaeyPharma / Medical Company System"
Cohesion: 0.25
Nodes (7): AGENTS.md — ElsebaeyPharma / Medical Company System, Current milestone, Development rules, HARD SAFETY RULES — never violate, Project, Test commands, Where things live

### Community 205 - "record_sale"
Cohesion: 0.32
Nodes (7): One debit entry per posted invoice (amount = grand_total)., record_sale(), _lines(), _lock_invoice(), post_invoice_atomic(), Atomic invoice posting: stock decrement + AR debit in one transaction. Kept as…, Post a draft invoice atomically: 1. decrement stock for each line…

### Community 206 - "app/main.py"
Cohesion: 0.32
Nodes (7): health(), meta(), get, Medical Company System API (Phase 2 — Platform Foundation). Current scope:…, Presentation flags for the PWA shell. ``demo_mode`` only lets the login screen…, Readiness probe: used by Docker + CI to confirm the API boots., root()

### Community 207 - "ElsebaeyPharma ERP — review unblock and recovery boundary"
Cohesion: 0.25
Nodes (7): ElsebaeyPharma ERP — review unblock and recovery boundary, Exact proposed write set if recovery is separately approved, Held candidate and exact NO_VERDICT diagnosis, Isolation recovery — proposal only; NO recovery writes authorized, Recorded state, not an assumption of empty/safe data, Review criteria and finite fallback, What does not require recovery approval

### Community 208 - "worker-delivered/app/sales/service.py"
Cohesion: 0.39
Nodes (7): _lines(), _lock_invoice(), post_invoice_atomic(), Atomic invoice posting and reversal: stock + AR in one transaction. Kept as…, Post a draft invoice atomically: 1. decrement stock for each line…, Reverse a Posted invoice atomically (append-only compensating entries): 1.…, reverse_invoice_atomic()

### Community 209 - "Sales UI slice — verified evidence (2026-10-18)"
Cohesion: 0.29
Nodes (6): Deliberately NOT done, Delivered, Sales UI slice — verified evidence (2026-10-18), Verification, What remains for the full Invoice → Stock → AR → Collections workflow, What this is

### Community 210 - "Final local code acceptance — PASS"
Cohesion: 0.33
Nodes (5): Accepted source, Delivered behavior, Exact closeout boundary, Final local code acceptance — PASS, Fresh native gates

### Community 211 - "Parent intake — current-code review accepted; release not approved"
Cohesion: 0.33
Nodes (5): Acceptance progression, Editorial corrections (original verdict unchanged), Findings disposition — no source changes, Independent method intake, Parent intake — current-code review accepted; release not approved

### Community 212 - "Final current-code acceptance — invoice-collection-20261017"
Cohesion: 0.40
Nodes (4): Final current-code acceptance — invoice-collection-20261017, Required judgment, Scope and authority, Strict tool envelope and output

### Community 213 - "GitHub first-push gate — BLOCKED"
Cohesion: 0.50
Nodes (3): Before the first push, Findings, GitHub first-push gate — BLOCKED

## Knowledge Gaps
- **887 isolated node(s):** `base`, `raw_sha256`, `bytes`, `diff_sha256`, `hunks` (+882 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1411 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_db()` connect `get_db` to `context/app/sales/router.py`, `app/inventory/router.py`, `worker-delivered/app/sales/router.py`, `files/tests/test_invoice_cycle_safety.py`, `tests/test_invoice_cycle_safety.py`, `customer_balance`, `app/sales/router.py`, `files/app/sales/router.py`, `InsufficientStock`, `files/tests/test_inventory_api.py`, `tests/test_inventory_api.py`, `reverse_invoice_atomic`, `app/auth/router.py`, `api-review-input/tests/test_invoice_api.py`, `tests/test_invoice_api.py`, `context/app/finance/router.py`, `app/finance/router.py`, `app/db.py`, `app/finance/payment_router.py`, `worker-delivered/app/finance/payment_router.py`, `files/app/finance/payment_router.py`, `test_ar_ledger.py`, `tests/test_collections.py`, `files/tests/test_invoice_cycle.py`, `files/tests/test_invoice_reversal.py`, `worker-delivered/tests/test_invoice_cycle.py`, `tests/test_invoice_cycle.py`, `tests/test_posting.py`, `master/router.py`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `verify_password()` connect `app/auth/router.py` to `api-review-input/app/auth/router.py`, `app/auth/repo.py`, `inventory-authorization/review-input/context/app/auth/router.py`, `invoice-cycle/review-input/context/app/auth/router.py`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `login()` connect `api-review-input/app/auth/router.py` to `app/auth/router.py`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `get_db()` (e.g. with `posting_env()` and `stock_env()`) actually correct?**
  _`get_db()` has 20 INFERRED edges - model-reasoned connections that need verification._
- **What connects `base`, `raw_sha256`, `bytes` to the rest of the system?**
  _887 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `context/app/sales/router.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07281772953414745 - nodes in this community are weakly interconnected._
- **Should `app/inventory/router.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09268707482993198 - nodes in this community are weakly interconnected._