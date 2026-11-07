# ENV_DIAG.md

## Browser missing in runner
- Approved runtime `erp-verify-runtime:20261101-003000-retry02` has Chromium at `/opt/playwright` (used by Codex browser pass).
- Runner sets `PYTHONPATH=/workspace` but not `PLAYWRIGHT_BROWSERS_PATH`. When pytest collects `scripts.browser_test`, `scripts.palette_search_test`, `scripts.private_accounts_ui_test`, `scripts.ui_workflow_test`, Playwright cannot locate Chromium and collection fails (4 errors).
- Proposed fix (patch, not applied): set `PLAYWRIGHT_BROWSERS_PATH=/opt/playwright` in the runner's env dict, OR mount `/opt/playwright` read-only. Do NOT edit runner now.

## s15 hang
- Stage int-finance-s15 timed out at 900s on both base and merge. No pytest.xml/run.json produced. The stage's test files likely include browser-heavy tests (test_lane2_*). Wall-clock exceeded 15 min before collection finished. Proposed: split browser tests into a separate stage or raise timeout only if runner supports it without code edit (it does not; timeout is a launcher-level concern).

## s20 no run.json
- Stage int-finance-s20 produced no run.json. Launcher log shows collection errors (scripts.*) and likely a crash before the runner wrote the receipt. Proposed: fix browser path first; re-run s20 alone.

## s06 timeout
- Stage int-finance-s06 (customer maintenance/contacts) timed out on base at 900s. Likely heavy test set. Proposed: split or increase timeout via launcher (not runner).

Patch file: ENV_DIAG.patch (not applied).
