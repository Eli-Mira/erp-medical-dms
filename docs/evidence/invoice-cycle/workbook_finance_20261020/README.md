# Finance workbook — traced calculations (sanitized) — 2026-10-20

Source: `الميزانية العمومية 2026.xlsx` (read-only input, SHA-256 frozen).
No amounts, partner names, or customer names are reproduced here; the
unsanitized cell-level extract stays in gitignored `private/workbook_probe/`.

## Sheets and their role

| Sheet | Role | Structure evidenced |
|---|---|---|
| `الموازنه العامه` | Presentation rollup | Cells are `=الميزانيه!…` and `=الاصول الثابته!…` references only; no independent data |
| `الميزانيه` | Balance sheet | `الأصول` vs `الخصوم`, plus opening equity lines (shares, owner current account, profit distribution, marketing value) |
| `النقديه` | Cash ledger | Running `الرصيد = C(n)+C(n-1)-B(n)`; separate cost / expense / fixed-asset / cash-discount columns feeding totals |
| `العملاء` | Receivables | One wide block per rep/warehouse; row 40+ feeds cash, revenue and current-asset sheets |
| `الارباح والخسائر` | P&L | Revenue − costs − expenses for a period, by sales-responsible |
| `الايرادات` / `التكاليف` / `المصروفات` | Detail ledgers | Columns: `التاريخ`, `البيان`, `المندوب`, `القيمه`, running `الاجمالى` |
| `الاصول الثابته` | Fixed-asset register | Category columns (establishment, revaluation, office equipment, other) + `نسبة الاهلاك` + `الاهلاك` + `الصافى` |
| `الاصول المتغيره` | Current assets | Opening inventory, wholesale stock, raw materials; per-product valuation `=العدد*السعر*التكلفة` |
| `حسابات خاصه` (separate workbook) | Owner-private ledger | Monthly `البداية` carried from the prior month; `المتبقى` chains |

## Calculations actually present (formula patterns)

1. **Cash running balance** — `الرصيد = C4+C5-B4` (debit/credit columns, balance carried down).
2. **Revenue / cost / expense roll-up** — each detail sheet carries `الاجمالى = previous + current value`.
3. **P&L composition** — revenue minus cost minus expense, plus **opening and closing inventory**
   (`بضاعة أول/آخر المدة`, `مواد خام أول/آخر المدة`); cost of sales uses the consumed-ratio cells
   (`=E6-H6`, `=E7*G7`).
4. **Inventory valuation at cost** — `=العدد*السعر*التكلفة` where the third factor is a per-product
   cost ratio (0.25 / 0.28 observed) rather than a purchased unit cost.
5. **Fixed-asset depreciation** — `=التكلفة*نسبة_الاهلاك/4` with a per-category rate (0.1 observed
   on one category, 0 on the others), i.e. a quarterly straight-line charge and a `الصافى` column.
6. **Balance sheet** — assets (fixed + current) = liabilities (suppliers/current) + capital
   (shares) + partner/owner current accounts + retained profit; `القيمة التسويقية` is a separate
   derived line.
7. **Private ledger** — each month opens with `البداية` equal to the previous month's closing;
   `المتبقى = مدفوع − مستحق` in the debt-tracking sheets.

## What the application currently lacks (specific, not "finance in general")

| Workbook calculation | App status | Missing piece |
|---|---|---|
| Revenue/cost/expense ledger rows (date, description, rep, value) | absent | no tables/endpoints; invoices only cover sales revenue |
| Cash ledger with running debit/credit balance | absent | no cash/bank account entity or opening balance |
| P&L incl. opening/closing inventory | absent | no inventory snapshots; no expense data |
| Cost of sales / margin | **blocked** | sales movements store the *selling* price in `stock_movement.unit_cost` (`app/sales/service.py`), so no purchase cost basis exists |
| Fixed-asset register + depreciation | absent | no asset table; category rates only exist inside the workbook |
| Balance sheet | absent | no opening balances, capital, or partner current accounts |
| Private monthly rollover | partially | D40 ledger records entries; no month-opening carry-forward calculation |

## Policies the workbook does not settle (need owner decision, ranked)

1. **Cost basis** — the workbook values stock with a per-product cost ratio, not purchase invoices.
   Confirm: import the cost ratios as product cost, or introduce purchase costing later?
   *Recommendation: import the ratios as a starting `standard_cost` per product, flagged "workbook
   estimate", until purchase costing exists.*
2. **Depreciation rate** — only one category shows 0.1; the others are 0.
   *Recommendation: keep the observed per-category rates as configurable values, no new policy.*
3. **Opening balances** — the balance sheet is dated 2025-01-01 while sales workbooks cover 2026.
   *Recommendation: record a single opening-balance date and import values once, then derive.*
4. **Private ledger sign convention** — `البداية` chains plus `المتبقى = مدفوع − مستحق`, but the
   D40 module stores generic debit/credit. *Recommendation: keep debit = outflow, credit = inflow,
   and expose totals only until the owner confirms closing-balance semantics.*
