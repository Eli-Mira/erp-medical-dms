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
