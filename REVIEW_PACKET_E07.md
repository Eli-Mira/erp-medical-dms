# REVIEW_PACKET_E07 — AR statements, aging, CSV exports

Commit under test: `6a9a139` (tree `e95cc6f9eccc2b46df695c957aa7d6a362120370`), branch `feature/lane-finance`.
Base: `2fed444`. No push, no tag, no deploy. `POSTING_ENABLED=false`.

## Touched files

| File | Change |
|---|---|
| `app/finance/statements.py` | new (62 lines) — opening balance + running-balance lines |
| `app/finance/aging.py` | new (69 lines) — due-date buckets |
| `app/finance/exports.py` | new (50 lines) — CSV rendering, BOM, formula-injection guard |
| `app/finance/router.py` | +141/−36 — new endpoints, `ar.balances`/`_visible_entries` extraction |
| `app/finance/ar.py` | +25 — `balances()` helper, opt-in `territory_id` |
| `app/finance/schemas.py` | +56 — `StatementOut`, `StatementLine`, `AgingOut`, `AgingCustomer`, `AgingTotals` |
| `app/finance/payment_router.py` | +48/−36 — `GET /collections/export`, shared `_visible_receipts` |
| `tests/conftest.py` | +3 — two module names appended to the financial admission set |
| `tests/test_overnight_ar_reports.py` | new (414 lines) |
| `tests/test_overnight_csv_exports.py` | new (233 lines) |

## Commands (approved contained runner, disposable `dms_cycle_test_*` DB)

```
python scripts/verify_invoice_cycle.py --stage focus-13 -- \
  tests/test_overnight_ar_reports.py tests/test_overnight_csv_exports.py \
  tests/test_ar_ledger.py tests/test_collections.py -p no:cacheprovider
```

## Raw results

| Run | Counts | Exit | DB | `unchanged` | Receipt (sha256) |
|---|---|---|---|---|---|
| RED `red-10` | 48 failed / 3 passed | 1 | `dms_cycle_test_05d7bbcd629445a2b38c918109bf1350` | true | `run.json` f17414da5372ee2bb6452a0156ae6d1ff9e9c9a0c545dc6cdda6d5ea8d0ece8f |
| GREEN `focus-13` | 87 passed / 0 failed | 0 | `dms_cycle_test_9fde4b714ca84771867fa8a21249c15f` | true | `run.json` 77c14604037dac212045f2833cee920a139c36e60c81c293ec78f004ab399642 |
| Full branch `full-11` | 1208 passed / 38 failed / 40 error / 56 skipped | 1 | `dms_cycle_test_a6bc9115055340a38dd6a51c5c0e9c0d` | true | this lane's modules: 0 failures |
| Full base `full-base-01` | 1160 passed / 35 failed / 40 error / 56 skipped | 1 | `dms_cycle_test_517f452e29294e4d959747c07d518152` | true | — |

`pytest.xml` sha256 for `focus-13`: `825dfe207488b975acc0bcf59170415c0d56ca8229be1f9e38d6cb6991e62994`.
All disposable DBs were removed by the runner.

## Risks / decisions a reviewer must rule on

1. **Aging rules are not owner-approved.** `BUYER_QUESTIONS.md` #14 ("Credit terms / due dates / aging rules") is unanswered. Buckets `current / d1_30 / d31_60 / d61_90 / over_90 / undated` are the standard convention, implemented as `due_date >= as_of`, overdue 1–30 / 31–60 / 61–90 / 91+, and `NULL due_date -> undated`.
2. **Aging is ledger-due-date based.** The posting flow never sets `ar_entry.due_date`, so posted invoices currently age into `undated`. Semantic gap, not a bug.
3. **Statement window:** `date_from` inclusive, `date_to` exclusive (matches `ar.list_entries`); opening balance is 0 when `date_from` is omitted.
4. **Zero money serialises as `"0"`** (`str(Decimal)`), consistent with the existing `/ar/balances`. Not padded to `"0.00"`.
5. **CSV formula-injection guard:** non-numeric text starting `= @ + -` (or tab/CR) is prefixed with `'`; real numbers stay numeric so negative balances are untouched.
6. **CSV now emits a UTF-8 BOM** and `content-type: text/csv; charset=utf-8` for Arabic Excel.
7. **AR scope stays branch-based** (existing semantics: `sales_manager`/`district_manager` by `platform.user_branch`). `territory_id` is an **opt-in filter** on balances/aging and their exports, not an automatic restriction.
8. **`medical_rep` keeps collections read** — `payment_router.READ_ROLES` already included it; preserved, not tightened.
9. **Route ordering:** `GET /collections/export` must stay declared before `GET /collections/{receipt_id}`, or Starlette captures `/export` as a UUID path param and returns 422.

## What a reviewer should try to break

1. Running balance vs an independent window-function SQL (`test_statement_matches_independent_window_sql`).
2. Aging bucket edges 30/31, 60/61, 90/91 and `NULL` due dates (`test_aging_bucket_boundaries`, `test_aging_matches_independent_case_sql`).
3. Scope: branch-scoped manager sees only their branch; out-of-scope customer returns 404, never 403/200 (`test_statement_out_of_scope_customer_404`, `test_aging_out_of_scope_customer_404`).
4. Denied roles (`warehouse_staff`, `medical_rep`, `admin`) get 403 on every export.
5. CSV: BOM present; `=HYPERLINK(...)` neutralised; `-50.00` stays numeric; CSV totals equal the JSON statement/aging totals.
6. `POSTING_ENABLED` guard and the conftest admission set still refuse a non-disposable DB.
7. Confirm no endpoint leaks a customer id outside the caller's branch (404 rather than existence reveal).
