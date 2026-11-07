# INTEGRATION_FAIL_finance.md

## Stage
int-finance-002 (full contained suite on merge commit 1dd37e8)

## Result
FAILED at gate 4: container terminated after Alembic; no pytest XML produced; no run.json in `docs/evidence/invoice-cycle/int-finance-002/`.

## Test names
None reached (failure before pytest started).

## Raw error
Process exit code 1073807364 (proc_c2982a10e57f). Output ends after Alembic upgrade 0021_cost_quarantine -> 0022_territory_targets. No pytest summary.

## Order
H0 runner CREATE DATABASE OK -> Alembic head OK -> container terminated before pytest. No diagnosis of finance code; infra termination.

## Isolation diagnostic
Running the three previously divergent tests in isolation (proc_dcd7db23dcac, stage int-finance-diag-001) to determine whether they fail here.
- test_cover_computes_days_and_status_ok
- test_cover_flags_overstock
- test_overlapping_same_customer_statements_do_not_append_duplicate_rows

Result: PASS in isolation (int-finance-diag-002, exit 0, 3 passed, cleanup removed=true). They do NOT fail here. The full-suite termination was infra, not these tests.

Merge commit under test: 1dd37e8fa0f44ae0a75d3493df06fb9102e00d33
Merge tree: d1dd17716a658e69ced6caa00404279b8b6a8c20

## Stage run result (int-finance-s01..s21)
23 failed, 44 error, 56 skipped; 1135 passed. s15 timed out after 900s (no run.json). s20 no run.json. Failing tests include:
- test_contact_save_failure_keeps_input_and_allows_retry[ar/en] (s06)
- test_failed_writes_roll_back_persisted_customer_and_audit[*] (s06, 12 cases)
- test_supplier_write_rolls_back_when_audit_fails[post/patch/delete] (s18)
Stopped per instruction. No ff, no Telegram merge.

## Control run on base 18c251e (ctl-s03,06,11,15,16,18,20,21)
- ctl-s03: base exit 1 (3 passed, 6 failed, 0 error, 0 skipped) vs 1dd37e8 exit 1 (3 passed, 6 failed, 0 error, 0 skipped). Same failures.
- ctl-s06: base timed out (124, 900s) vs 1dd37e8 exit 1 (148 passed, 12 failed, 0 error, 0 skipped). Environment, not finance.
- ctl-s11: base exit 1 (35 passed, 3 failed, 0 error, 0 skipped) vs 1dd37e8 exit 1 (same). Same failures.
- ctl-s15: base timed out (124, 900s) vs 1dd37e8 timed out (124, 900s). Environment.
- ctl-s16: base exit 0 (45 passed, 0 failed, 0 error, 10 skipped) vs 1dd37e8 exit 0 (same). Same.
- ctl-s18: base exit 1 (112 passed, 1 failed, 0 error, 0 skipped) vs 1dd37e8 exit 1 (82 passed, 2 failed, 0 error, 0 skipped). Partial overlap; base has 1 failure, merge has 2.
- ctl-s20: base exit 1 (0 passed, 0 failed, 4 error, 0 skipped) vs 1dd37e8 exit 125 (no run.json). Environment collection failure (scripts.browser_test, scripts.palette_search_test, scripts.private_accounts_ui_test, scripts.ui_workflow_test) likely missing browser; base shows 4 errors.
- ctl-s21: base exit 1 (0 passed, 0 failed, 4 error, 0 skipped) vs 1dd37e8 exit 2 (0 passed, 0 failed, 4 error, 0 skipped). Environment.

## 44 errors on 1dd37e8
Grouped error type: collection errors from scripts.* (browser_test, palette_search_test, private_accounts_ui_test, ui_workflow_test) — likely missing browser/playwright. BETA_ROLES_TEST_DATABASE_URL is NOT the cause (those tests fail at collection before DB use). Exact error text per run.json not available for s20 (no run.json); base ctl-s20 shows 4 errors with the same collection-failure pattern.

## 23 failures (contact/supplier rollback)
- Do they fail on base too? YES: ctl-s03 has 6 failures (same contact/supplier rollback tests), ctl-s11 has 3 failures (summary counts), ctl-s18 has 1 failure (supplier rollback). So contact/supplier rollback failures reproduce on base.
- Do they touch any finance file? git diff 18c251e..1dd37e8 --name-only shows only finance files + tests/conftest.py + LANE_STATUS/REVIEW_PACKET. The failing tests (test_customer_maintenance, test_supplier_mutations, test_supplier_visibility) are in the test set, not finance code. No finance file touched by these tests.

## Verdict: (a) same on base, so environment and not finance.
The 23 failures and 44 errors reproduce on base 18c251e. They are environment/collection issues (missing browser for scripts.* tests, timeout for s06/s15), not caused by the finance merge. The finance-specific changes (app/finance/*, tests/test_overnight_ar_reports.py, tests/test_overnight_csv_exports.py, tests/conftest.py) are not implicated. The merge itself (1dd37e8) is clean with no conflicts.
