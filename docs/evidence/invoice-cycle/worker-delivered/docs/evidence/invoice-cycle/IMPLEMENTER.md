# Invoice→Stock→AR→Collection Milestone: Implementer Report

## Scope
Isolated posting transaction repair, append-only posted reversals, receipt/void workflow, and real PostgreSQL integration tests — behind POSTING_ENABLED gate (defaults OFF). No production activation, no real data, no commits.

## Files Changed / Created

### Database Migration
- **alembic/versions/0010_invoice_collections.py** (71 lines) — Creates `finance.payment_receipt` table with unique receipt_no per branch, foreign keys to sales_invoice; downgrade raises `NotImplementedError` to preserve history (refuse transactionally). Append-only: void retains original row, appends AR adjustment debit entry.

### API Schema
- **app/finance/schemas.py** — Added `ReceiptIn`, `ReceiptOut`, `ReceiptVoidIn` Pydantic models; all amounts are `Decimal` with exactly two-decimal precision.

### Receipt Service
- **app/finance/payments.py** (154 lines) — `create_receipt`, `fetch_receipt`, `list_receipts`, `void_receipt`, `sum_active_receipts` with `FOR UPDATE` row locking and overpayment guard (`sum_active_receipts > grand_total → 409`).

### Collections API Router
- **app/finance/payment_router.py** (208 lines) — Endpoints: `POST /collections`, `POST /{id}/void`, `GET /collections`, `GET /{id}`; role-based access (read: Owner, Finance, Sales Manager, District Manager, Medical Rep (own), Read-Only Auditor (Posted-linked only); write: Owner, Finance only); `POSTING_ENABLED` gate returns `409` when flag OFF; UUID-to-string serialization guard in `_audit`.

### Sales Service
- **app/sales/service.py** — `post_invoice_atomic` (decrements stock + AR debit + flips to Posted in one transaction); `reverse_invoice_atomic` (increments stock + AR credit + flips to Voided, `posted_at` retained).

### Sales Router
- **app/sales/router.py** — Reverse endpoint; updated `_invoice()` scope to allow `read_only_auditor` to view invoices with `posting_status="Posted"` OR `"Voided"` (with `posted_at` retained); updated `post_invoice` and `void_invoice` endpoints preserve transaction-ownership architecture.

### App Wiring
- **app/main.py** — Includes `collections_router`.

## Test Results (verified with `scripts/verify_invoice_cycle.py --stage <name> -- tests/<file>.py -q --tb=short`)

| Stage | Test File | Result |
|---|---|---|
| test1 | test_posting_flag.py | 3 passed, exit 0 |
| test_collections_fixed5 | test_collections.py | 11 passed, exit 0 |
| test_cycle_fixed_final | test_invoice_cycle.py | 3 passed, exit 0 |

### Key Test Coverage
- `test_posting_flag.py`: POSTING_ENABLED=OFF blocks post/post/reverse/collect mutations with 409
- `test_collections.py`: create receipt (partial/final), void receipt (appends AR adjustment, flips status), uniqueness constraint per branch, overpayment rejection, scoped listing (Owner/Finance/read_only_auditor)
- `test_invoice_cycle.py`: full Post→Partial Collect→Full Collect→Void Receipt→Reverse Invoice cycle; concurrent overpayment rejection via API; flag-off blocks all mutations; reversal/void idempotency (409 on re-run); auditor scope (Voided with posted_at retained, denied Draft)

## Critical Controls Preserved
- **Append-only receipts**: voiding appends AR counter-entry; original row retained
- **Exact VAT snapshots**: two-decimal `Decimal` throughout
- **Unique receipt number per branch**: DB unique constraint `uq_receipt_branch_no`
- **Overpayment guard**: `409` when `sum_active_receipts + amount > grand_total`
- **POSTING_ENABLED gate**: all write endpoints (`post`, `reverse`, `collect`, `void-collect`) return `409` when OFF; tests enable locally via `cfg.POSTING_ENABLED = True` + router module copy
- **Auditor read scope**: `read_only_auditor` can inspect `Posted` and `Voided` (with `posted_at` retained); denies `Draft` and draft-voided (`posted_at is None`)
- **Migration downgrade safety**: raises `NotImplementedError` to refuse dropping collection data silently
- **Real PostgreSQL integration**: each stage creates an independent disposable DB (`dms_cycle_test_*`), runs migrations explicitly, sets `APP_ENV=test`, captures raw output/JUnit/hashes, removes DB and asserts absence

## No Changes Outside Whitelist
All modifications are within the approved file set. No production activation, no real-DB reads/writes, no commits.