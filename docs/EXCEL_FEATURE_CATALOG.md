# EXCEL_FEATURE_CATALOG.md

**Generated:** 2026-10-12  
**Evidence:** `docs/summary_extract.md`, `docs/inventory_raw.md`, `docs/inventory.json`

## Purpose
Catalog Excel features present (not just structure): formulas, merges, validations, external links, cross-workbook references, large column sets. All with citations.

## External Links (Cross-Workbook)
Detected mechanically (inventory with `keep_links=True`):
- `حسابات خاصه.xlsx`: **7** external links (indexed references like `'[1]كامل الكمية'!$N$44`, `'[2]كامل الكمية'` observed in `اجمالى الحسابات` — see `summary_extract.md` lines ~2006-2083)
- `مبيعات 6 اكتوبر 2026.xlsx`: **4**
- `مبيعات الدقهليه 2026.xlsx`: **4**
- Others: 0

**Open question:** existence/path of linked workbooks at runtime (if moved/deleted). Logged in `OPEN_QUESTIONS.md`.

## Merged Cells
Common in headers/layout: e.g. `الموازنه العامه` (4), `الميزانيه` (4), `النقديه` (4), `العملاء` (124 merged). See per-sheet in `inventory_raw.md`.

## Data Validations
- `حسابات خاصه.xlsx` → `الشالية مارينادلتا`: **1 validation** (mechanical). Others 0 in inventory; Excel may have dropdowns dependent on named ranges (none detected). Needs confirmation if business-critical.

## Formula Density (Notable)
- Per-warehouse sheets are very large (many rows × 36 cols) with thousands of formulas per sheet (e.g. `مخزن الزهراء اكتوبر` ~6315 formulas over 3916 non-empty rows) — indicative of per-row calculations and cross-sheet references in source.
- `رصيد الارصدة المباعة` sheets carry 1100–1267 formulas across ~60–74 non-empty rows (dense header/total area).
- `الرئيسية` sheets aggregate from other sheets (see rollups below).

## Key Business Features (from `summary_extract.md`)

### Sales Rollups (`الرئيسية`) — per sales workbook
- Per-warehouse/customer lines pull values from corresponding per-warehouse sheet (e.g. `='مخزن الزهراء اكتوبر'!K1`, `='مخزن الزهراء اكتوبر'!K2`, `!O14`, `!M14`, month columns `N17..Y17` mapped to Jan..Dec).  
  **Citations:** `summary_extract.md` lines ~10-86 (6 أكتوبر), ~398-474 (الدقهليه), ~786-862 (الشرقية), ~1020-1096 (الغربية), ~1254-1330 (الفيوم).

### Sold Balances (`رصيد الارصدة المباعة`)
- Structure includes customer/agent, dates, quantities/prices, net totals. Formulas present; header set varies slightly by branch workbook.  
  **Citations:** `summary_extract.md` ~87-163, ~552-628, ~940-1019, ~1174-1253.

### Stock Lists (`كامل الكمية` / `تحت التصريف`)
- `كامل الكمية`: item codes/descriptions, quantities/prices, net price `E = C*(1-D)` (discount logic), totals `SUM(E5:E...)`, cumulative `SUMIFS(B:B,A:A,A2)` patterns observed.  
  **Citations:** `summary_extract.md` ~164-240, ~629-705, ~1174-1253 (الغربية), ~1331-1407 (الفيوم).
- `تحت التصريف`: per-row quantities/prices with formulas; large row counts (3751–4455 non-empty).  
  **Citations:** `summary_extract.md` ~318-397, ~1408-1487.

### Payroll (`المرتبات`)
Present in: `مبيعات الدقهليه 2026.xlsx` (~54x19), `مبيعات الشرقية 2026.xlsx` (~46x19), `مبيعات الغربية  2026.xlsx` (~45x19).
- Fields: `الاسم` (name), basic/due/received, `دبى`, `Dopay`, `التارجيت`, net `E = B-C-D`.  
  **Citations:** `summary_extract.md` ~475-551, ~863-939, ~1097-1173.

### Balance Sheet / P&L (`الميزانية العمومية 2026.xlsx`)
- `الموازنه العامه`: aggregate structure (assets/liabilities/capital) — formulas 26.  
  **Cite:** ~1488-1530.
- `الميزانيه`: detailed balance sheet (assets/liabilities, capital/partners, net profit, distribution, market value) — formulas 93.  
  **Cite:** ~1531-1607.
- `الارباح والخسائر`: P&L summary — 45 formulas.  
  **Cite:** ~1608-1669.
- `الايرادات`/`التكاليف`/`المصروفات`: detail sheets (40×5 each), ~41–44 formulas.  
  **Cite:** ~1670-1848.
- `النقديه`: cash ledger (40×24), 272 formulas.  
  **Cite:** ~1849-1925.
- `العملاء`: customer ledger (47×747 columns) — **very wide** (747 cols), 342 formulas, 124 merged; includes مدين/دائن, agent, dates.  
  **Cite:** ~1926-2005.
- `الاصول الثابته`/`الاصول المتغيره`: fixed/current assets.

### Private Accounts (`حسابات خاصه.xlsx`)
- `اجمالى الحسابات`: summary aggregating across external workbooks (indexed refs). Formulas 76, 70×23.  
  **Cite:** ~2006-2082.
- `الحاج علاء`: 97×8, 4 formulas.  
  **Cite:** ~2083-2103.
- `مصاريفى`: large (272×109), 166 formulas.  
  **Cite:** ~2104-2180.
- `الشركة الجديدة`: (876×26), 109 formulas.  
  **Cite:** ~2181-2222 (approx in summary_extract.md).
- Many monthly tabs (`اجمالى الحسابات شهر *`, `مصاريفى شهر *`) with smaller structures.

## References
- `docs/summary_extract.md` (exact citations above)
- `docs/inventory_raw.md`, `docs/inventory.json`
- `docs/analysis.json` (duplicates/placeholders)
