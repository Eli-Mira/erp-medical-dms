# INTEGRATION_READINESS.md

- Finance integrated at 79c8014 (tree e2dd0b315876c410fde1dcd1b2f7d64a82567616).
- Regression-equivalent to base in a degraded environment, NOT a clean pass. 23 failures + 44 errors + 56 skipped on both base and merge; root cause is environment (missing Chromium, s15/s06 timeout, s20 collection crash). No new failures introduced by finance merge. New finance tests (test_overnight_ar_reports.py, test_overnight_csv_exports.py) pass.
- ENV_DIAG.md documents proposed fixes (PLAYWRIGHT_BROWSERS_PATH=/opt/playwright, split browser tests, raise timeout via launcher). No runner edits applied.
- Telegram merge NOT performed. Transfer/Returns policy decision remains open. E11/E18 queued.
