# Audit: App vs Original Workbooks + Approved Additions (corrected)

Inspection only. No code/DB/workbook modified. Evidence refs are workbook → sheet → cell/formula where verifiable; unavailable evidence marked UNVERIFIED.

## Corrected audit table

Columns: Business requirement (source) | App feature | Status | Verdict | Reason

### A. Business requirements evidenced in workbooks

| Requirement | Workbook → Sheet (ref) | App feature | Status | Verdict | Reason |
|---|---|---|---|---|---|
| Territory ≠ source warehouse | V2 §2B.1 | Invoice desk (territory_id + warehouse_id) | REAL | KEEP | Approved distinction preserved |
| Warehouse routing rules | V2 §2B.2 | Inventory scoping (branch grants) | REAL (internal) | KEEP (no standalone screen) | Behavior preserved in `_scope_warehouses`; standalone screen hidden (empty PROTO) |
| Warehouse→warehouse transfer | V2 §2B.3; `حسابات خاصه.xlsx` → `اجمالى الحسابات شهر 6/7` (term "تحويل" present; cell UNVERIFIED) | `/transfers` + screen | REAL | KEEP | Approved + workbook term present |
| Hide zero-qty invoice lines | V2 §2B.4 | Print view | REAL | KEEP | Matches Excel printed invoices |
| VAT per line | V2 §2B.5 | Invoice lines (vat_rate, vat_amount) | REAL | KEEP | Approved formula |
| Batch tracking | V2 §2B.6; sales workbooks (batch cols UNVERIFIED) | Batches screen + `/inventory/batches` | REAL | KEEP | Approved; sheet evidence UNVERIFIED |
| Expiry tracking | V2 §2B.7 | Batches (expiry) + invoice check | REAL | KEEP | Approved |
| Sell-in tracking | V2 §2B.8 | Invoice lines quantity | REAL | KEEP | Approved |
| Sell-through tracking | V2 §2B.9; sales workbooks (`رصيد الارصدة المباعة`) | Visits screen + calc | REAL (formula) | KEEP | Approved formula preserved verbatim |
| Customer stock visit | V2 §2B.10 | Visits screen | REAL | KEEP | Mobile workflow |
| Auto sell-through calc | V2 §2B.11 | `prev + delivered − returns − current` | REAL | KEEP | Approved formula |
| Explicit returns | V2 §2B.12; sales workbooks (sheets `تحت التصريف`, `عهدة ...`, `مخزن ...`, `كامل الكمية` contain "مرتجع") | `/returns` + screen | REAL | KEEP | Approved + workbook term present |
| Sales targets | V2 §2B.13; term "هدف" NOT found in any workbook (UNVERIFIED) | `/targets` + screen | REAL | KEEP (SIMPLIFY) | Approved addition; Excel evidence unavailable → mark unverified |
| Stock cover | V2 §2B.14 | `/inventory/cover` + screen | REAL | KEEP | Approved formula |
| Overstock alerts | V2 §2B.15 | Cover screen (status) | REAL | KEEP | Approved threshold (D41) |
| KOL spend | V2 §2B.16; `حسابات خاصه.xlsx` → Sheet1 (doctor list) | `/marketing/spend` + screen | REAL | KEEP (SIMPLIFY) | Approved; spend ledger is new (no Excel equivalent) |
| Product/brand spend | V2 §2B.17 | join table `marketing_spend_product` | REAL | KEEP | Approved; structured link |
| Marketing objective/KPI | V2 §2B.18 | `/marketing/objectives` + screen | REAL | KEEP (SIMPLIFY) | Approved; no Excel equivalent |

### B. Finance requirements (corrected: required-but-unbuilt/deferred, not REMOVE)

| Requirement | Workbook → Sheet (ref) | App feature | Status | Verdict | Reason |
|---|---|---|---|---|---|
| Balance sheet | `الميزانية العمومية 2026` → `الموازنه العامه`, `الميزانيه` (formulas: `=الميزانيه!A2`, `=H4`, etc.) | MISSING | Required-but-unbuilt | Finance reports evidenced in Excel; app has COA only |
| P&L | same workbook → `الارباح والخسائر` (formulas `='الموازنه العامه'!C9`) | MISSING | Required-but-unbuilt | Evidenced; not built |
| Cash ledger | same → `النقديه` (formulas `=C4+C5-B4`, `=SUM(...)`) | MISSING | Required-but-unbuilt | Evidenced; not built |
| AR ledger (747 cols) | same → `العملاء` (`=D4+J4+...`, per-customer blocks) | AR balances/entries | REAL (partial) | KEEP | Core finance; period mapping UNVERIFIED |
| Revenue / costs / expenses | same → `الايرادات`, `التكاليف`, `المصروفات` | MISSING | Required-but-unbuilt | Evidenced; not built |
| Fixed/variable assets | same → `الاصول الثابته`, `الاصول المتغيره` | MISSING | Required-but-unbuilt | Evidenced; not built |
| Payroll (lightweight) | sales workbooks → `الرئيسية` (term "رواتب" present) | MISSING | Deferred (discovery-gated) | Answers.txt: salary records/payments only; depth unconfirmed |
| Purchasing | `حسابات خاصه.xlsx` → `مصاريفى` (term "مشتريات") | MISSING | Deferred (discovery-gated) | Answers.txt: progressive; depth unconfirmed |
| Budgeting | Not in V2 §2B (Answers.txt: out of scope) | — | REMOVE (from scope) | Not evidenced; explicitly out of scope |

### C. Safeguards vs everyday workflows

**Safeguards (internal, keep):** auth/sessions, RBAC, audit (write), posting gate (OFF), branch/territory scoping, reason codes, immutable invoice history, Decimal money, protected-file hashes.

**Everyday workflows (user-facing):** invoice desk, inventory movements, transfers, returns, AR balances, collections, visits, targets entry, marketing spend entry, print, CSV export.

### D. Recommended smallest Arabic nav (desktop + mobile)

Top-level (RTL): الرئيسية | الفواتير | المخزون | الذمم | المبيعات | التسويق | الإدارة (owner/finance only).

Mobile bottom nav: max 5 items (Home, Invoices, Inventory, AR, More drawer). All else in "المزيد".

Hidden from nav (empty PROTO): routing, UOM, credit, analytics, telegram, purchases, payroll, cash, expenses, P&L, private accounts, reference, import, alerts, settings.

### E. Excel capabilities not yet preserved

- HQ rollups (`الرئيسية`) — branch totals recompute not imported (P4).
- Cross-workbook consolidation (`اجمالى الحسابات`) — blocked on missing Mansoura workbook.
- Sell-through (`رصيد الارصدة المباعة`) — formula stored, no import/reconciliation yet.
- AR 747-col period mapping — not imported.
- BS/P&L/cash/expenses/assets detail — not built.
- Payroll net formula (`E = B-C-D`) — not built (discovery-gated).
- External links (15) — not resolved at import.

### F. Uncertain (unverified) items

- Exact Excel sheet/cell refs for batch/expiry/returns/transfers/targets columns (column-level scan not done).
- Whether `حسابات خاصه` monthly sheets are production data or personal.
- UOM necessity (UQ-6), credit terms (UQ-9).
- Targets quantity- vs value-based in Excel (assumed quantity).
- Whether marketing spend exists in Excel beyond doctor list (Sheet1).

No code, DB or workbook modified in this inspection.