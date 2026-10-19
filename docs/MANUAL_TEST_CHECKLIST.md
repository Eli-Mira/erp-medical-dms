# Manual Testing Checklist (Prototype)

**Server:** http://127.0.0.1:8018/app/  (running, POSTING_ENABLED=false)
**Credentials:** demo_owner / Demo-2026 (also demo_rep, demo_finance; all same password)
**DB:** medical_demo (synthetic, safe to reset via `scripts/make_demo.py`)

## A. Auth & RBAC
- [ ] Login as demo_owner → sees all nav items.
- [ ] Login as demo_rep → sees only permitted nav (invoice, visits, targets own rows, doctors); finance-only items hidden.
- [ ] Login as demo_finance → sees finance items; no invoice create.
- [ ] Logout → returns to login; protected routes 401.

## B. Invoice desk (draft-only)
- [ ] Create draft invoice: customer, warehouse, lines; totals compute (client estimate vs server authority labels).
- [ ] Save draft → status Draft; no stock/AR change.
- [ ] Open saved draft → lines preserved, zero-qty lines dimmed on screen.
- [ ] Print / Save as PDF → zero-qty lines hidden in print.
- [ ] Try /post → 409 surfaced verbatim (no fake success).

## C. Invoice list (REAL)
- [ ] `/invoices` filters: status, date_from, date_to apply and re-fetch.
- [ ] Open invoice from list → detail matches.

## D. Inventory
- [ ] Opening stock movement → balance updates.
- [ ] Adjustment with reason code → balance updates.
- [ ] Insufficient stock → error surfaced.
- [ ] Batches screen (REAL) → FEFO order, zero-balance batches visible.
- [ ] Cover screen (REAL) → no_sales_history status (posting off).

## E. Transfers / Returns (REAL)
- [ ] Transfer between warehouses → source decreases, destination increases, batch preserved, no invoice/AR created.
- [ ] Insufficient stock transfer → 409.
- [ ] Return → warehouse stock increases, reason recorded.

## F. Targets (REAL)
- [ ] Owner sets monthly target for demo_rep → appears in list.
- [ ] demo_rep sees only own rows.
- [ ] Actuals show null (posting off).

## G. Marketing (REAL)
- [ ] Create spend with product links → list shows.
- [ ] Create objective linked to spend → list shows.

## H. AR / Collections
- [ ] Balances screen shows customer balances.
- [ ] Export CSV (Blob) downloads ar-balances.csv.
- [ ] Customer ledger (card) renders entries.
- [ ] Collections list renders.

## I. Audit (REAL)
- [ ] Audit log shows newest-first, filters work (entity_type, actor, date).

## J. Settings
- [ ] Owner reads inventory policy → 30/180 defaults.
- [ ] Owner updates → persists; non-owner → 403.

## K. PWA / UX (Vertix borrow)
- [ ] Reduced motion: animations disabled.
- [ ] Focus-visible outlines on keyboard nav.
- [ ] Escape closes command palette.
- [ ] Skeleton shimmer renders on loading (if applied).
- [ ] Count-up KPI tiles on Home animate (skip if reduced motion).
- [ ] Print view hides zero-qty lines.

## L. RTL / i18n
- [ ] All screens RTL; ar/en key parity (no missing keys).

## R-35 click-through evidence (record screenshots)
- [ ] Print invoice
- [ ] Invoice list
- [ ] Targets
- [ ] Batches
- [ ] Cover
- [ ] Audit
- [ ] Transfers
- [ ] Returns
- [ ] Marketing
- [ ] Balances CSV export

## Blocked (cannot test here)
- Server-side PDF (D45) — needs requirements.txt approval.
- Phase-4 items (cash/bank, expenses, P&L, payroll, POs) — need business rules.
- Independent review — needs authorized reviewer.
- Lighthouse pass — needs Chrome + lighthouse.
EOF
echo "written"