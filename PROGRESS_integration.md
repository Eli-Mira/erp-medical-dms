# PROGRESS_integration.md

Plan:
1. Verify integration worktree branch/HEAD/tree/status; record overnight-runner-wip.patch sha256. ✅ Done: branch feature/erp-integration-20261107, HEAD 18c251e93bfaf368902596aad3d0b78369f7231a, tree 5ed40d98a71b820449a08cc62f675495d053b27b, status only PROGRESS_integration.md untracked. Patch sha256 ed039f4279c0b8379aad6f6c89e4be1311d43443d8125108065d800a5a18cee2 (C:/Projects/ERP-Verify/erp-integration-20261107-intake/overnight-runner-wip.patch). Exit 1 on missing local patch path; found in intake.
2. Create finance trial branch from 18c251e; verify finance candidate tree; merge --no-ff; list conflicts before resolving.
3. Confirm one Alembic head and posting default returns 409.
4. Run full contained suite with H0 runner on merge commit; record commit/tree, exit, counts, sha256 per result; compare to 1291/0 baseline.
5. If pass: fast-forward feature/erp-integration-20261107 and update INTEGRATION_READINESS.md. If fail: stop, write INTEGRATION_FAIL_finance.md, re-run failing tests in isolation.
6. No push/tag/deploy/Telegram merge; keep trial branch.
