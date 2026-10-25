# EXCEL_TO_SYSTEM_MAPPING.md

**Generated:** 2026-10-12  
**Purpose:** Detailed Excel sheet/column/formula → System mapping with exact citations. **Separate from MODULE_MAP.md**.

## Mapping Rules
- Every business mapping cites sheet + location from `summary_extract.md` or structural inventory.
- Do not merge with MODULE_MAP. Keep detailed mappings per module area.
- Branch-scoped sheets mapped by `(Workbook + Sheet)` to avoid collision from duplicate names.
- Placeholders excluded unless confirmed.

## A. Sales → C.Sales
| Excel (Workbook + Sheet) | Type | Observed Logic/Fields | System Target (Module C) | Citation |
|---|---|---|---|---|
| `مبيعات 6 أكتوبر 2026.xlsx::الرئيسية` | Rollup (HQ) | Cross-sheet refs to per-warehouse sheets: `='مخزن الزهراء اكتوبر'!K1`, `!K2`, `!O14`, `!M14`, months `N17..Y17` (Jan..Dec) | Sales.BranchRollup (branch-scoped) | `summary_extract.md` ~10-86 |
| `مبيعات الدقهليه 2026.xlsx::الرئيسية` | Rollup | Same pattern | Sales.BranchRollup (branch-scoped) | ~398-474 |
| `مبيعات الشرقية 2026.xlsx::الرئيسية` | Rollup | Same | Sales.BranchRollup | ~786-862 |
| `مبيعات الغربية  2026.xlsx::الرئيسية` | Rollup | Same | Sales.BranchRollup | ~1020-1096 |
| `مبيعات الفيوم 2026.xlsx::الرئيسية` | Rollup | Same | Sales.BranchRollup | ~1254-1330 |
| `*::رصيد الارصدة المباعة` (all 5 sales) | Ledger | Sold balances (customer/agent, dates, qty/price, net). 1100–1267 formulas | Sales.SoldBalances (branch-scoped) | ~87-163, 552-628, 940-1019, 1174-1253 |
| `*::كامل الكمية` (all 5) | Price/Item list | `E = C*D` (opening quantity × price) in the verified 6 October layout; cumulative/catalog fields need per-sheet mapping. Net-price discount formula belongs to transaction sheets, not this citation. | Sales.PriceList / Inventory.Items (branch context) | ~164-240, 629-705, 1174-1253, 1331-1407 |
| `*::تحت التصريف` (6 أكتوبر, الفيوم) | Stock view | Large row sets (3751–4455 non-empty), per-line qty/price formulas | Inventory.StockView_UnderDisposal (branch-scoped) | ~318-397, 1408-1487 |
| Per-warehouse/pharmacy sheets (many) | Source transactions | Large transaction sheets (3460–5520 rows); net `E=C*(1-D)` (D is fractional discount), total `F=B*E`; feeds `الرئيسية`. Application comparison: 133 numeric rows in two complete named sheets, see INVOICE_SLICE_1.md. | Sales.Transactions (warehouse-scoped) | Structural: `inventory_raw.md` (per sheet counts) |

**Notes:** Same names across workbooks → map by `(workbook,sheet)`. Net price formula `E=C*(1-D)` must be preserved in logic (not guessed beyond formula). Discount bands observed ~0.28–0.30 — confirm applicability.

## B. Payroll → B.MasterData/Platform (lightweight) + related
| Excel | Fields/Logic | System Target | Citation |
|---|---|---|---|
| `مبيعات الدقهليه 2026.xlsx::المرتبات` | `الاسم`, basic/due/received, `دبى`, `Dopay`, `التارجيت`, **UNVERIFIED salary formula**: prior `E=B-C-D` claim conflicts with observed E=دوباى; preserve source values until real salary formulas are verified | Payroll.SalaryRecord (lightweight) | ~475-551 |
| `مبيعات الشرقية 2026.xlsx::المرتبات` | same | same | ~863-939 |
| `مبيعات الغربية  2026.xlsx::المرتبات` | same | same | ~1097-1173 |

**Gating:** Payroll depth (HR/attendance/leave/taxes) discovery-gated.

## C. Finance → E.Finance
| Excel (Workbook+Sheet) | Structure/Logic | System Target | Citation |
|---|---|---|---|
| `الميزانية العمومية 2026.xlsx::الموازنه العامه` | Aggregate BS (assets/liabilities/capital), 26 formulas | Finance.BalanceSheetSummary | ~1488-1530 |
| `الميزانية العمومية 2026.xlsx::الميزانيه` | Detailed BS: assets/liabs, capital/partners, net profit, distribution, market value, 93 formulas | Finance.BalanceSheetDetail | ~1531-1607 |
| `الميزانية العمومية 2026.xlsx::الارباح والخسائر` | P&L summary, 45 formulas | Finance.PnLSummary | ~1608-1669 |
| `الميزانية العمومية 2026.xlsx::الايرادات` | Revenue detail, 40×5, 43 formulas | Finance.RevenueDetail | ~1670-1730 |
| `الميزانية العمومية 2026.xlsx::التكاليف` | Costs detail, 40×5, 44 formulas | Finance.CostDetail | ~1730-1790 |
| `الميزانية العمومية 2026.xlsx::المصروفات` | Expenses detail, 40×5, 41 formulas | Finance.ExpenseDetail | ~1791-1848 |
| `الميزانية العمومية 2026.xlsx::النقديه` | Cash ledger (debit/credit/balances), 40×24, 272 formulas | Finance.CashLedger | ~1849-1925 |
| `الميزانية العمومية 2026.xlsx::العملاء` | AR ledger, **47×747 cols**, 342 formulas, 124 merged; includes مدين/دائن, agent, dates | Finance.ARLedger (wide columnar) | ~1926-2005 |
| `الميزانية العمومية 2026.xlsx::الاصول الثابته` | Fixed assets, 7×18, 22 formulas | Finance.FixedAssets | ~inventory_raw.md` (sheet 9) |
| `الميزانية العمومية 2026.xlsx::الاصول المتغيره` | Current assets, 55×22, 74 formulas | Finance.CurrentAssets | ~inventory_raw.md` (sheet 10) |

**Notes:** P&L + Balance Sheet reporting = item 30 (confirmed). **Budgeting discovery-gated**. AR ledger width (747 cols) suggests period columns — confirm period structure.

## D. Private Accounts → Private/Owner Accounts (same DB, protected boundary)
| Excel (Workbook+Sheet) | Structure/Logic | System Target | Citation |
|---|---|---|---|
| `حسابات خاصه.xlsx::اجمالى الحسابات` | Summary aggregating across external workbooks via indexed refs: `'[1]كامل الكمية'!$N$44`, `'[2]كامل الكمية'` (7 external links). 70×23, 76 formulas | PrivateAccounts.Summary (consolidated) | ~2006-2082 |
| `حسابات خاصه.xlsx::الحاج علاء` | Partner/person account, 97×8, 4 formulas | PrivateAccounts.PartnerAccount | ~2083-2103 |
| `حسابات خاصه.xlsx::مصاريفى` | Expenses, 272×109, 166 formulas | PrivateAccounts.Expenses | ~2104-2180 |
| `حسابات خاصه.xlsx::الشركة الجديدة` | New company/project, 876×26, 109 formulas | PrivateAccounts.ProjectAccount | ~2181-2222 |
| `حسابات خاصه.xlsx::الشالية مارينادلتا` | Property account, 60×24, 220 formulas, 1 validation | PrivateAccounts.PropertyAccount | `summary_extract.md` context (sheet present) |
| `حسابات خاصه.xlsx::اجمالى الحسابات شهر *` / `مصاريفى شهر *` (series) | Monthly summaries (various months/years noted) | PrivateAccounts.MonthlySummary | structural (`inventory_raw.md` sheets 9–44 series) |

**Critical:** Cross-workbook aggregation exists. Linked workbook paths/existence unknown at discovery time → `OPEN_QUESTIONS.md`. **Same DB, separate protected module with separate permissions/RLS/audit boundary** (no second DB).

## E. Cross-cutting Notes
- **Branch scoping:** Duplicate sheet names (86) → always key by `(workbook, sheet)`. Rollups are branch-scoped.
- **Placeholders:** 53 unnamed sheets (`ورقة1 (NN)`, `Sheet1/2`, `اخر ورقة`) — **not mapped** (treat as non-business). Confirm before import.
- **External links:** 15 total (7 in `حسابات خاصه.xlsx`, 4+4 in sales). System must not assume links resolve; capture link targets if present.
- **Formulas preserved as logic:** `E=C*(1-D)` (transaction sheets), `الرصيد = C-D` (with explicit known anomaly; see INVOICE_SLICE_1.md). Payroll `E=B-C-D` is UNVERIFIED, cross-sheet references, `SUMIFS(B:B,A:A,A2)`. No behavioral expansion beyond cited logic.
- **Discovery-gated:** Purchasing/Raw Materials/Manufacturing (BOM/MRP/PO depth), Budgeting, UOM necessity, deeper Payroll HR/attendance/leave/taxes.

## B-01. Customer creation and lifecycle (explicit owner-approved addition)

Source: PRD B-01; APP_FLOW §B1 (create active by default; inactive prevents new sales and preserves history); D34 responsibility/territory access; S1 immediate-recovery directive `pasted_content_2026-10-25_07-58-11-296_78e520.txt`.

The approved basic slice uses the existing `master_data.master_customer` fields: unique code, Arabic/optional English names, existing branch and territory, and server-owned `is_active`. Owner-only create/name-edit/deactivate/reactivate is persisted and atomically audited; readers retain assigned-territory restrictions. No branch-to-territory relationship is invented: the present territory schema has no branch foreign key. Inactive customers remain retrievable by the owner, disappear from new-sale choices, and retain invoices, AR and stock history. Contact fields, credit policy, reassignment and imports are not implemented by this slice. Arabic/English PWA and disposable verification evidence are linked from `PROGRESS_CHECKLIST.md`.

## B-01. Customer phone/address maintenance (explicit owner-approved extension)

Source: PRD B-01; APP_FLOW B1; DATABASE_SCHEMA master_customer row; owner S1 customer-contact directive `pasted_content_2026-10-25_11-33-10-789_c4c010.txt`. These are approved additional master fields, **not claimed extracted/populated from workbook cells**; the data dictionary supplies no additional phone format or multiplicity policy.

`0016_customer_contacts` adds nullable `contact_phone varchar(30)` and `address text` without changing existing customer records. Existing customer create/read/partial-update and the current bilingual PWA maintain them under owner-write/assigned-territory-read rules. Optional contact strings trim only outer whitespace, preserve local number text, accept NULL, and normalize blank to NULL; omitted fields stay unchanged. Phone sharing is permitted because no unique-contact requirement exists. Written addresses never reassign branch, territory or warehouse. Audit includes authenticated actor and full relevant old/new snapshot in the same locked transaction; unchanged values do not duplicate audit. Existing invoices/receivables/history, names and lifecycle are preserved. Downgrade refuses to discard populated contact fields. No multiple-phone model, email/VAT/credit rules, imports or accounting changes are introduced. Current evidence is linked from PROGRESS_CHECKLIST.

## References
- `docs/summary_extract.md` (all citations above)
- `docs/inventory_raw.md`, `docs/inventory.json`
- `docs/ENTITY_DUPLICATE_REPORT.md`, `docs/CURRENT_WORKFLOWS.md`
- Specs: `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC.md`, `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (authoritative V2)
