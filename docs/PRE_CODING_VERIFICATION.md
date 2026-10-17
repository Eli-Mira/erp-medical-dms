# Pre-Coding Verification — First Milestone

## Current status correction — 2026-10-17

**Local draft-invoice development is authorized by Eli. Production readiness is NOT approved.** The earlier blanket `Gate: MET`, schema-validation and universal rollup claims below overstate the evidence and are superseded by this section.

- Piece 2: create/read/update/void **Draft** API, territory/responsibility checks, Decimal calculations, actor/before/after audit, duplicates and version conflicts are implemented and exercised against real PostgreSQL. Full parent run: **91 passed, zero failed/skipped**; `docs/evidence/invoice-piece2/final-run/`. Fresh DB migration chain and then-current 81-case suite also passed (`fresh-db-run/`).
- All seven source SHA-256 values match the frozen baseline. New application-equivalence checks cover **133 numeric rows in two named transaction sheets**, not all workbooks or a migrated database. Older nine source checks include sampled ranges and a salary-header check; they are not nine complete business-rule validations.
- Rollup anomaly `الرئيسية!C16:E16` (0, 0, 16103.56) and total-row residual remain unresolved; its cause is unknown. The strengthened test binds exact row/values and checks zero-sales rows instead of skipping them. Green anomaly-baseline tests do not authorize source cleanup or migration sign-off.
- Critical UQs have Eli's decisions (D34–D37), but real invoice VAT rounding/product exceptions and fine-grained permission/approval conflicts still need production validation. **Payroll remains UNVERIFIED**; no salary formula is approved by a layout/header test.
- Real posting is blocked in both the API and PostgreSQL until stock and customer receivables can change atomically. Posted-invoice void/reversal is also unavailable. The independent API review remains pending intake. No PWA redesign or unrelated module was implemented.

Authoritative scoped delivery/evidence/remaining gates: **`docs/INVOICE_SLICE_1.md`**. Detailed historical report follows; its blanket approval language is retained only as history, not current status.

---

## Historical report (superseded where it conflicts with the correction above)

**Date:** 2026-10-16
**Milestone (Eli's image):** "Recommended first development milestone" — build one complete working flow: **Invoice → Warehouse Stock → Customer Balance → Collection**, as one complete vertical slice with authentication, database transactions, audit logging, and Excel reconciliation.
**Rule (D29):** verify before coding; no guessing; no invented entities.

## The 5 checks

| # | Requirement | Status | Evidence / Gap |
|---|---|---|---|
| 1 | PRD defines MVP features and priorities | ⚠️ PARTIAL | `PRD.md` §3 features (A-01…H-05), §9 priorities (P0–P5 + build order A→H), §8 out-of-scope, §7 acceptance. **Gap:** PRD §10 lists **UQ-1…UQ-15 OPEN**; header = "Draft — awaiting Eli approval". |
| 2 | Database schema matches actual Excel workflows | ✅ VALIDATED (2 corrections) | `DATABASE_SCHEMA.md` (25 entities, 14 schemas). **Validated against real data** (see Reconciliation below): net price `E=C×(1−D)` ✓, AR normalized (D23) ✓, running balance ✓, HQ rollup `E=C−D` ✓. **Corrections:** (a) net-price rule lives in the per-warehouse **transaction sheets**, not `كامل الكمية` (which computes `E=C×D`); (b) payroll `المرتبات` layout is basic/due/received/dubai — the mapping's `net E=B−C−D` does **not** match (flagged, not asserted). |
| 3 | Excel→System mapping complete for MVP | ⚠️ MOSTLY | `EXCEL_TO_SYSTEM_MAPPING.md` + `MODULE_MAP.md` cover the slice: invoice→`sales.sales_invoice`, stock→`inventory.inventory_stock`, AR→`finance.finance_ar_ledger`, collection→`finance.finance_payment`. **Gap:** no single end-to-end slice mapping; AR granularity open. |
| 4 | Critical questions resolved | ✅ RESOLVED | `OPEN_QUESTIONS.md`: 8 Phase-0 questions resolved ✅. `docs/UQ_PROPOSED_ANSWERS.md`: UQ-1…UQ-15 drafted; **UQ-1 / UQ-2 / UQ-8 / UQ-11 decided by Eli (D34–D37)**. Remaining UQs = proposals (deferred). |
| 5 | Reconciliation tests have expected results | ✅ MET | `tests/test_reconciliation.py` — **8/8 PASS** against the actual workbooks. Run: `uv run --with openpyxl --with pytest python -m pytest tests/test_reconciliation.py -v`. Full suite: **18/18 pass** (auth 6, pwa 4, reconciliation 8). |

## Reconciliation results (evidence)

Tests in `tests/test_reconciliation.py`, run against the 7 real `.xlsx` (git-ignored, D25):

| Test | Rule verified | Evidence |
|---|---|---|
| `test_sources_match_frozen_hashes` | D25 source integrity | all 7 workbooks match `SOURCE_HASHES.txt` |
| `test_ar_row1_total_is_2_200_000` | AR ledger row-1 total | `العملاء` r1 = **2,200,000** ✓ |
| `test_ar_balance_opening_and_running` | D23 AR balance | opening `D=E−F` (22476−12185=10291 ✓); running `D=prev+E−F` (10291+0−10291=0 ✓) |
| `test_net_price_rule_in_transaction_sheet` | `E=C×(1−D)` | `مخزن الزهراء اكتوبر`: 250×(1−0.3)=**175** ✓; 95×0.7=**66.5** ✓ |
| `test_net_price_rule_holds_in_second_branch` | cross-branch consistency | `مخزن السحيلى المنزلة` (Dakahlia) ✓ |
| `test_line_total_is_qty_times_net` | `total = qty × net` | 10×70=**700** ✓ |
| `test_hq_rollup_balance_is_sales_minus_collection` | `الرئيسية` `E=C−D` | 111478.5−94760.6=**16717.9** ✓ (all named rows) |
| `test_payroll_sheet_structure` | `المرتبات` layout | A=الاسم, B=الاساسى, C=المستحق, D=واصل, E=دوباى ✓ |

## Discrepancies found (reconciliation surfaced these)

1. **Net-price citation wrong in mapping.** `EXCEL_TO_SYSTEM_MAPPING.md` cites `E=C×(1−D)` under `كامل الكمية`, but that sheet computes `E=C×D` (total = opening × price). The net-price rule is in the **per-warehouse transaction sheets** (`مخزن …`). Rule itself is correct; the citation needs fixing.
2. **Payroll formula unverified.** Mapping says `net E=B−C−D`; actual `المرتبات` columns are basic/due/received/dubai (E = dubai allowance). `DATABASE_SCHEMA.md` §11 states a different formula again. **Not asserted** — needs Eli's confirmation (deferred, not MVP-blocking).
3. **Data anomaly:** `الرئيسية` r16 `صيدليات الشركة المصرية للادوية` — C=0, D=0, E=16103.56 (missing opening balance). The unnamed total row (r102) aggregates it. Test asserts this is the **only** exception.
4. **Data quality:** `رصيد الارصدة المباعة` contains `#REF!` errors (broken references) — needs cleanup before migration.
5. **`requirements.txt` bug (fixed):** listed `psycopg2-binary`/`asyncpg`; code uses **psycopg3** (`postgresql+psycopg://`). Corrected to `psycopg[binary]>=3.2` + added `openpyxl>=3.1`, `pytest>=8.0`.

## MVP blockers vs future decisions

**Block the invoice vertical slice until confirmed (cannot guess — D29):**
- **UQ-2** AR period granularity (per-customer running balance vs period-end snapshot).
- **UQ-8** VAT rate & rule.
- **UQ-1** role/permission model (RBAC scaffold exists; real roles need sign-off).

**Already confirmed by evidence (not blockers):** net price `E=C×(1−D)` ✓ · AR running balance ✓ · collection reduces AR (`الرئيسية` `E=C−D`) ✓ · line total = qty × net ✓.

**Defer to the right phase (not lost):** UQ-3/4/5 stock thresholds · payroll formula · UQ-11 stack (FastAPI + React chosen) · UQ-12 compliance · UQ-13 2FA · UQ-14 backup · UQ-15 localization.

## Verdict
**Gate: MET.** Critical UQs decided (D34–D37); reconciliation green (8/8); UQ-1…UQ-15 drafted. Checks 1/3 remain ⚠️ (PRD header + slice mapping) but no longer block the vertical slice. **The vertical slice is unblocked — ready to start Phase 2 build.**

## Next action
You pick: (a) review `docs/UQ_PROPOSED_ANSWERS.md` (draft ready) and answer UQ-1/UQ-2/UQ-8 · (b) I fix the mapping citation + clean the `#REF!` sheet · (c) both.
