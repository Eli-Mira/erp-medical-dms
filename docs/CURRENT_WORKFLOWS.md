# CURRENT_WORKFLOWS.md

**Generated:** 2026-10-12  
**Evidence:** `docs/summary_extract.md` with exact citations

> Workflows inferred mechanically from formulas/structure. No process steps invented beyond what formulas imply.

## 1. Sales Rollup Workflow (HQ Summary)
**Where:** `الرئيسية` sheets in each sales workbook  
**Citations:** ~10-86 (6 أكتوبر), ~398-474 (الدقهليه), ~786-862 (الشرقية), ~1020-1096 (الغربية), ~1254-1330 (الفيوم)

- **Inputs:** Per-warehouse/pharmacy sheets (same workbook) provide values via cross-sheet references (e.g. `='مخزن الزهراء اكتوبر'!K1`, `!K2`, `!O14`, `!M14`, monthly `N17..Y17` → Jan..Dec).
- **Process:** `الرئيسية` aggregates per-warehouse lines into branch-level totals by month.
- **Outputs:** Branch HQ summary (totals by warehouse/customer and by month).
- **Notes:** Same-named `الرئيسية` exists in 5 workbooks (branch-scoped). Mapping must preserve branch context.

## 2. Sold Balances Workflow (`رصيد الارصدة المباعة`)
**Citations:** ~87-163, 552-628, 940-1019, 1174-1253  
- **Purpose:** Tracks sold balances (customer/agent, dates, quantities/prices, net). Dense formula area suggests computed totals.
- **Inputs:** Transaction lines per branch workbook.
- **Outputs:** Sold balances ledger per branch.

## 3. Stock/Item Lists Workflow (`كامل الكمية` / `تحت التصريف`)
**`كامل الكمية`:** ~164-240, 629-705, 1174-1253, 1331-1407  
- Computes **net price** `E = C*(1-D)` (discount), row totals `SUM(E5:E...)`, **cumulative by item** `SUMIFS(B:B,A:A,A2)`. Discount observed ~0.28–0.30 in context.
- Represents full quantities/price list per branch workbook.

**`تحت التصريف`:** ~318-397, 1408-1487  
- Per-line quantities/prices with formulas; large volumes (3751–4455 non-empty). Suggests under-disposal/allocated stock view.

## 4. Payroll Workflow (`المرتبات`)
**Present in:** الدقهليه/الشرقية/الغربية  
**Citations:** ~475-551, 863-939, 1097-1173  
- **Fields:** `الاسم`, basic/due/received, `دبى`, `Dopay`, `التارجيت`, **net `E = B-C-D`**.
- **Flow:** Input employee components → compute net due/received.  
- **Scope:** Salary records/payments only (lightweight). Deeper HR/attendance/leave/taxes discovery-gated per instructions.

## 5. Finance Workflow (Balance Sheet/P&L)
**Workbook:** `الميزانية العمومية 2026.xlsx`  
**Citations:** ~1488–2005

- **`النقديه`** (cash ledger, 272 formulas): Debit/credit entries → balances.  
- **`العملاء`** (customer ledger, 747 cols, 342 formulas): Wide columnar layout (dates/periods). Debit/credit, agent.  
- **`الايرادات`/`التكاليف`/`المصروفات`** → feed P&L (`الارباح والخسائر`).  
- **`الميزانيه`/`الموازنه العامه`** → Balance Sheet aggregation (assets/liabilities, capital/partners, net profit, distribution, market value).  
- **`الاصول الثابته`/`الاصول المتغيره`** → asset tracking.

**P&L + Balance Sheet reporting** is item 30; Budgeting is discovery-gated.

## 6. Private Accounts Workflow (`حسابات خاصه.xlsx`)
**Citations:** ~2006–2222  
- **`اجمالى الحسابات`** aggregates across external workbooks via **indexed cross-workbook references** (`'[1]كامل الكمية'!$N$44`, `'[2]كامل الكمية'`, etc.). This is a cross-workbook consolidation (summary).
- **Partner/person accounts:** `الحاج علاء`, others.
- **Expenses/projects:** `مصاريفى`, `الشركة الجديدة`, `الشالية مارينادلتا`.
- **Periodic:** Monthly `اجمالى الحسابات شهر *` / `مصاريفى شهر *` summaries.

**Key point:** Aggregation depends on external linked workbooks. Existence/path of those linked files must be confirmed (logged in `OPEN_QUESTIONS.md`).

## Cross-cutting Notes
- **Branch-scoping:** Many entities duplicated by branch workbook (same sheet names). System must treat as branch-scoped.
- **Cross-workbook links:** Present in `حسابات خاصه.xlsx` (7) and two sales workbooks (4+4) — consolidation dependency.
- **Placeholders:** 53 unnamed sheets exist; treat as non-business unless confirmed.
- **Formulas as source of truth for logic:** Rollups (cross-sheet refs), net price `E=C*(1-D)`, net payroll `E=B-C-D`, `الرصيد = C-D` observed. No behavioral rules invented.
