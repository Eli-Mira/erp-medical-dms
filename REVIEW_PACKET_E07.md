# REVIEW_PACKET_E07 — AR statements, aging, CSV exports

Commit under test: `99de4f4` (tree `e79776bb209e5c28be9c7156febba8770d8220e1`), branch `feature/lane-finance`.
Base: `2fed444`. No push, no tag, no deploy. `POSTING_ENABLED=false`.

## Touched files

| File | Change |
|---|---|
| `app/finance/statements.py` | new (62 lines) — opening balance + running-balance lines |
| `app/finance/aging.py` | new (74 lines) — due-date buckets, `entry_date <= as_of`, label/note |
| `app/finance/exports.py` | new (50 lines) — CSV rendering, BOM, formula-injection guard |
| `app/finance/router.py` | +141/−36 — new endpoints, `ar.balances`/`_visible_entries` extraction |
| `app/finance/ar.py` | +25 — `balances()` helper, opt-in `territory_id` |
| `app/finance/schemas.py` | +56 — `StatementOut`, `StatementLine`, `AgingOut`, `AgingCustomer`, `AgingTotals` |
| `app/finance/payment_router.py` | +48/−36 — `GET /collections/export`, shared `_visible_receipts` |
| `tests/conftest.py` | +3 — two module names appended to the financial admission set |
| `tests/test_overnight_ar_reports.py` | new (435 lines) |
| `tests/test_overnight_csv_exports.py` | new (303 lines) |

## Commands (approved contained runner, disposable `dms_cycle_test_*` DB)

```
python scripts/verify_invoice_cycle.py --stage focus-15 -- \
  tests/test_overnight_ar_reports.py tests/test_overnight_csv_exports.py \
  tests/test_ar_ledger.py tests/test_collections.py -p no:cacheprovider
```

## Raw results

| Run | Counts | Exit | DB | `unchanged` | Receipt (sha256) |
|---|---|---|---|---|---|
| RED `red-10` | 48 failed / 3 passed | 1 | `dms_cycle_test_05d7bbcd629445a2b38c918109bf1350` | true | `run.json` f17414da5372ee2bb6452a0156ae6d1ff9e9c9a0c545dc6cdda6d5ea8d0ece8f |
| GREEN `focus-15` | 92 passed / 0 failed | 0 | `dms_cycle_test_7ce050d902634d9384c2920a16806256` | true | `run.json` ff4bff576cff02eeb1e03a52f63df57ede3fb191b51566c45126c475f818f224 |
| Full branch `full-11` | 1208 passed / 38 failed / 40 error / 56 skipped | 1 | `dms_cycle_test_a6bc9115055340a38dd6a51c5c0e9c0d` | true | this lane's modules: 0 failures |
| Full base `full-base-01` | 1160 passed / 35 failed / 40 error / 56 skipped | 1 | `dms_cycle_test_517f452e29294e4d959747c07d518152` | true | — |
| Isolation `iso-inv1` | 1 passed / 0 failed | 0 | `dms_cycle_test_04ad1268ae5142dfa4dcd9b5a7701034` | true | `run.json` f49850154992347dd0f9cf309614607c235bd151bae53ce91e4b6fc014e42c74 |
| Isolation `iso-inv2` | 1 passed / 0 failed | 0 | `dms_cycle_test_0d3cd7d662ce4806881641d2c80dbf8b` | true | `run.json` c726f8919811104e19373dd4a1369afb64d99659edd8456c965cd8eb2fd776a5 |
| Isolation `iso-beta3` | 1 passed / 0 failed | 0 | `dms_cycle_test_f5377ee69e13455497ccfb2933b2c59a` | true | `run.json` c8fce0e4c610257d3b39bdf20019b09bb1e65dc065b5d2914c94da0db860f0f8 |

`pytest.xml` sha256 for `focus-15`: `e0efcc834654697ea2d3bc056a0a18207aa55bde5262ea9e3be786eeb53fc15c`.
All disposable DBs were removed by the runner.

## Risks / decisions a reviewer must rule on

1. **Aging rules are not owner-approved.** `BUYER_QUESTIONS.md` #14 ("Credit terms / due dates / aging rules") is unanswered. Buckets `current / d1_30 / d31_60 / d61_90 / over_90 / undated` are the standard convention, implemented as `due_date >= as_of`, overdue 1–30 / 31–60 / 61–90 / 91+, and `NULL due_date -> undated`. The payload carries `label: "ledger aging"` plus a `note` saying the rules are pending accountant approval; the CSV is named `ar_ledger_aging.csv`.
2. **Aging counts only entries dated on or before `as_of`** (`e.entry_date <= :as_of`). A future-dated entry with an old due date is excluded from both JSON and CSV.
3. **Aging is ledger-due-date based.** The posting flow never sets `ar_entry.due_date`, so posted invoices currently age into `undated`. Semantic gap, not a bug.
4. **Statement window:** `date_from` inclusive, `date_to` exclusive (matches `ar.list_entries`); opening balance is 0 when `date_from` is omitted.
5. **Zero money serialises as `"0"`** (`str(Decimal)`), consistent with the existing `/ar/balances`. Not padded to `"0.00"`.
6. **CSV formula-injection guard:** non-numeric text starting `= @ + -` (or tab/CR) is prefixed with `'`; real numbers stay numeric so negative balances are untouched.
7. **CSV now emits a UTF-8 BOM** and `content-type: text/csv; charset=utf-8` for Arabic Excel.
8. **AR scope stays branch-based** (existing semantics: `sales_manager`/`district_manager` by `platform.user_branch`). `territory_id` is an **opt-in filter** on balances/aging and their exports, not an automatic restriction.
9. **`medical_rep` keeps collections read** — `payment_router.READ_ROLES` already included it; preserved, not tightened. `/collections/export` returns 200 with only that rep's own receipts.
10. **Route ordering:** `GET /collections/export` must stay declared before `GET /collections/{receipt_id}`, or Starlette captures `/export` as a UUID path param and returns 422.

## What a reviewer should try to break

1. Running balance vs an independent window-function SQL (`test_statement_matches_independent_window_sql`).
2. Aging bucket edges 30/31, 60/61, 90/91, `NULL` due dates, and the `entry_date <= as_of` cut-off (`test_aging_excludes_entries_dated_after_as_of`, `test_aging_csv_excludes_entries_dated_after_as_of`, `test_aging_matches_independent_case_sql`).
3. Scope: branch-scoped manager sees only their branch; out-of-scope customer returns 404, never 403/200 (`test_statement_out_of_scope_customer_404`, `test_aging_out_of_scope_customer_404`).
4. `warehouse_staff`/`admin` get 403 on every export. `medical_rep` **is** in collections `READ_ROLES`, so `/collections/export` returns 200 containing only that rep's own receipts — `_receipt_scope` -> `_invoice` enforces `invoice.created_by == user.id` — and 403 on the AR exports. (Corrected: an earlier revision of this packet claimed a blanket 403 for `medical_rep`.)
5. CSV: BOM present; `=HYPERLINK(...)` neutralised; `-50.00` stays numeric; CSV totals equal the JSON statement/aging totals.
6. `POSTING_ENABLED` guard and the conftest admission set still refuse a non-disposable DB.
7. Confirm no endpoint leaks a customer id outside the caller's branch (404 rather than existence reveal).
8. Collections export policy: a rep sees only their own receipts in both `/collections` and `/collections/export` (`test_collections_csv_export_rep_cannot_see_other_reps_receipt`).
