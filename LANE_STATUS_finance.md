# LANE_STATUS_finance — 2026-11-06

Card: E07 AR statements + aging (t_88e7781f) and E08 CSV exports. Lane: feature/lane-finance.
Commit under test: 99de4f4 (tree e79776bb209e5c28be9c7156febba8770d8220e1).
RED: 48 failed / 3 passed, exit 1 — tests/test_overnight_ar_reports.py + tests/test_overnight_csv_exports.py (out-red10/red-10/run.json, sha256 f17414da5372ee2bb6452a0156ae6d1ff9e9c9a0c545dc6cdda6d5ea8d0ece8f).
GREEN: 92 passed / 0 failed, exit 0 — those two + tests/test_ar_ledger.py + tests/test_collections.py (out-focus15/focus-15/run.json, sha256 ff4bff576cff02eeb1e03a52f63df57ede3fb191b51566c45126c475f818f224).
Full suite (6a9a139): 1208 passed / 38 failed / 40 error / 56 skipped; base 2fed444: 1160 / 35 / 40 / 56. This lane's modules: 0 failures.
The 3 branch-only failures pass under equivalent isolation (1/1 each, exit 0): iso-inv1 f4985015…, iso-inv2 c726f891…, iso-beta3 c8fce0e4… — shared-DB contamination, not the diff.
Shared files for integration owner: app/finance/payment_router.py (new /collections/export + shared _visible_receipts), tests/conftest.py (two module names appended to the financial admission set, append-only).
Next: reviewer sign-off on REVIEW_PACKET_E07.md. E09 search/alerts stays queued — separate blocked card (R40), untouched by this lane.
