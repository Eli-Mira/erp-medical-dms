# MIGRATION_RECONCILIATION_PLAN.md

**Generated:** 2026-10-12  
**Evidence:** Structural inventory + extracted rules + specs

## Goals
- Migrate from 7 Excel workbooks (361 sheets) to system without guessing.
- Reconcile aggregates (rollups, cross-workbook consolidations).
- Enforce boundaries (private accounts), branch-scoping, and discovery gates.

## Migration Phases
| Phase | Scope | Verification |
|---|---|---|
| **P0 - Discovery (Complete)** | Inventory, hashes, duplicates/placeholders, external links, rule extraction with citations | Baseline `SOURCE_HASHES.txt` immutable; 0 ERR in inventory. |
| **P1 - Confirm Gates** | Resolve `OPEN_QUESTIONS.md` (linked files, placeholders, discovery-gated items: Payroll depth, Purchasing/Raw Materials/BOM/MRP/PO, Budgeting, UOM) | All gate questions answered or explicitly deferred with rationale. |
| **P2 - Master Data (B)** | Normalize customers/suppliers/items/warehouses/branches/employees (minimal), establish branch keys to disambiguate duplicate sheet names | Uniqueness by (branch_key, entity_id); no collisions. |
| **P3 - Platform (A)** | Auth/RBAC, posting states (Draft→Posted→Voided), reason codes, audit timeline, import validation, global search, integration settings (Telegram first) | Role matrix covers private accounts boundary. |
| **P4 - Sales/Inventory (C/D)** | Import branch-scoped transactions/price lists; preserve `E=C*(1-D)` logic; reconcile `الرئيسية` rollups to per-warehouse sums | Row-count + formula-equivalent totals match sampled branches. |
| **P5 - Finance (E)** | Cash/AR/AP/GL, BS/P&L, assets. Validate AR (747 cols) period mapping; P&L+BS reporting per item 30 | BS/P&L reconciliation to Excel samples. |
| **P6 - Private Accounts (Protected)** | Import with separate permissions/RLS/audit boundary (same DB). Reconcile `اجمالى الحسابات` consolidation only if linked workbooks resolvable; else flag | Boundary tests (owner-only access), audit entries present. |
| **P7 - Purchasing (G, gated)** | Only if depth confirmed (PO/GRN/BOM/MRP). Otherwise defer. | Scope matches confirmed depth. |
| **P8 - Analytics/Telegram (H)** | Cross-module dashboards + Telegram only; respect private accounts boundary | Read-only views, boundary enforced. |

## Reconciliation Checks (Minimum)

### Structural
- **Sheet coverage:** All business sheets mapped or explicitly excluded with reason (placeholders). 
- **Branch scoping:** Every branch-scoped entity keyed by `(workbook_branch, sheet)`. No global name collisions.
- **Placeholders:** 53 unnamed sheets must be confirmed (data vs template). Exclude until confirmed.

### Aggregates
- **HQ Rollups (`الرئيسية`):** For each sales workbook, recompute branch totals from per-warehouse source sheets; compare to Excel rollup for sampled rows. Tolerance 0 (exact for formula-equivalent).
- **Sold Balances:** Row counts + key totals vs source per branch.
- **Net price:** `E = C*(1-D)` preserved; discount samples ~0.28–0.30 validated.
- **Payroll net:** `E = B-C-D` preserved.
- **Cross-workbook consolidation (`اجمالى الحسابات`):** Only possible if all linked workbooks (`[n]...`) exist at import time. If missing → block import with clear error + log in OPEN_QUESTIONS.

### Finance
- **BS/P&L:** Reconcile totals between `الميزانيه`/`الموازنه العامه` and detail sheets (`الايرادات`/`التكاليف`/`المصروفات`, assets/cash/AR). 
- **Cash/AR:** Balance checks (debit-credit). AR is 747-col wide → validate period mapping (dates/columns).
- **Posting states:** Enforce Draft→Posted→Voided; audit all state changes.

### Security/Boundary
- **Private accounts:** Same DB, **separate permissions/RLS/audit boundary**. Owner-only by default. No cross-tenant leakage.
- **Audit timeline:** All sensitive operations logged.
- **External links:** 15 detected (7+4+4). Import must not silently ignore broken links; treat as reconciliation dependency for private accounts consolidation.

## Tools (Existing)
- `tools/inventory_excel.py` (fixed: guards `merged_cells`, `read_only=False, keep_links=True`) — structural capture
- `tools/analyze_inventory.py` — duplicates/placeholders
- `tools/extract_summary.py` — targeted extraction with citations
- Evidence: `docs/inventory*.json/md`, `docs/summary_extract.md`, `docs/SOURCE_HASHES.txt`

## Gating Criteria (Go/No-Go for gated areas)
- **Payroll depth:** Only implement beyond salary records/payments if confirmed required (HR/attendance/leave/taxes). Otherwise lightweight.
- **Purchasing/Raw Materials/Manufacturing (BOM/MRP/PO):** Confirm scope (PO/GRN/BOM/MRP). Depth gated.
- **Budgeting:** Gated (separately from P&L+BS reporting).
- **UOM:** Confirm necessity (box/pack/unit only if used).

## References
- Specs: `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC.md`, `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (authoritative V2)
- Discovery: `docs/*` (all 10 docs + evidence)
- Answers: `C:\Desktop\Answers.txt` (module additions, split rules, decisions)
