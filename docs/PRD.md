# Product Requirements Document (PRD)

**Project:** Medical Company System (ERP-lite / Distribution Management System)
**Source:** 7 Arabic Excel workbooks (361 sheets) for an Egyptian medical distribution company
**Authoritative Spec:** `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (V2, 2026-10-10)
**Phase:** Phase 1 — Planning (six core documents)
**Status:** Draft — awaiting Eli approval

---

## 1. Project Goal

Build a custom, zero-cost/open-source-first business-management system that centralizes the business capabilities currently spread across 7 Excel workbooks into a reliable, PostgreSQL-backed web/PWA application for desktop and mobile. The system must preserve every relevant business capability unless an explicit decision changes it; improve reliability, auditability, reporting, statistics and usability; self-host on the company's always-on CEO-room PC while supporting secure access from other networks; implement Telegram before WhatsApp; use ERPNext and other open-source projects as design/reference material rather than making them the application codebase; and not start major implementation until discovery, requirements, schema, migration/reconciliation, security and implementation planning are documented well enough that no critical behavior must be guessed.

---

## 2. Users & Roles

Confirmed from V2 §6 and Eli's answers (`C:\Users\emadg\CrossDevice\Desktop\Answers.txt`, 2026-10-11). Role permissions are candidate and subject to confirmation during Phase 1 user interviews.

| Role | Can See | Can Create | Can Edit | Can Void/Cancel | Can Approve | Can Export | Must Never See | Desktop | Mobile |
|---|---|---|---|---|---|---|---|---|---|
| **CEO / Owner** | All modules including private/owner accounts | All | All | All | All | All | — | Yes | Yes |
| **System Administrator** | Platform module (settings, users, audit log, integrations); NO private/owner accounts | Users, roles, settings, audit filters | Settings, role assignments | Audit entries (log only) | Configuration changes | System reports, audit logs | Private/owner account detail rows | Yes | Limited |
| **Finance / Accounting** | Sales (posted invoices), Inventory (stock levels, movements), Finance (GL, AR, AP, Cash, BS, P&L, assets), Platform alerts | Invoices, cash entries, journal entries, asset records | Draft invoices/entries; void with reason code | Drafts freely; Posted items via void + reason code | Price overrides, discount overrides, expense approvals, stock adjustments, transfers (per reason code) | Financial reports (BS, P&L, AR/AP aging, cash), invoice exports | Private/owner accounts; other branches' transactions unless scoped | Yes | Yes |
| **Sales Manager** | All sales by all branches (rollups), inventory (branch-scoped), marketing (targets, spend), CRM/customer list | Sales orders (draft), returns (draft), sales targets, marketing activities | Draft invoices; edit price/discount within policy | Drafts freely; Posted invoices via manager approval + reason code | Returns, discount overrides, price overrides, marketing spend (up to limit) | Sales reports, territory reports, target vs actual, marketing summary | Private/owner accounts; finance GL/AP/Cash detail | Yes | Yes |
| **Sales Representative** | Own branch transactions, own customers, own territory, stock-visit form, own sales targets | Sales invoices (own customer/branch), customer stock-visit records, sell-through entries | Draft invoices; edit own draft invoices | Drafts freely; cannot void posted invoices | — | Own sales report, own customer statements, stock-visit export | All other branches' transactions; private/owner accounts; finance GL; competitor data | Yes (primary) | Yes (primary) |
| **Warehouse / Inventory** | All warehouses' stock levels, movements, batches, expiry, transfers | Stock receipts, transfers, adjustments (draft) | Draft adjustments; edit transfers before posting | Drafts freely; Posted items via manager approval + reason code | Stock adjustments, transfer approvals (within limit) | Inventory reports, stock-by-warehouse, batch/expiry reports, transfer summaries | Customer debt/balance; private/owner accounts | Yes | Limited (stock lookup) |
| **Branch / Area Manager** | Own branch sales, inventory, payroll (branch-only), marketing activities | Branch invoices, transfers (branch-scoped), marketing activities | Draft invoices; edit within branch | Drafts freely; Posted invoices via manager approval | Branch expense approvals, discount overrides (branch limit), transfers out of branch | Branch sales report, branch P&L summary, branch payroll summary | Other branches' data; private/owner accounts; GL/AP detail | Yes | Yes |
| **Read-Only / Auditor** | All posted transactions (read-only), audit timeline, reports | — | — | — | — | All reports (read-only export) | Private/owner accounts; draft entries | Yes | Yes |
| **Private / Owner Account Holder** | Only private/owner accounts module (separate schema/RLS boundary) | Private transactions, monthly summaries | Own private entries | Own entries (before posting) | Own entries | Private account summary | Main company transactions; sales; inventory; finance | Yes | Yes |

**Notes:**
- Roles above are candidates. Eli may add, remove or merge roles during Phase 1 interviews.
- "Cannot void posted" means a void transaction is created (audit trail preserved); original data is never deleted.
- Branch scoping means each branch sees only their own data unless explicitly granted cross-branch access (Sales Manager, CEO).
- Private/Owner accounts live in the **same PostgreSQL database** but in a separate protected schema/module with separate permissions, RLS policies and audit logs. No second database. (D10)

---

## 3. Feature List

### Module A — Platform (Foundation)

| ID | Feature | Description | Source Evidence |
|---|---|---|---|
| A-01 | Authentication | Email/password (or SSO if zero-cost option exists). Session management with expiration and revocation. | V2 §10 |
| A-02 | Role-Based Access Control | RBAC with the role matrix in §2 above. | V2 §6, D13 |
| A-03 | Audit Timeline | Immutable log of all creates, edits, voids, approvals with user, timestamp, old/new values. | D13; V2 §13 |
| A-04 | System Settings | Fiscal year, VAT rate, company info, currency (EGP), invoice/document numbering sequence. | D13 |
| A-05 | Posting Status Engine | Draft → Posted → Voided state machine for all financial/stock transactions. | D13 |
| A-06 | Reason Codes | Predefined codes for returns, voids, adjustments, overrides — required at void/approve time. | D13 |
| A-07 | Alert Engine | Configurable alerts: low stock, overstock, near expiry, overdue AR, credit-limit exceeded. | D13, V2 §2B.15 |
| A-08 | Import Validation | CSV/XLSX import with preview, duplicate detection, rejected-row report, reconciliation counts. | D13 |
| A-09 | Global Search | Search across customers, invoices, products, collections, transfers (single search bar, role-scoped results). | D13 |
| A-10 | Integration Settings | Telegram bot configuration (token, authorized users, command whitelist). WhatsApp deferred. | D6, V2 §9, D13 |
| A-11 | Credit Management | Customer credit limits, holds, aging buckets, manager override workflow. | D13 |
| A-12 | Simple Approvals | Configurable approval thresholds for returns, discounts, price overrides, expenses, stock adjustments, warehouse transfers. | D13 |
| A-13 | Dashboard Shell | Responsive layout with navigation, global search, alert badge, user menu. Framework for KPI widgets. | V2 §7 |

### Module B — Master Data

| ID | Feature | Description | Source Evidence |
|---|---|---|---|
| B-01 | Customers | Pharmacies, distributors, companies. Fields: name, type, branch, territory, contact, phone, address, credit limit, aging bucket, status. | V2 §6, EXCEL_TO_SYSTEM_MAPPING |
| B-02 | Suppliers / Vendors | Supplier master for purchasing module (discovery-gated depth). | D11 |
| B-03 | Items / Products | Drug/medical product catalog. Fields: SKU, name (AR/EN), brand, category, batch tracking enabled flag, expiry tracking enabled flag, UOM (box/pack/unit optional per D13), cost price, selling price. | V2 §2B.6–7, D13 |
| B-04 | Warehouses | Company-owned warehouses (Dakahlia, Sharqia, Fayoum, 6 October, Gharbia implied from routing rules). Fields: name, location/governorate, active flag. | V2 §2B.1–2 |
| B-05 | Territories / Regions | Sales territories distinct from warehouses. Fields: name, parent territory, assigned branch. | V2 §2B.1 |
| B-06 | Representatives | Sales reps with assignment to territory/branch. Fields: name, employee ID, territory, branch, contact. | V2 §2B.1 |
| B-07 | Districts / Governorates | Dakahlia, Sharqia, Fayoum, 6 October, Gharbia, etc. Parent of territory. | V2 §2B.2 routing rules |
| B-08 | Specialties | Doctor/KOL specialty (e.g., pediatrics, cardiology). Used for marketing spend linking. | V2 §2B.16 |
| B-09 | Categories | Product categories (drug class, therapeutic area). | V2 §6 |
| B-10 | Payment Methods | Cash, check, transfer, credit terms. | D13 |
| B-11 | UOM (optional) | Box/pack/unit conversions **only if real operations use them**. Light weight. | D13 |
| B-12 | Chart of Accounts | Minimal COA supporting AR, AP, Cash, Revenue, Expense, Assets. | D13, EXCEL_TO_SYSTEM_MAPPING |
| B-13 | Doctor / KOL List | Master list of doctors with name, specialty, area/territory. Imported from `حسابات خاصه.xlsx::Sheet1`. | D22, V2 §2B.16 |

### Module C — Sales

| ID | Feature | Description | Source Evidence |
|---|---|---|---|
| C-01 | Sales Invoice (Create/Edit/Void) | Full invoice: customer, date, branch, territory, source warehouse, representative, lines (product, batch, qty, unit price, discount %, net price, VAT). | V2 §2B.1–5, D18 |
| C-02 | Net Price Formula | `E = C × (1 − D)` where C = unit price, D = discount %, E = net price per line. Hardcoded rule, not spreadsheet-cell dependent. | D18, EXCEL_TO_SYSTEM_MAPPING |
| C-03 | Branch-Scoped Rollups | HQ summary (`الرئيسية`) per branch showing per-warehouse/month totals. Auto-recomputed from posted transactions. | EXCEL_TO_SYSTEM_MAPPING, CURRENT_WORKFLOWS |
| C-04 | Sold Balances Ledger | Per-customer/agent sold-balance ledger with dates, quantities, prices, debit/credit/net. Auto-updated on invoice post/void. | EXCEL_TO_SYSTEM_MAPPING |
| C-05 | Price List / Full Quantities (`كامل الكمية`) | Current item stock with price, discount, net price, cumulative quantity by item. | EXCEL_TO_SYSTEM_MAPPING |
| C-06 | Under-Disposal Stock View (`تحت التصريف`) | Per-line stock view (allocated/committed inventory). | EXCEL_TO_SYSTEM_MAPPING |
| C-07 | Hide Zero-Quantity Invoice Lines | Printed/PDF invoices omit product lines where qty = 0. | V2 §2B.4 |
| C-08 | VAT Calculation | VAT applied per invoice line per approved business formula. Stored and reproducible per line. | V2 §2B.5 |
| C-09 | Sell-In Tracking | Quantity invoiced/delivered from company to customer. Stored separately from sell-through. | V2 §2B.8 |
| C-10 | Sales Targets | Targets by representative, territory, product, period. Actual vs target comparison. | V2 §2B.13 |
| C-11 | Customer Stock-Visit Workflow | Mobile-optimized form: previous stock, new order/delivery, returns, current stock, calculated sell-through, collection info, notes, rep, date. | V2 §2B.10 |
| C-12 | Automatic Sell-Through Calculation | `Sell-through = Previous customer stock + New delivered — Returns − Current customer stock`. Exceptions documented. | V2 §2B.10–11 |
| C-13 | Customer/Product Returns | Explicit return transaction: customer, product, qty, date, warehouse, batch, reason code. Not silent invoice edit. | V2 §2B.12 |
| C-14 | Territory ≠ Warehouse | Sales territory and source warehouse are separate fields on every sale transaction. Reporting uses territory; stock deduction uses source warehouse. | V2 §2B.1, §2C |
| C-15 | Warehouse Routing Rules | Default source warehouse suggestion by territory (e.g., Dakahlia sales → Dakahlia warehouse; Sharqia → Dakahlia; Fayoum → Fayoum; 6 Oct → 6 Oct; Gharbia → either). Actual source warehouse stored on transaction. | V2 §2B.2 |

### Module D — Inventory

| ID | Feature | Description | Source Evidence |
|---|---|---|---|
| D-01 | Stock by Warehouse | Current stock levels per product per warehouse, with batch detail where applicable. | V2 §2B.6–7 |
| D-02 | Batch Tracking | Every stock movement attributable to a batch number. Remaining stock reconstructible by batch. | V2 §2B.6 |
| D-03 | Expiry-Date Tracking | Batches have expiry dates. View stock by expiry; warning on approaching expiry; expiry preserved on invoice lines. | V2 §2B.7 |
| D-04 | Warehouse-to-Warehouse Transfers | Stock movements between company warehouses. Decrease source, increase destination, preserve batch info. Not a sale (no debt, no revenue, no territory sales impact). | V2 §2B.3 |
| D-05 | Stock Cover Calculation | `Stock Cover = Current stock / recent average sales rate`. Configurable averaging window. Available by product, by warehouse, optionally company-wide. | V2 §2B.14 |
| D-06 | Overstock Alerts | Flag products/warehouses where stock cover exceeds configurable threshold (not hardcoded). | V2 §2B.15 |
| D-07 | Low-Stock / Attention Alerts | Alert when stock falls below configurable reorder point. | D13 |
| D-08 | Stock Adjustments | Manual stock adjustment (found, damaged, lost) with reason code and manager approval. | D13 |
| D-09 | FEFO Behavior (Future) | Future-first-out functionality if approved. Not in MVP unless explicitly required. | V2 §2B.7 |

### Module E — Finance

| ID | Feature | Description | Source Evidence |
|---|---|---|---|
| E-01 | Cash Ledger (`النقديه`) | Debit/credit entries with running balance. | EXCEL_TO_SYSTEM_MAPPING |
| E-02 | AR Ledger (`العملاء`) | Normalized AR entries: customer, date, rep, description, debit, credit, running balance. Wide columnar source (747 cols) → normalized model. | D23, EXCEL_TO_SYSTEM_MAPPING |
| E-03 | AP Ledger | Supplier payables (discovery-gated depth). | D11 |
| E-04 | GL / Journal Entries | General ledger entries with debit/credit mapping to COA. | V2 §6 |
| E-05 | Chart of Accounts | Minimal COA supporting BS and P&L. | D13 |
| E-06 | Balance Sheet (`الميزانيه` / `الموازنه العامه`) | Aggregate and detailed BS: assets, liabilities, capital/partners, net profit, distribution, market value. | EXCEL_TO_SYSTEM_MAPPING |
| E-07 | P&L (`الارباح والخسائر`) | P&L summary. | EXCEL_TO_SYSTEM_MAPPING |
| E-08 | Revenue Detail (`الايرادات`) | Revenue breakdown. | EXCEL_TO_SYSTEM_MAPPING |
| E-09 | Cost Detail (`التكاليف`) | Cost breakdown. | EXCEL_TO_SYSTEM_MAPPING |
| E-10 | Expense Detail (`المصروفات`) | Expense breakdown. | EXCEL_TO_SYSTEM_MAPPING |
| E-11 | Fixed Assets (`الاصول الثابته`) | Asset register with depreciation tracking. | EXCEL_TO_SYSTEM_MAPPING |
| E-12 | Current Assets (`الاصول المتغيره`) | Current asset register. | EXCEL_TO_SYSTEM_MAPPING |
| E-13 | Payroll (Lightweight) | Salary records and payments per branch. Net = B − C − D. No HR/attendance/leave/taxes unless real workflow proves need. | D9, EXCEL_TO_SYSTEM_MAPPING |
| E-14 | AR Aging | Customer-by-customer aging buckets. | D13 |

### Module F — Marketing

| ID | Feature | Description | Source Evidence |
|---|---|---|---|
| F-01 | Doctor/KOL Marketing Spend | Link expense/activity to doctor/KOL, specialty, area/territory, date, amount, activity type, notes. | V2 §2B.16 |
| F-02 | Product/Brand-Linked Marketing Spend | Explicit link to one or more products/brands. No inference from free text. | V2 §2B.17 |
| F-03 | Marketing Activity Objective + KPI | Track objective, expected outcome/KPI, actual result, follow-up notes, product/brand, target doctor/KOL. Enables future ROI analysis without complex ROI model in V1. | V2 §2B.18 |
| F-04 | Sales Targets (Marketing-Linked) | Targets by rep/territory/product with marketing-activity linkage. | V2 §2B.13 |

### Module G — Purchasing (Progressive)

| ID | Feature | Description | Source Evidence |
|---|---|---|---|
| G-01 | Suppliers | Supplier master (import from existing data). | D11 |
| G-02 | Purchase Orders (if confirmed) | PO creation and tracking — only if Excel discovery proves real use. | D11, D20 |
| G-03 | Goods Receipt (if confirmed) | GRN — only if Excel discovery proves real use. | D11, D20 |
| G-04 | Raw Materials / Manufacturing Costs (if confirmed) | Only the real existing data/workflows, built progressively. No full MRP/BOM/PO/GRN until discovery proves use. | D11 |
| G-05 | Purchase Payments | AP-linked payments to suppliers. | D11 |

### Module H — Executive Analytics / Telegram

| ID | Feature | Description | Source Evidence |
|---|---|---|---|
| H-01 | Executive Dashboard | Cross-module KPIs: sales today/week/month/year, collections today/week/month, receivables, revenue, expenses, gross/net profit, profit/loss trend, sales by governorate/area/branch, sales by rep, top customers, highest outstanding balances, product performance, inventory value, low-stock alerts, overdue payments. | V2 §7 |
| H-02 | KPI Formula Definitions | Every KPI has an exact formula/business definition documented before implementation. No guessing. | V2 §7 |
| H-03 | Telegram Integration | Bot commands: daily executive summary, customer/account lookup, outstanding balance lookup, low-stock alerts, collection/payment alerts, exception alerts, scheduled reports, links back to app. Whitelist authorized users. Read-only first; write actions require explicit approval. | V2 §9, D6 |
| H-04 | WhatsApp (Later Phase) | Deferred. Does not block core system. | V2 §9, D6 |
| H-05 | Export / Report | PDF invoice print (hide zero-qty lines), Excel/CSV export for all reports. | V2 §2B.4, D13 |

---

## 4. User Goals

| User | Goals |
|---|---|
| CEO / Owner | See real-time business picture (sales, collections, profit, stock) without opening 7 Excel files. Control private/owner accounts separately. Receive Telegram alerts. Approve exceptions. |
| System Administrator | Set up users, roles, system settings. Monitor audit log. Configure Telegram bot. Import data with validation. Ensure backups run. |
| Finance / Accounting | Record and manage AR, AP, cash entries. Produce Balance Sheet and P&L without Excel cross-references. Age receivables. Track assets. Process payroll (lightweight). |
| Sales Manager | Manage all branches' sales. Set and track targets. Monitor territory performance. Approve discounts/returns/overrides. View sell-through reports. |
| Sales Representative | Enter invoices quickly on mobile. Visit customers and record stock/sell-through. See own targets vs actual. Check own customer balances. |
| Warehouse / Inventory | Know exact stock by warehouse and batch. Track expiry. Move stock between warehouses. Get alerted on low/over stock. |
| Branch / Area Manager | Manage own branch's operations. Approve branch-level exceptions. View branch P&L and payroll. |
| Read-Only / Auditor | Review any posted transaction with full audit trail. Export reports. Cannot modify data. |
| Private / Owner Account Holder | Manage personal/company-external accounts in isolation. No visibility into main company transactions. |

---

## 5. Business Rules (Cited to Evidence)

| Rule ID | Rule | Evidence Source |
|---|---|---|
| BR-01 | Net price: `E = C × (1 − D)` where C = unit price, D = discount %, E = net price per line. | D18, EXCEL_TO_SYSTEM_MAPPING (§ C.02) |
| BR-02 | Payroll net: `E = B − C − D` (basic − deductions − payments = net). | D18, EXCEL_TO_SYSTEM_MAPPING (§ E-13) |
| BR-03 | AR running balance: `D = prev + E − F` (prev balance + debit − credit). | D18, OPEN_QUESTIONS.md §6a |
| BR-04 | Sell-through formula: `Previous customer stock + New delivered — Returns − Current customer stock`. Any exception must be documented, not silently changed. | V2 §2B.11 |
| BR-05 | Stock Cover formula: `Current stock / recent average sales rate`. Averaging window is configurable, not hardcoded. | V2 §2B.14 |
| BR-06 | Territory ≠ Warehouse. Sales territory drives territory reporting; source warehouse drives stock deduction. Both stored on every sales transaction. | V2 §2B.1, §2C |
| BR-07 | Warehouse-to-warehouse transfer: decreases source, increases destination, preserves batch, creates NO customer debt, NO sales revenue, NO territory sales impact. | V2 §2B.3 |
| BR-08 | Printed/PDF invoice omits product lines with quantity = 0. Underlying catalog may still contain those products. | V2 §2B.4 |
| BR-09 | VAT calculation is consistent across products, stored/reproducible per invoice line, calculated from approved formula, validated against existing invoice output during migration. | V2 §2B.5 |
| BR-10 | Batch tracking: every stock movement attributable to a batch; remaining stock reconstructible by batch. | V2 §2B.6 |
| BR-11 | Expiry tracking: batches have expiry dates; system supports view-by-expiry, warning on approaching expiry, expiry on invoice lines. | V2 §2B.7 |
| BR-12 | Sell-in ≠ Sell-through. Store separately. Sell-through must not be inferred from sell-in alone. | V2 §2B.8–9, §2C |
| BR-13 | Sale ≠ Collection. Invoice creates AR; collection reduces AR. They are separate transaction types. | V2 §2C |
| BR-14 | Invoice ≠ Payment. Payment is a separate transaction against an invoice or AR entry. | V2 §2C |
| BR-15 | Product ≠ Batch. One product can have many batches with different expiry dates. | V2 §2C |
| BR-16 | Return is an explicit transaction (not a silent invoice edit). Records customer, product, qty, date, warehouse, batch, reason/status. | V2 §2B.12 |
| BR-17 | Sales targets stored by representative, territory, product, and period. Actual performance comparable against target. | V2 §2B.13 |
| BR-18 | Overstock threshold is configurable, not hardcoded as a permanent accounting rule. | V2 §2B.15 |
| BR-19 | Marketing spend links explicitly to doctor/KOL **and/or** product/brand. System must not require inference from free text. | V2 §2B.16–17 |
| BR-20 | Marketing activity tracks objective, expected KPI, actual result, follow-up notes. Enables future ROI analysis without forcing complex ROI model into V1. | V2 §2B.18 |
| BR-21 | Private/Owner accounts: same PostgreSQL DB, separate protected module with separate permissions, RLS policies, audit logs, ideally separate schema/tables. No second database. | D10 |
| BR-22 | No hard delete of posted financial/stock records. Use status/void/reversal patterns. Immutable audit trail for sensitive actions. | V2 §11 |
| BR-23 | Money uses exact numeric/decimal type (never floating point). Currency explicitly defined (EGP). | V2 §11 |
| BR-24 | Branch scoping: 5 sales workbooks = 5 branches. Same-named sheets are branch-scoped; key everything by `(workbook, sheet)`. | D17 |
| BR-25 | Placeholder/unnamed sheets (53) excluded from import unless confirmed business-relevant. | D19 |

---

## 6. Edge Cases

| # | Edge Case | Handling |
|---|---|---|
| 1 | **Zero-quantity line on invoice** | Line exists in database (audit trail), hidden on print/PDF. |
| 2 | **Return without original invoice reference** | Allowed with reason code; system flags unlinked return for audit review. |
| 3 | **Transfer between warehouses with different batch expiry** | Batch metadata (batch number, expiry) copied to destination; source batch remaining qty updated. |
| 4 | **Sell-through negative result** | Formula may produce negative (data error or unrecorded loss). System allows but flags for review. |
| 5 | **Customer exceeds credit limit on invoice post** | Hard block unless sales manager overrides with reason code. Override logged in audit. |
| 6 | **Cross-workbook external link missing at import** | `حسابات خاصه.xlsx::اجمالى الحسابات` references a missing Mansoura workbook. Import flagged; consolidation recomputed from local copies where possible; missing link logged. (D21) |
| 7 | **Duplicate customer/product across branches** | Normalize to single entity; branch context added as attribute, not duplicate record. |
| 8 | **AR ledger wide-column period mapping** | 747-column AR ledger (period columns) → normalized entries at import. Period granularity confirmed during discovery; exact date mapping per column validated. (D23) |
| 9 | **Posted invoice voided** | Void creates reversal entry; original row stays in DB (soft void); audit log captures who, when, why. |
| 10 | **Payroll net formula variance** | If real data shows `E ≠ B − C − D`, documented as exception; formula not silently changed. |
| 11 | **Private accounts cross-reference to main company data** | Private accounts aggregation (`اجمالى الحسابات`) may reference main-company data. Access controlled by RLS: owner sees both; other roles see only main-company data without private aggregation. |
| 12 | **Concurrent invoice creation by two reps for same customer** | Database transaction isolation prevents double-counting; unique constraint on invoice number per branch/period. |
| 13 | **Expiry-date batch fully expired** | System warns on stock view; invoice line can still be posted (business decision) but flagged with expiry-warning tag. |
| 14 | **Missing or stale external workbook links at import time** | Migration tool must fail loudly with clear error listing missing workbooks; never silently ignore. |
| 15 | **Offline PWA use** | PWA caches read-only data; writes require network. Offline queue for mobile stock-visit entry if feasible (deferred to Phase 2 if needed). |

---

## 7. Acceptance Criteria

### Module A — Platform
- [ ] Users can create, edit, deactivate accounts; roles assign correctly.
- [ ] RBAC enforces the permission matrix in §2 for all modules.
- [ ] Audit timeline records every create/edit/void/approve with user, timestamp, old/new values.
- [ ] System settings (fiscal year, VAT, company info, currency, numbering) are persisted and visible to admin.
- [ ] Draft invoices cannot appear in financial reports; posted invoices can.
- [ ] Reason code is mandatory at void/approve time; audit captures the code.
- [ ] Import validation previews rows, flags duplicates, rejects invalid rows, shows reconciliation count.
- [ ] Global search returns role-scoped results only.
- [ ] Telegram bot connects with configured token; unauthorized users get no data.
- [ ] Credit hold blocks invoice post; override requires manager role + reason code.
- [ ] Simple approval workflow routes requests to correct approver role.
- [ ] Dashboard shell loads with navigation, search bar, alert badge, user menu.

### Module B — Master Data
- [ ] All customer, supplier, product, warehouse, territory, rep, doctor/KOL entities are CRUD-manageable.
- [ ] Duplicate detection on import (by name + branch/territory).
- [ ] UOM conversion present only if box/pack/unit are used (confirmed per D13).
- [ ] Doctor/KOL list imported from `حسابات خاصه.xlsx::Sheet1` with specialty and area fields.

### Module C — Sales
- [ ] Invoice creation: all fields (customer, date, branch, territory, source warehouse, rep, lines) required and validated.
- [ ] Net price `E = C × (1 − D)` computed correctly for every line.
- [ ] VAT computed per line per approved formula; stored and reproducible.
- [ ] Zero-quantity lines hidden on printed/PDF invoice.
- [ ] Territory ≠ warehouse enforced: both fields mandatory and independent.
- [ ] Warehouse routing suggests default but allows manual override; actual source warehouse stored.
- [ ] Branch rollup (`الرئيسية`) auto-recomputes from posted transactions; totals match Excel sample for tested branch.
- [ ] Sold balances ledger updates on invoice post/void/return.
- [ ] Sell-in and sell-through stored separately.
- [ ] Stock-visit form works on mobile (touch-friendly, minimal fields).
- [ ] Sell-through auto-calculated per BR-04; exceptions documented.
- [ ] Return creates explicit transaction; original invoice untouched.
- [ ] Sales targets CRUD; actual vs target report shows variance.

### Module D — Inventory
- [ ] Stock by warehouse + batch view accurate after any transaction.
- [ ] Batch number mandatory on stock receipt and invoice line where batch tracking enabled.
- [ ] Expiry date stored on batch; approaching-expiry warning configurable.
- [ ] Warehouse transfer: source decreases, destination increases, batch preserved, no AR impact.
- [ ] Stock cover computed and displayed by product/warehouse.
- [ ] Overstock alert fires when configurable threshold exceeded.
- [ ] Low-stock alert fires when reorder point breached.
- [ ] Stock adjustment requires reason code and approval if posted.

### Module E — Finance
- [ ] Cash ledger entries post with running balance; balances reconcile to source samples.
- [ ] AR ledger normalized from wide-column source; customer balance matches source total (row 1 = 2,200,000 EGP for tested sample).
- [ ] AP ledger posts (depth gated — only confirmed workflows imported).
- [ ] Journal entries balance (debit = credit).
- [ ] Balance Sheet and P&L reconcile to Excel source samples (formula-equivalent totals).
- [ ] Fixed/current asset register tracks acquisition, depreciation, net book value.
- [ ] Payroll net `E = B − C − D` computed correctly for all branch records.

### Module F — Marketing
- [ ] Doctor/KOL spend linked to doctor, specialty, territory, product/brand.
- [ ] Marketing activity has objective, expected KPI, actual result, notes.
- [ ] Spend rollup by product/brand available.

### Module G — Purchasing
- [ ] Suppliers imported and manageable.
- [ ] PO/GRN/MRP built only if discovery proves use; otherwise deferred. (D11, D20)

### Module H — Analytics / Telegram
- [ ] Executive dashboard shows all KPIs from V2 §7 with documented formulas.
- [ ] Each KPI formula is documented in-app and in `TECHNICAL_REQUIREMENTS.md`.
- [ ] Telegram bot sends daily summary, responds to lookup commands, alerts on configured events.
- [ ] WhatsApp not implemented; does not block any core feature.
- [ ] Export to PDF/Excel works for all reports.

### Cross-Cutting
- [ ] PWA installs and works on desktop browser and mobile browser.
- [ ] Arabic (RTL) and English (LTR) UI toggle works; all labels translated.
- [ ] PostgreSQL never exposed publicly; accessible only via application server.
- [ ] HTTPS enforced for all remote access.
- [ ] Backup and restore procedure tested.
- [ ] Server reboot test passes (application and DB recover cleanly).
- [ ] Migration reconciliation report proves source-to-system equivalence for imported data.
- [ ] Private/owner accounts accessible only to CEO/owner and admin; other roles see nothing.

---

## 8. Out-of-Scope Items

| Item | Reason |
|---|---|
| Budgeting | Discovery-gated; not a V2 confirmed feature. (D24, V2 §2B) |
| Full MRP / BOM / PO / GRN system | Progressive scope — build only what real data proves is used. (D11, D20) |
| Deep Payroll (HR, attendance, leave, taxes, complex formulas) | Lightweight only: salary records/payments. Deeper HR gated. (D9) |
| WhatsApp integration | Later phase; must not block core. (V2 §9, D6) |
| Patient/medical records | No evidence in source workbooks; do not assume. (V2 §10) |
| UOM beyond box/pack/unit | Only if real operations use conversions. (D13) |
| Multi-tenant architecture | Single company; no tenant isolation needed. |
| Offline-first PWA with write queue | Deferred unless mobile stock-visit workflow proves need. |
| AI/ML-driven forecasting | Out of scope for V1; data quality must be established first. |
| Complex ROI model for marketing | V1 tracks objective/KPI/result; ROI calculation deferred. (V2 §2B.18) |
| ERPNext as application base | Reference only; custom build. (D2) |
| Second PostgreSQL database | Private accounts in same DB, separate schema/RLS. (D10) |
| Hard deletes of posted financial/stock records | Soft void/reversal pattern only. (V2 §11) |
| Preserving Excel formula mechanics | Preserve business logic; replace spreadsheet implementation with database logic. |
| Replicating placeholder/unnamed sheets as business data | 53 placeholders excluded unless confirmed. (D19) |

---

## 9. Priorities

| Priority | Modules / Features | Rationale |
|---|---|---|
| **P0 — Foundation** | Module A (Platform), Module B (Master Data) | Everything depends on auth, roles, settings, and clean master data. |
| **P1 — Core Transactions** | Module C (Sales), Module D (Inventory) | Sales and inventory are the primary business cycle; Finance depends on posted sales. |
| **P2 — Financial Reporting** | Module E (Finance) — Cash, AR, GL, BS, P&L | Financial truth depends on Sales/Inventory being posted. |
| **P3 — Marketing & Purchasing** | Module F (Marketing), Module G (Purchasing, gated) | Marketing tracked alongside sales; purchasing progressive. |
| **P4 — Analytics & Telegram** | Module H (Executive Dashboard, Telegram) | Depends on trustworthy data from A-G. |
| **P5 — Private/Owner Accounts** | Protected module (same DB, separate schema/RLS) | Security boundary; can be built parallel to P1 but gated on RBAC. |
| **Deferred** | WhatsApp, Deep Payroll, Full MRP, Budgeting, Complex ROI | Out of scope or discovery-gated. |

**Build order:** A → B → C → D → E → F → G → H (with Private Accounts parallel to A).

---

## 10. Unresolved Questions

| # | Question | Impact | Status |
|---|---|---|---|
| UQ-1 | Exact role list — are all 9 roles in §2 confirmed, or should some be merged/split? | RBAC design | Open — confirm with Eli |
| UQ-2 | What is the AR ledger period granularity? (747 columns = how many periods? Daily? Monthly?) | Finance schema, migration mapping | Open — needs deeper sheet inspection |
| UQ-3 | What is the exact averaging window for stock cover (BR-05)? 30 days? 90 days? Trailing months? | Inventory algorithm | Open — confirm with business owner |
| UQ-4 | What is the overstock threshold (configurable value in BR-18)? | Alert configuration | Open — needs business input |
| UQ-5 | What is the low-stock reorder point (configurable per product or flat)? | Alert configuration | Open — needs business input |
| UQ-6 | Are there any UOM conversions actually used in the workbooks (box/pack/unit)? | Master data design | Gated — confirm during discovery |
| UQ-7 | What specific Telegram commands and alert types does Eli want first? | Module H scope | Open — confirm with Eli |
| UQ-8 | What is the exact VAT rate and rule (standard, reduced, exempt lines)? | Invoice calculation | Open — confirm from Excel VAT logic |
| UQ-9 | Are there credit terms (payment due date, late fees) used in the current workflow? | Credit management scope | Open — confirm from AR ledger |
| UQ-10 | What is the final product/project name? | Branding, UI title | Open |
| UQ-11 | Backend framework, frontend framework, hosting OS — have these been decided? | Technical requirements | Open — D21 says D19 (hosting) still open |
| UQ-12 | Does the company need Egypt-specific regulatory compliance (tax authority, e-invoicing)? | Security/legal scope | Open — D26 notes regulatory obligation unknown |
| UQ-13 | Is 2FA required? | Security baseline | Open — V2 §10 lists as open |
| UQ-14 | What is the approved backup destination and offsite-copy method? | Backup/recovery plan | Open — V2 §19 lists as open |
| UQ-15 | Arabic/English localization: which language is primary in the UI? Is full RTL required? | Design brief scope | Open — V2 §19 lists as open |

---

## 11. References

- `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (authoritative spec)
- `docs/DECISION_LOG.md` (D1–D26)
- `docs/OPEN_QUESTIONS.md` (all resolved; UQ-1 to UQ-15 are new/open)
- `docs/MODULE_MAP.md` (module definitions, build order)
- `docs/EXCEL_TO_SYSTEM_MAPPING.md` (sheet → system mapping with citations)
- `docs/CURRENT_WORKFLOWS.md` (inferred workflows from formulas)
- `docs/DATA_DICTIONARY.md` (field names and types from source)
- `docs/SOURCE_WORKBOOK_INVENTORY.md` (7 workbooks, 361 sheets, hashes)
- `docs/EXCEL_FEATURE_CATALOG.md` (formulas, links, merges, validations)
- `docs/ENTITY_DUPLICATE_REPORT.md` (86 duplicate sheet names, 53 placeholders)
- `docs/MIGRATION_RECONCILIATION_PLAN.md` (migration phases, reconciliation checks)
- `C:\Users\emadg\CrossDevice\Desktop\Answers.txt` (Eli's answers, 2026-10-11)
