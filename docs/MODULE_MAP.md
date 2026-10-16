# MODULE_MAP.md

**Generated:** 2026-10-12  
**Purpose:** High-level modules, relationships, boundaries. **Standalone** — do not merge with `EXCEL_TO_SYSTEM_MAPPING.md`.

## Build Order (A→H)
`A Platform → B Master Data → C Sales → D Inventory → E Finance → F Marketing → G Purchasing → H Executive Analytics/Telegram`

## Module Definitions

### A. Platform (Foundation)
- **Scope:** AuthN/AuthZ, roles/permissions, audit timeline, system settings, tenant/config, posting status (Draft→Posted→Voided), reason codes, alerts, import validation, global search, integration settings (Telegram first, WhatsApp later), app config.
- **Notes:** Cross-cutting. Security model supports private/owner accounts boundary.

### B. Master Data
- **Scope:** Customers, suppliers/vendors, employees (minimal for payroll), items/products (drugs/medical items implied), warehouses/branches, UOM (box/pack/unit only if used), agents, partners, chart of accounts (minimal COA to support finance), territories/regions.
- **Notes:** Normalize branch context (due to duplicate sheet names across branch workbooks). UOM necessity to be confirmed (discovery-gated).

### C. Sales
- **Scope:** Sales transactions by branch/warehouse, HQ rollups (`الرئيسية`), sold balances (`رصيد الارصدة المباعة`), price lists (`كامل الكمية`), under-disposal view (`تحت التصريف`), per-warehouse sheets (mapped by branch context). Credit management integration.
- **Notes:** 5 sales workbooks represent branch contexts (6 أكتوبر, الدقهليه, الشرقية, الغربية, الفيوم). Same-named sheets are branch-scoped. Net price logic `E=C*(1-D)` observed.

### D. Inventory
- **Scope:** Stock by warehouse, movements, allocations, `كامل الكمية`/`تحت التصريف` alignment, recons. 
- **Notes:** Inventory logic present in sales workbooks (per-warehouse sheets). Manufacturing/Raw Materials discovery-gated (activity confirmed; depth gated).

### E. Finance
- **Scope:** Cash (`النقديه`), AR (`العملاء` - wide 747 cols), AP, GL, Chart of Accounts, Balance Sheet (`الميزانيه`/`الموازنه العامه`), P&L (`الارباح والخسائر` + `الايرادات`/`التكاليف`/`المصروفات`), Fixed/Current Assets (`الاصول الثابته`/`الاصول المتغيره`), distributions.
- **Notes:** P&L + Balance Sheet reporting = item 30. **Budgeting discovery-gated**. AR ledger is very wide (columnar periods) — needs confirmation of period granularity.

### F. Marketing
- **Scope:** As per spec/V2; lightweight unless specified. (Not central in extracted evidence; defer to specs.)

### G. Purchasing
- **Scope:** PO/GRN, suppliers, payments. **Purchasing/Raw Materials/Manufacturing BOM/MRP/PO depth discovery-gated** (activity confirmed).

### H. Executive Analytics/Telegram
- **Scope:** Cross-module executive dashboards/analytics + **Telegram integration only** (WhatsApp later). Consolidates sales by branch, finance summaries, private accounts summaries where permitted.
- **Notes:** Consolidation must respect private accounts boundary.

## Cross-cutting: Private/Owner Accounts
- **Location:** Same PostgreSQL database as main system.
- **Boundary:** Separate protected module with **separate permissions/RLS/audit boundary**. 
- **Source evidence:** `حسابات خاصه.xlsx` aggregates via cross-workbook references (`'[1]كامل الكمية'!$N$44`, etc.) — consolidation depends on linked workbooks.
- **Owner-only visibility** strictly enforced.

## Relationships (High-Level)
- **Sales (C)** feeds **Inventory (D)** (stock movements) and **Finance (E)** (AR/invoices).
- **Purchasing (G)** feeds **Inventory (D)** and **Finance (E)** (AP).
- **Master Data (B)** shared across all.
- **Private Accounts** (protected) may reference allowed aggregates but isolated by permissions/RLS.
- **H (Analytics/Telegram)** reads cross-module (with boundary enforcement).

## References
- `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC.md` (V1), `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (V2, authoritative)
- `docs/CURRENT_WORKFLOWS.md`, `docs/EXCEL_TO_SYSTEM_MAPPING.md`
- `docs/SOURCE_WORKBOOK_INVENTORY.md`, `docs/EXCEL_FEATURE_CATALOG.md`
