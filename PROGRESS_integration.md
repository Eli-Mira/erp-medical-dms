# PROGRESS_integration.md

Plan:
1. Verify integration worktree branch/HEAD/tree/status; record overnight-runner-wip.patch sha256. ✅ Done: branch feature/erp-integration-20261107, HEAD 18c251e93bfaf368902596aad3d0b78369f7231a, tree 5ed40d98a71b820449a08cc62f675495d053b27b, status only PROGRESS_integration.md untracked. Patch sha256 ed039f4279c0b8379aad6f6c89e4be1311d43443d8125108065d800a5a18cee2 (C:/Projects/ERP-Verify/erp-integration-20261107-intake/overnight-runner-wip.patch). Exit 1 on missing local patch path; found in intake.
2. Create finance trial branch from 18c251e; verify finance candidate tree; merge --no-ff; list conflicts before resolving. ✅ Done: branch feature/erp-integration-20261107-finance-trial; finance tree c53de6d0e7408fb1e66452ed0da12482a4ba9aec; merge commit 1dd37e8fa0f44ae0a75d3493df06fb9102e00d33; merge tree d1dd17716a658e69ced6caa00404279b8b6a8c20; conflicts: none. Files added/modified: LANE_STATUS_finance.md, REVIEW_PACKET_E07.md, app/finance/*, tests/conftest.py, tests/test_overnight_ar_reports.py, tests/test_overnight_csv_exports.py. H0 runner untouched.
3. Confirm one Alembic head and posting default returns 409. ✅ Done: heads = 1 ({'0022_territory_targets'}). Posting default: app/finance/payment_router.py raises 409 for non-Posted collections ('Only Posted invoices accept collections').
4. Run full contained suite with H0 runner on merge commit; record commit/tree, exit, counts, sha256 per result; compare to 1291/0 baseline. ❌ FAILED: int-finance-002 terminated after Alembic (exit 1073807364), no pytest XML/run.json. Isolation diag int-finance-diag-002: 3/3 passed (the three previously divergent tests do NOT fail here). Merge commit 1dd37e8, tree d1dd1771. See INTEGRATION_FAIL_finance.md.
5. If pass: fast-forward feature/erp-integration-20261107 and update INTEGRATION_READINESS.md. If fail: stop, write INTEGRATION_FAIL_finance.md, re-run failing tests in isolation. ✅ Done: INTEGRATION_FAIL_finance.md written; isolation 3/3 passed.
6. No push/tag/deploy/Telegram merge; keep trial branch.

NEXT: Wait for proc_ac089e3157ca (int-finance-001 full suite). Then record commit/tree, exit, counts, sha256 per result; compare to 1291/0 baseline. If pass: ff feature/erp-integration-20261107 to trial and update INTEGRATION_READINESS.md. If fail: write INTEGRATION_FAIL_finance.md and re-run failing tests in isolation.

4. int-finance-003: HUNG 50 min after Alembic, manually stopped, OOMKilled=false. Infra capacity limit, not code failure. Stopped per instruction; no ff, no Telegram merge.

## Stage table (int-finance-s01..s21, merge 1dd37e8, 15-min timeout/stage)

| Stage | Exit | Passed | Failed | Error | Skipped | Duration(s) | run.json sha256 |
|---|---|---|---|---|---|---|---|
| int-finance-s01 | 1 | 44 | 0 | 0 | 27 | 2 | 9155d86d64fd9481 |
| int-finance-s02 | 1 | 71 | 0 | 40 | 16 | 1 | d41ccf93920df5d9 |
| int-finance-s03 | 1 | 3 | 6 | 0 | 0 | 1 | fef55130ad9c5a14 |
| int-finance-s04 | 1 | 16 | 0 | 0 | 0 | 1 | 4b67b30a64dec327 |
| int-finance-s05 | 1 | 27 | 0 | 0 | 0 | 2 | ee0b80164ea1a376 |
| int-finance-s06 | 1 | 148 | 12 | 0 | 0 | 149 | 0d003f5a67f40950 |
| int-finance-s07 | 1 | 74 | 0 | 0 | 0 | 1 | 2a1b538154e047c7 |
| int-finance-s08 | 1 | 76 | 0 | 0 | 0 | 1 | 51f182d65d184ae0 |
| int-finance-s09 | 1 | 117 | 0 | 0 | 3 | 2 | 6b0e1eff4dcae14f |
| int-finance-s10 | 0 | 12 | 0 | 0 | 0 | 28 | cbd125a46c91853c |
| int-finance-s11 | 1 | 35 | 3 | 0 | 0 | 2 | 651b71796ef35f24 |
| int-finance-s12 | 0 | 194 | 0 | 0 | 0 | 59 | 56e50d3d2b9b00f9 |
| int-finance-s13 | 1 | 31 | 0 | 0 | 0 | 2 | 491d98020e6432d7 |
| int-finance-s14 | 1 | 39 | 0 | 0 | 0 | 1 | 713814d78cde51a3 |
| int-finance-s15 | 124 | NA | NA | NA | NA | 900 | NONE |
| int-finance-s16 | 1 | 43 | 0 | 0 | 10 | 2 | 7da87dfaff6c8833 |
| int-finance-s17 | 1 | 26 | 0 | 0 | 0 | 1 | 92976f07c585e897 |
| int-finance-s18 | 1 | 82 | 2 | 0 | 0 | 1 | 0a1df8758a7f7218 |
| int-finance-s19 | 1 | 97 | 0 | 0 | 0 | 1 | 9f1f416b5a311dc3 |
| int-finance-s20 | 125 | NA | NA | NA | NA | 0 | NONE |
| int-finance-s21 | 2 | 0 | 0 | 4 | 0 | 16 | df5a4b3e0203cb6f |

Totals: passed=1135 failed=23 error=44 skipped=56. Baseline: 1291/0/0/0. Delta: -156 passed, +23 failed, +44 error, +56 skipped. New finance tests do not explain failures; s15 timed out (124, 900s), s20 no run.json (125). Stopped; no ff.
