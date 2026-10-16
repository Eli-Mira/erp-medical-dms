# DATA_DICTIONARY.md

**Generated:** 2026-10-12  
**Evidence:** `docs/summary_extract.md` with exact sheet+cell citations

> Note: Field names preserved as they appear in Arabic sheets where possible. Types are inferred from structure/formulas (not guessed beyond observation). Definitions are mechanical where cited.

## 1. Sales - `الرئيسية` (HQ Summary/Rollups)
**Workbooks:** All 5 sales workbooks (`6 أكتوبر`, `الدقهليه`, `الشرقية`, `الغربية`, `الفيوم`)  
**Citations:** `summary_extract.md` ~10-86, 398-474, 786-862, 1020-1096, 1254-1330

Key structure (representative):
- Rows: per warehouse/customer (branch-level rollup lines)
- Columns include: warehouse/customer identifier/name, quantity/value rollups pulled from corresponding per-warehouse sheet (e.g. `='[Warehouse]'!K1`, `!K2`, `!O14`, `!M14`, monthly totals `N17..Y17` mapped to **Jan..Dec**)
- Aggregates: totals by month/branch; `الرصيد = C-D` observed in related contexts (sold balances). Formulas are cross-sheet references to per-warehouse sheets.

## 2. Sales - `رصيد الارصدة المباعة` (Sold Balances)
**Citations:** ~87-163, 552-628, 940-1019, 1174-1253  
**Size:** ~64×97 up to ~74×101, 1100–1267 formulas

Fields (observed headers/structure): customer/agent, document/date fields, item/quantity/price, debit/credit/net totals. Dense formula area (totals).

## 3. Sales - `كامل الكمية` / `تحت التصريف`
**`كامل الكمية`:** ~164-240, 629-705, 1174-1253, 1331-1407  
- Item code/description, quantity, price, discount (D), **net price `E = C*(1-D)`**, totals `SUM(E5:E...)`, cumulative `SUMIFS(B:B,A:A,A2)`. Discount ~0.28–0.30 range observed in context.

**`تحت التصريف`:** ~318-397, 1408-1487  
- Large row sets (3751–4455 non-empty), quantities/prices, formulas per row (transaction/stock lines).

## 4. Payroll - `المرتبات`
**Workbooks:** `الدقهليه`, `الشرقية`, `الغربية`  
**Citations:** ~475-551, 863-939, 1097-1173  
**Size:** ~45–54×19

Fields:
- `الاسم` (Name)
- Basic/due/received components
- `دبى` (Dubai)
- `Dopay`
- `التارجيت` (Target)
- **Net:** `E = B-C-D` (formula observed)

Scope: salary records/payments (lightweight by design).

## 5. Finance - Balance Sheet/P&L (`الميزانية العمومية 2026.xlsx`)
**Citations:** ~1488–2005

### `الموازنه العامه` (18×15, 26 formulas)
- Aggregate balance sheet structure (Assets/Liabilities/Capital).

### `الميزانيه` (46×19, 93 formulas)
- Detailed BS: Assets/Liabilities, Capital/Partners, Net Profit, Distribution, Market Value.

### `الارباح والخسائر` (21×10, 45 formulas)
- P&L summary.

### `الايرادات` / `التكاليف` / `المصروفات` (40×5 each, ~41–44 formulas)
- Revenue/Costs/Expenses detail.

### `النقديه` (40×24, 272 formulas)
- Cash ledger (debit/credit, balances).

### `العملاء` (47×747, 342 formulas, 124 merged)
- Customer ledger, **very wide (747 columns)**. Fields include مدين/دائن (Debit/Credit), Agent, Dates. High merge count (layout).

### `الاصول الثابته` / `الاصول المتغيره` (Fixed/Current Assets)
- Asset registers.

## 6. Private Accounts - `حسابات خاصه.xlsx`
**Citations:** ~2006–2222

### `اجمالى الحسابات` (70×23, 76 formulas)
- Summary rollup. Uses **cross-workbook indexed references**: e.g. `'[1]كامل الكمية'!$N$44`, `'[2]كامل الكمية'` (external links). Aggregates across linked workbooks.

### `الحاج علاء` (97×8, 4 formulas)
- Partner/person account.

### `مصاريفى` (272×109, 166 formulas)
- Expenses (wide).

### `الشركة الجديدة` (876×26, 109 formulas)
- New company/project accounts.

### Monthly tabs
- `اجمالى الحسابات شهر *` and `مصاريفى شهر *` series (various months 1–12, years noted) — smaller structures, periodic summaries.

## Notes
- Types/semantics preserved as-is (Arabic business terms).  
- Cross-workbook references are present in `اجمالى الحسابات` (external links confirmed).  
- Placeholder sheets (`Sheet1/2`, `ورقة1 (NN)`, `اخر ورقة`) excluded from dictionary as non-business content (see `ENTITY_DUPLICATE_REPORT.md`).
- Wide columns (e.g. `العملاء` 747 cols) likely represent time-period or columnar layouts; exact column headers require deeper sheet inspection only where necessary (citations point to summary sections). No guessing applied.
