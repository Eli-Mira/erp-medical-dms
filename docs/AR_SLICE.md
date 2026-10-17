# Receivables (AR) Slice 1 — ledger + atomic posting transaction

**Updated:** 2026-10-17. **Scope:** the customer-receivables half of the eventual atomic posting, plus the tested Invoice → Stock → AR transaction. The HTTP posting endpoint is still disabled (409).

## Delivery and evidence

- [x] Migration `0006_inventory_ar_gate`: `platform.user_branch` mapping; posting-status gates relaxed from "no Posted rows ever" to "a Posted row must carry `posted_at`"; `posted_by` column added.
- [x] Migration `0007_ar_ledger`: `finance.ar_entry` append-only ledger (customer, invoice, entry_type, debit/credit, checks).
- [x] `app/finance/ar.py` + `app/finance/router.py`: AR ledger service and role-gated API.
- [x] `app/sales/service.py::post_invoice_atomic`: the full transaction — decrement stock per line, create the AR debit entry, flip the invoice to Posted — all in one DB transaction.
- [x] Full-suite run: **162 passed, 0 failed, 0 skipped**, direct exit 0. Bound evidence: `docs/evidence/ar-slice1/final-run/{pytest.log,pytest.xml,run.json}` (hashes before/after match; dev `finance.ar_entry`/`inventory.stock_movement`/`inventory.stock_balance` all 0 after tests).
- [x] Fresh disposable database: chain `0001 → 0007`, downgrade to `0005`, re-upgrade, full suite green; disposable DB dropped and absence verified.

## API contract

| Method and path | Behavior |
|---|---|
| `GET /ar/balances` | Balance (`Σ debit − Σ credit`) per customer; optional `customer_id`. |
| `GET /ar/entries` | Ledger, newest first. Filters `customer_id`, `entry_type`, `date_from`, `date_to`. |
| `POST /ar/entries` | Record `opening`/`payment`/`credit_note`/`adjustment`. 201. |

`invoice` is not an accepted API entry type (schema regex) — it is produced only by `post_invoice_atomic`. `adjustment` requires an active reason code. An entry must set at least one of debit/credit. Amounts are non-negative NUMERIC(14,2); the sign lives in which side is set, matching the Excel العملاء `مدين`/`دائن` columns.

## Authorization (PRD §2)

| Role | Access |
|---|---|
| `owner` + `is_owner` | All customers; read + write. |
| `finance` | All customers; read + write. |
| `read_only_auditor` | Read all customers. |
| `sales_manager`, `district_manager` | Read/write **denied**; read scoped to customers in their assigned branches (`platform.user_branch`). No branch assignment ⇒ sees nothing (not everything). |
| `warehouse_staff`, `medical_rep`, `admin`, `user` | Denied. |

The branch-scoped roles now use the `user_branch` mapping: a territory-scoped user and a branch-scoped user are different things, and a branch assignment covers every warehouse in that branch (some territories share warehouses because several branches can serve overlapping territories).

## The atomic posting transaction (tested; endpoint disabled)

`app.sales.service.post_invoice_atomic(db, invoice_id, actor)`:

1. Locks the invoice; rejects anything not `Draft`.
2. For each line, records a stock movement (`movement_type='sale'`, quantity negative) — decrements `inventory.stock_balance`.
3. Records one AR debit entry (`entry_type='invoice'`, debit = `grand_total`).
4. Flips the invoice to `Posted`, sets `posted_at`/`posted_by`, bumps `version`.

All four happen in the caller's transaction. `tests/test_posting.py` proves: the success path (stock 10→8, AR 228.00, invoice Posted with `posted_by`); that insufficient stock raises and rolls back **everything** (invoice stays Draft, stock intact, no movement, no AR entry); and that `POST /invoices/{id}/post` still returns **409** — posting is not enabled through the API.

## Excel reconciliation (real data)

`tests/test_reconciliation.py::test_ar_customer_balance_is_debits_minus_credits` reads the real `الميزانية العمومية 2026.xlsx::العملاء` first customer block (rows 4–5) and asserts `Σ debit − Σ credit == last الرصيد` (22476 − 22476 == 0). All 7 source workbooks still match the frozen hashes.

## What is deliberately not here

The HTTP posting endpoint stays 409. Stock-cover/overstock/low-stock thresholds, transfers, receipts, returns and the Finance GL/P&L/Balance Sheet are deferred. No AR UI — use `/docs`.

## Run locally (existing PostgreSQL must be available)

```bash
uv run --with-requirements requirements.txt alembic upgrade head
uv run --with-requirements requirements.txt python -m pytest tests/ -v
uv run --with-requirements requirements.txt uvicorn app.main:app --host 127.0.0.1 --port 8000
```
