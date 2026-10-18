# OPEN_QUESTIONS.md

**Generated:** 2026-10-12 · **Updated:** 2026-10-16 (all items resolved with evidence)
**Status:** ✅ ALL RESOLVED — no blockers remain. Evidence-based resolutions below; no guessing.

## Purpose
Explicitly log ambiguities found during Phase 0. Each was resolved against workbook evidence (not assumption). New ambiguities must go here.

## Resolution Summary

| # | Question | Status | Resolution |
|---|---|---|---|
| 1 | External links / cross-workbook refs | ✅ RESOLVED | 15 links mapped; 14 target the 6 sibling workbooks (present, stale `E:\` path), 1 targets a missing Mansoura workbook. Consolidation recomputed at import from local copies. |
| 2 | Read-only → full load impact | ✅ RESOLVED | Fix accepted; all 7 SHA-256 hashes re-verified 2026-10-16 — identical to `SOURCE_HASHES.txt`. No source modification. |
| 3 | Placeholders / unnamed sheets (53) | ✅ RESOLVED | Sampled: `ورقة1 (NN)`/`Sheet2` series = duplicate copies of transaction sheets (identical to each other 40/40 rows; differ from named sheets 3–4/40) → exclude as duplicates, flag as possible historical data. `Sheet1` in `حسابات خاصه` = doctor list (business master data → include). `Sheet1` in `مبيعات الفيوم` = warehouse withdrawal totals (business summary → include). |
| 4 | Cross-workbook sheet name duplicates (86) | ✅ RESOLVED | Confirmed branch-scoped: 5 sales workbooks = 5 branches (6 أكتوبر، الدقهليه، الشرقية، الغربية، الفيوم), same sheet names, branch-scoped rollups. Key by `(workbook, sheet)`. |
| 5a | Payroll depth | ✅ RESOLVED | `Answers.txt` 2026-10-11: **lightweight** — salary records/payments only. No HR/attendance/leave/taxes unless real workflow proves need. |
| 5b | Purchasing/Raw Materials/Manufacturing | ✅ RESOLVED | `Answers.txt` 2026-10-11: **progressive** — import real existing data (suppliers/purchases/stock movements); no full MRP/BOM/PO/GRN until discovery proves use. |
| 5c | Budgeting | ✅ RESOLVED | Not among V2 confirmed features; `Answers.txt`: modules unused in Excel are not core migration scope. **Out of scope** unless Eli says otherwise. (Spec item 30 = P&L + Balance Sheet reporting only.) |
| 5d | UOM necessity | ✅ RESOLVED | `Answers.txt` 2026-10-11: box/pack/unit conversions **only if real operations use them**. Keep optional/lightweight in master data. |
| 6a | AR ledger width (`العملاء`, 747 cols) | ✅ RESOLVED | Structure decoded: ~48 customer blocks × 6 columns (`الرصيد`, `مدين`, `دائن`, `البيان`, `المندوب`, `التاريخ`), transactions down rows. Running balance: opening `D=E−F`, then `D=prev+E−F`. Row 1 total = 2,200,000. Model = normalized AR entries (customer, date, rep, description, debit, credit, running_balance). |
| 6b | Balance Sheet/P&L completeness | ✅ RESOLVED | Inventory complete (361 sheets, 0 ERR). Finance workbook = 10 sheets, all mapped. No additional supporting sheets found. |
| 7 | Private accounts boundary | ✅ RESOLVED | `Answers.txt` 2026-10-11: **same PostgreSQL DB, separate protected module/security boundary** — separate permissions, restricted queries, audit logs, ideally separate schema/tables. No second DB. |
| 8 | Tooling/process (read-only fix) | ✅ RESOLVED | Documented fix; no source modifications (hashes verified). |

## Evidence Detail

### 1. External Links (resolved 2026-10-16)
Method: parsed `xl/externalLinks/*.xml` + rels from each `.xlsx` (zip, no full load).
- `حسابات خاصه.xlsx` (7 links) → targets:
  - `E:\حسابات جديده 2025\الملفات المهمة\مبيعات الدقهليه 2026.xlsx` (present in folder)
  - `...\مبيعات الغربية  2026.xlsx` (present)
  - `...\مبيعات الشرقية 2026.xlsx` (present)
  - `...\مبيعات 6 اكتوبر 2026.xlsx` (present)
  - `...\مبيعات الفيوم 2026.xlsx` (present)
  - `...\الميزانية العمومية 2026.xlsx` (present)
  - `\\Laptop\حسابات جديده 2025\مهم جدا\حسابات الشركة\متابعة مبيعات المنصورة الجديده.xlsx` (**NOT provided**)
- `مبيعات 6 اكتوبر 2026.xlsx` (4 links) → الدقهليه، الشرقية، الفيوم، الغربية (all present)
- `مبيعات الدقهليه 2026.xlsx` (4 links) → 6 اكتوبر، الغربية، الشرقية، الفيوم (all present)
- **Conclusion:** linked set = the 6 sibling workbooks (by basename) + 1 missing Mansoura workbook. The `E:\` path is stale (files now in `C:\Users\emadg\CrossDevice\Desktop\Huge system`). System must recompute `اجمالى الحسابات` consolidation from local copies at import; Mansoura link stays broken → flag, never block other modules.

### 2. Source Integrity (resolved 2026-10-16)
`sha256sum` of all 7 workbooks re-run 2026-10-16 → **all identical** to `SOURCE_HASHES.txt` baseline. No write operations occurred during discovery.

### 3. Placeholders (resolved 2026-10-16)
Method: openpyxl sampling (12×12) + row-hash comparison (40 rows × 36 cols).
- `ورقة1 (81…88)` (6 اكتوبر), `Sheet2`/`ورقة1 (102)` (الدقهليه/الشرقية/الغربية): headers `items, quantity, price, الخصم, Net price, total, المبيعات بسعر الجمهور, اجمالى المسحوبات` — same structure as named transaction sheets. `ورقة1 (81)` vs `(85)` vs `(88)`: **40/40 identical** → duplicate copies. vs named sheets: 3–4/40 → different data (likely archived/historical snapshots).
- `Sheet1` in `حسابات خاصه.xlsx`: `الاجمالى, الوصف, المنطقة, التخصص` + doctor names (e.g. `د ابراهيم محمد احمد على اطفال حلوان`, الجيزة, اطفال) → **doctor/KOL master data** (supports V2 feature 16).
- `Sheet1` in `مبيعات الفيوم 2026.xlsx`: `اجمالى مسحوبات المخازن من اول السنه` + warehouse names → **business summary data**.
- **Treatment:** exclude duplicate transaction copies from MVP import (flag for Eli as possible historical data); include doctor list + warehouse summary as business data.

### 6a. AR Ledger (resolved 2026-10-16)
Method: openpyxl read of `الميزانية العمومية 2026.xlsx::العملاء` rows 1–6 × 747 cols.
- Row 1: `العملاء` + total `2,200,000`.
- Row 2: `المديونيه` / `المسئول` labels, then customer names every 6 columns (D, J, P, V, AB, …) — mix of pharmacies (`ص …`), warehouses (`مخزن …`), companies (`شركة …`).
- Per-customer block headers (row 3): `الرصيد` (balance), `مدين` (debit), `دائن` (credit), `البيان` (description), `المندوب` (rep), `التاريخ` (date).
- Running balance: `D4 = E4−F4` (opening = debit − credit); `D5 = D4+E5−F5` (rolling). Rep column mirrors balance.
- **Model:** normalized `ar_entry(customer_id, entry_date, rep_id, description, debit, credit, running_balance)` — the wide layout is a pivot, not a time series.

## Resolution Policy (retained)
- **No guessing:** any answer not evident from evidence requires user confirmation.
- **Log all:** new ambiguities must go here.
- **Blockers:** none. All Phase 0 gates cleared; ready for Phase 1 planning documents.

## References
- Evidence: `docs/summary_extract.md`, `docs/inventory_raw.md`, `docs/inventory.json`, `docs/analysis.json`, `docs/SOURCE_HASHES.txt`
- Tools: `tools/inventory_excel.py` (fixed), `tools/analyze_inventory.py`, `tools/extract_summary.py`
- Specs: `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC.md`, `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (authoritative)
- Decisions: `C:\Users\emadg\CrossDevice\Desktop\Answers.txt` (2026-10-11), `docs/DECISION_LOG.md`

## 2026-10-18 — Private accounts security boundary (`حسابات خاصه`)

- **Source:** `حسابات خاصه.xlsx` (owner's accounts notebook, one of the 7 source workbooks).
- **Question:** Should private accounts live inside the same application/database security boundary as the
  distribution company books, or in a separate domain/user set (owner-only)?
- **Why it matters:** V1 §6/§10 flags owner/private-account separation as open; the current prototype shows
  the module view-only and owner-only (`web/app.js` `PROTON.privateaccounts`, `data-roles="owner"`).
- **Status:** RESOLVED 2026-10-18 — answered by `C:/Desktop/Answers.txt` (2026-10-16, Eli): **same PostgreSQL database, separate protected module/security boundary** — separate permissions, restricted queries, audit logs, ideally separate schema/tables; no second database. Recorded as **D40** in `docs/DECISION_LOG.md`. No design finalized before this was answered, as required above.
- Related note: audit/analytics read endpoints and the private-accounts model are both untouched by this decision.
