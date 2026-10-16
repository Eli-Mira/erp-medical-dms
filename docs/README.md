# MEDICAL COMPANY SYSTEM - Excel Discovery Handoff

**Generated:** 2026-10-12  
**Source Root:** `C:\Desktop\Huge system`  
**Status:** Phase 0 Discovery Complete

## Purpose
This directory contains the Excel discovery artifacts produced to enable replacing the 7 Arabic Excel workbooks without guessing. All findings are mechanical (structural) or explicitly cited from extracted evidence; ambiguities are logged in `OPEN_QUESTIONS.md`.

## Source of Truth
- `C:\Desktop\Huge system\MEDICAL_COMPANY_SYSTEM_MASTER_SPEC.md` (V1) - Keep
- `C:\Desktop\Huge system\MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (V2) - **Authoritative**, keep both

## Discovery Documents (Index)

| Document | Purpose |
|---|---|
| [`SOURCE_WORKBOOK_INVENTORY.md`](SOURCE_WORKBOOK_INVENTORY.md) | Complete inventory of all 7 workbooks (361 sheets), hashes, sizes, structure |
| [`EXCEL_FEATURE_CATALOG.md`](EXCEL_FEATURE_CATALOG.md) | Catalog of Excel features found (formulas, merges, validations, external links) with citations |
| [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) | Key entities/fields extracted from `summary_extract.md` with sheet+cell citations |
| [`ENTITY_DUPLICATE_REPORT.md`](ENTITY_DUPLICATE_REPORT.md) | 86 cross-workbook sheet-name duplicates + 53 placeholder/unnamed sheets |
| [`CURRENT_WORKFLOWS.md`](CURRENT_WORKFLOWS.md) | Inferred current workflows from formulas/structure (Sales rollups, Payroll, Balance Sheet/P&L, Private Accounts) with citations |
| [`EXCEL_TO_SYSTEM_MAPPING.md`](EXCEL_TO_SYSTEM_MAPPING.md) | **Detailed** Excel sheet/column/formula → System mapping (separate from MODULE_MAP) |
| [`MODULE_MAP.md`](MODULE_MAP.md) | **High-level** modules, relationships, build order A→H (standalone; do not merge with EXCEL_TO_SYSTEM_MAPPING) |
| [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) | Ambiguities requiring clarification; no guessing rule enforced |
| [`MIGRATION_RECONCILIATION_PLAN.md`](MIGRATION_RECONCILIATION_PLAN.md) | Migration approach, reconciliation checks, gating items |
| [`README.md`](README.md) | This index/handoff document |

## Evidence Artifacts (Mechanical)
- [`SOURCE_HASHES.txt`](SOURCE_HASHES.txt) - SHA-256 baseline of all sources (immutable)
- [`inventory.json`](inventory.json) - Full structural inventory (7.55 MB)
- [`analysis.json`](analysis.json) - Duplicate/placeholder analysis
- [`inventory_raw.md`](inventory_raw.md) - Human-readable structural inventory
- [`summary_extract.md`](summary_extract.md) - Targeted extraction with exact sheet+cell citations

## Key Findings (Summary)
- **Workbooks:** 7 | **Sheets:** 361
- **Duplicates:** 86 cross-workbook sheet-name duplicates
- **Placeholders:** 53 (`ورقة1 (NN)`, `Sheet1/2`, `اخر ورقة`)
- **External links:** Confirmed in `حسابات خاصه.xlsx` (7), `مبيعات 6 اكتوبر 2026.xlsx` (4), `مبيعات الدقهليه 2026.xlsx` (4) — cross-workbook references observed (e.g. `'[1]كامل الكمية'!$N$44` style in `اجمالى الحسابات`)
- **Critical fix applied:** `tools/inventory_excel.py` guards `ws.merged_cells` (ReadOnlyWorksheet) and uses `read_only=False, keep_links=True` to capture merged cells, validations, and external link definitions. 0 ERR entries in regenerated inventory.

## Build Order (A→H)
`A Platform → B Master Data → C Sales → D Inventory → E Finance → F Marketing → G Purchasing → H Executive Analytics/Telegram`

**Notes:** Payroll lightweight (salary records/payments only) unless depth justified. Purchasing/Raw Materials/Manufacturing and Budgeting are discovery-gated. Private/Owner Accounts = same PostgreSQL DB with separate protected module/security boundary (separate permissions/RLS/audit). No second DB.

## Handoff Instructions
1. Read V2 spec (`MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`) as authoritative; keep V1.
2. Review `MODULE_MAP.md` for high-level structure; consult `EXCEL_TO_SYSTEM_MAPPING.md` for detailed Excel→system mappings with citations.
3. Resolve items in `OPEN_QUESTIONS.md` before implementation (do not guess).
4. Use evidence artifacts (`summary_extract.md`, `inventory*.json/md`) for any citation checks.

**No known blockers remain. Any new ambiguity goes into `OPEN_QUESTIONS.md` and must not be guessed.**
