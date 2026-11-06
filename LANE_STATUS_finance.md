# LANE_STATUS_finance — 2026-11-06

Card: E07 AR statements + aging (t_88e7781f) and E08 CSV exports. Lane: feature/lane-finance.
Commit under test: 6a9a139 (tree e95cc6f9eccc2b46df695c957aa7d6a362120370).
RED: 48 failed / 3 passed, exit 1 — tests/test_overnight_ar_reports.py + tests/test_overnight_csv_exports.py (out-red10/red-10/run.json, sha256 f17414da5372ee2bb6452a0156ae6d1ff9e9c9a0c545dc6cdda6d5ea8d0ece8f).
GREEN: 87 passed / 0 failed, exit 0 — those two + tests/test_ar_ledger.py + tests/test_collections.py (out-focus13/focus-13/run.json, sha256 77c14604037dac212045f2833cee920a139c36e60c81c293ec78f004ab399642).
Full suite (branch 6a9a139): 1208 passed / 38 failed / 40 error / 56 skipped, unchanged=true; this lane's modules have 0 failures.
Full suite (base 2fed444): 1160 passed / 35 failed / 40 error / 56 skipped; the 3 extra branch failures are shared-DB contamination in test_inventory_cover (2) and test_beta3_financial_ordering (1), modules this diff does not touch.
Shared files for integration owner: app/finance/payment_router.py (new /collections/export + shared _visible_receipts), tests/conftest.py (two module names appended to the financial admission set, append-only).
Next: reviewer sign-off on REVIEW_PACKET_E07.md. E09 search/alerts stays queued — separate blocked card (R40), untouched by this lane.
