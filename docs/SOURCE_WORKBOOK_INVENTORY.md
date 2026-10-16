# SOURCE_WORKBOOK_INVENTORY.md

**Generated:** 2026-10-12  
**Source:** Mechanical inventory from `docs/inventory*.json/md` and `docs/SOURCE_HASHES.txt`

## Overview
7 Arabic workbooks, 361 sheets total. All files read-only. Baseline hashes in `SOURCE_HASHES.txt`.

## 1. الميزانية العمومية 2026.xlsx
- **Size:** 90,021 bytes  
- **SHA-256:** `d4a64fb777ceaa0e4f1398cdf057e3548e1771baac36daa930cc93623f48b884`  
- **Sheets:** 10 | Defined names: 0 | External links: **0**

| # | Sheet | State | Rows×Cols | Non-empty | Formulas | Merged | Validations |
|---|---|---|---|---|---|---|---|
| 1 | الموازنه العامه | visible | 18×15 | 18 | 26 | 4 | 0 |
| 2 | الميزانيه | visible | 46×19 | 43 | 93 | 4 | 0 |
| 3 | النقديه | visible | 40×24 | 40 | 272 | 4 | 0 |
| 4 | العملاء | visible | 47×747 | 47 | 342 | 124 | 0 |
| 5 | الارباح والخسائر | visible | 21×10 | 18 | 45 | 0 | 0 |
| 6 | الايرادات | visible | 40×5 | 40 | 43 | 1 | 0 |
| 7 | التكاليف | visible | 40×5 | 40 | 44 | 1 | 0 |
| 8 | المصروفات | visible | 40×5 | 40 | 41 | 1 | 0 |
| 9 | الاصول الثابته | visible | 7×18 | 7 | 22 | 0 | 0 |
| 10 | الاصول المتغيره | visible | 55×22 | 55 | 74 | 0 | 0 |

**Notes:** Finance-heavy (Balance Sheet/P&L structure). See `summary_extract.md` for detailed headers/formulas.

## 2. حسابات خاصه.xlsx
- **Size:** 223,297 bytes  
- **SHA-256:** `37dac95c617ed6c69e2bd89eb944fd4681ff7d4a2945814ec9c8b7c985f19c37`  
- **Sheets:** 44 | Defined names: 0 | External links: **7** (cross-workbook references detected)

Key sheets: `اجمالى الحسابات` (aggregates across external workbooks via indexed references e.g. `'[1]كامل الكمية'!$N$44`, `'[2]كامل الكمية'`), `الحاج علاء`, `مهندس عماد`, `ح د غادة`, `الشركة الجديدة`, `مصاريفى`, `الشالية مارينادلتا`, plus many monthly `اجمالى الحسابات شهر *` / `مصاريفى شهر *`. Includes placeholder `Sheet1`.

**Citations:** `docs/summary_extract.md` (sections `اجمالى الحسابات` through `الشركة الجديدة`).

## 3. مبيعات 6 اكتوبر 2026.xlsx
- **Size:** 12,319,748 bytes  
- **SHA-256:** `abf2b8163d33cae49d1a86572c593041faf59a166322cf5c8cf9b3f67b64cb7f`  
- **Sheets:** 97 | Defined names: 0 | External links: **4**

Core: `الرئيسية` (HQ summary/rollups), `رصيد الارصدة المباعة` (sold balances ledger), `كامل الكمية` (full quantities), `تحت التصريف` (under disposal). Many per-warehouse/pharmacy sheets (e.g. `مخزن الزهراء اكتوبر`, `صيدليات د احمد يحى اكتوبر`, ..., `شركة الربيع لتجارة الادوية`).

## 4. مبيعات الدقهليه 2026.xlsx
- **Size:** 9,222,783 bytes  
- **SHA-256:** `497f382926f18d5688346c2cf2b4d74fd9f2def379f143550385ca04d16277ca`  
- **Sheets:** 59 | Defined names: 0 | External links: **4**

Includes `الرئيسية`, `المرتبات` (payroll), `رصيد الارصدة المباعة`, `المبيعات الشهرية` (monthly sales), `كامل الكمية`, plus extensive per-location sheets and `عهدة الشرقية`/`عهدة الشرقية 2`. Placeholders: `Sheet2`, `ورقة1 (102)`.

## 5. مبيعات الشرقية 2026.xlsx
- **Size:** 2,710,910 bytes  
- **SHA-256:** `06a0fbf918215b1aefed4735085ceceeedcc487256aa2dd5e4e2fad4aa8b735d`  
- **Sheets:** 19 | Defined names: 0 | External links: **0**

Includes `الرئيسية`, `المرتبات`, `رصيد الارصدة المباعة`, `كامل الكمية`, regional sheets, `عهدة الشرقية`/`عهدة الشرقية 2`, placeholders `Sheet2`, `ورقة1 (102)`.

## 6. مبيعات الغربية  2026.xlsx
- **Size:** 8,424,314 bytes  
- **SHA-256:** `57a14aaa84a401025d7e605a2c24a5ade4452dce49f1da021668a6886ea2945c`  
- **Sheets:** 53 | Defined names: 0 | External links: **0**

Includes `الرئيسية`, `المرتبات`, `رصيد الارصدة المباعة`, `المبيعات الشهرية`, `كامل الكمية`, many per-warehouse/pharmacy sheets, placeholders `Sheet2`, `ورقة1 (102)`.

## 7. مبيعات الفيوم 2026.xlsx
- **Size:** 10,492,091 bytes  
- **SHA-256:** `9824a300452c85030cbe17fa14964bcef11ecddf40bad962aff29055b5f94b08`  
- **Sheets:** 79 | Defined names: 0 | External links: **0**

Includes `الرئيسية`, `كامل الكمية`, `تحت التصريف`, many regional/customer sheets, extensive placeholder chain `ورقة1 (81)–(102)`, `اخر ورقة`, `Sheet1`.

## Totals
- **Workbooks:** 7  
- **Sheets:** 361 (visible)  
- **Duplicate sheet names:** 86 (see `ENTITY_DUPLICATE_REPORT.md`)  
- **Placeholder/unnamed sheets:** 53 (see `ENTITY_DUPLICATE_REPORT.md`)  
- **External links total:** 15 (7+4+4) — **all in sales/private accounts workbooks**; Balance Sheet workbook has 0.  
- **Defined names:** 0 across all workbooks

## References
- `docs/SOURCE_HASHES.txt` (baseline, immutable)
- `docs/inventory_raw.md`, `docs/inventory.json`, `docs/analysis.json`
- `docs/summary_extract.md` (citations for headers/formulas)
