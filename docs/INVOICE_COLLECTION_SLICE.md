# Invoice → Stock → AR → Collection — test-only API slice

## Current state

Current source has **315 passing tests**, no failed/error/skipped cases, plus **16 overlapping lifecycle/race/rollback controls** repeated on a separate disposable database. Scoped Ruff on 17 changed Python files is clean; whole repository still has 145 inherited findings (169 at baseline). Independent current-code SPEC/QUALITY/SECURITY review passed, with precise parent corrections and non-blocking findings dispositioned in `finalization-20261018/REVIEW_INTAKE.md`. Fresh candidate and post-integration full suites each passed all 315 cases on separate disposable databases with unchanged source/config/Excel, default OFF and verified cleanup; these are repeated controls, not additional unique cases. Verified local code commit: **`d233893425bc23df9d344bd9e0b88c6f501b4828`**; the committed Git tree/source blobs and raw evidence bytes were read back against the tested candidate. Current status: `docs/evidence/invoice-cycle/CURRENT_STATUS.md`. One Starlette/anyio dependency deprecation warning is unchanged.

**Production posting remains OFF. Do not run this branch against the default local database yet.** The rejected worker directly applied its old migration 0010 there despite isolation instructions. Read-only assessment confirms an empty receipt table and 0010 stamp, but missing final link columns/guards. Applying `upgrade head` would not resolve that stamp/content mismatch. No automated recovery has been attempted. Approval for controlled schema recovery is required; company-row immutability across the whole historical task cannot be certified from a missing preimage.

## API workflow

| Operation | API | Behavior |
|---|---|---|
| Create invoice | `POST /invoices` | Existing validated Draft workflow; snapshots trusted product VAT/prices. |
| Post invoice | `POST /invoices/{id}/post` | Locks invoice; revalidates territory/source grants, active references and route; commits Stock + AR + Posted status + before/after audit atomically. |
| Collect | `POST /collections` | Owner/Finance only; `invoice_id`, `invoice_version`, `receipt_no`, `receipt_date`, positive exact amount, `method` (`cash`/`check`/`transfer`), optional note. Customer/branch/status/actor are server-owned. Partial/final receipts allowed; overpayments rejected. |
| Read receipts | `GET /collections`, `GET /collections/{id}` | Scoped via linked invoice territory/responsibility; managers additionally need branch assignment. Optional invoice/customer/date filters. |
| Void receipt | `POST /collections/{id}/void` | Current receipt `version` and active void/reversal `reason_id`; retains receipt/original payment and appends a linked AR debit. |
| Reverse invoice | `POST /invoices/{id}/reverse` | Owner/Finance, current invoice `version`, active reason; active receipts must first be voided. Retains posted header/lines/VAT and appends exact stock/AR counter-entries linked to originals. |
| Inspect balances/history | `GET /ar/balances`, `/ar/entries` | Existing AR scope; linked receipt and reverse-entry IDs included in ledger output. |

All four new financial mutation paths use the existing `POSTING_ENABLED` gate and return 409 when OFF. Duplicate posting/reversal/void, stale versions, exhausted stock, overpayment and wrong lifecycle states reject without partial writes. Missing/out-of-scope entities return 404, forbidden roles 403, disabled sessions 401 and invalid inputs/reasons 422. Unexpected late AR/audit failure rolls back every financial/status/audit write.

The invoice row is the common serialization point. Independent committed race controls require two PostgreSQL backend PIDs and cover duplicate posts/reversals/payment voids, competing stock, simultaneous overcollection and reversal-versus-payment. Posted/voided invoice snapshots, receipts and stock/AR ledger history reject direct UPDATE/DELETE. Schema-owner/superuser/TRUNCATE protection and deployment least privilege are separate production concerns.

## Boundaries

- One invoice per receipt; multiple partial receipts supported. No multi-invoice allocations, advances or overpayments.
- Receipt void is an accounting counter-entry, not a bank refund. No cash/GL/bank settlement engine or partial product-return workflow was added.
- Reversals use the current PostgreSQL date while retaining original dates, amounts, tax and posting metadata. Production timezone/accounting-period policy still needs sign-off.
- Existing VAT-inclusive Decimal/half-up calculations are preserved, not a claim of validated production tax/printed-invoice exception policy.
- Existing `/docs` is the API interaction surface; no new PWA UI, deployment, company-data import or GitHub push.

## Repeat verification safely

Use the interpreter with the already-installed dependencies:

```bash
"C:/Users/emadg/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" scripts/verify_invoice_cycle.py --stage UNIQUE_NEW_LABEL --chain -- tests/ -q --tb=short
```

The runner exclusively creates a fresh local `dms_cycle_test_*` database, binds Alembic and the application explicitly, uses synthetic writable fixtures, verifies source/workbook/config hashes/default OFF, then removes and verifies absence of only its created database. New financial tests also refuse a non-disposable database before enabling any flag. Source workbooks are read-only reconciliation inputs.

Empty 0010 downgrade/re-upgrade is tested. Populated downgrade refuses transactionally before deleting financial provenance; recovery is never an automatic deletion of history.

Evidence: `docs/evidence/invoice-cycle/PARENT_REPORT.md`, final raw log/JUnit/run records, frozen `review-input/manifest.json`, original delivery disposition and `DEFAULT_DB_INCIDENT.json`. Original worker evidence loss remains explicitly historical; fresh runs establish current behavior only.
