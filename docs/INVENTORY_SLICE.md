# Inventory Slice 1 — stock ledger and balances

**Updated:** 2026-10-17. **Scope:** the stock half of the eventual atomic invoice posting. Invoice posting is still disabled in both the API and PostgreSQL.

## Delivery and evidence

- [x] Migration `0005_inventory_stock`: append-only `inventory.stock_movement` ledger and `inventory.stock_balance` running total per `(warehouse, product, batch)`, plus a batch↔warehouse uniqueness pair so a movement cannot move a batch into the wrong warehouse.
- [x] `app/inventory/{schemas,service,router}.py`: atomic movement application (ledger row + balance in one transaction), role-gated read/write API, audit entry per movement.
- [x] Full-suite run: **132 passed, 0 failed, 0 skipped**, direct exit 0 — `docs/evidence/inventory-slice1/final-run/{pytest.log,pytest.xml,run.json}` binds source/test/workbook hashes before and after execution. 41 of those cases are new inventory controls.
- [x] Fresh disposable database: chain `0001 → 0005` applied, `0005` downgraded to `0004` and re-applied, then the full suite passed against it. The UUID-named database was dropped and its absence verified. The dev database was not dropped.
- [ ] Customer-receivables ledger and the atomic stock+AR posting flow: **not built**. This is why posting stays blocked.

## API contract

Bearer authentication uses existing `/auth/login` sessions. Decimal values serialize as strings.

| Method and path | Behavior |
|---|---|
| `GET /inventory/stock` | Current balances. Filters `warehouse_id`, `product_id`, `batch_id`. |
| `GET /inventory/movements` | Ledger, newest first. Filters `warehouse_id`, `product_id`, `batch_id`, `movement_type`, `date_from`, `date_to`. |
| `POST /inventory/movements` | Record `opening` or `adjustment`; updates the balance atomically and audits the actor. 201. |

`opening` requires a positive quantity. `adjustment` requires a non-zero signed quantity and an active `audit.reason_code` of category `adjustment`. `sale`, `return`, `transfer_in`, `transfer_out` and `receipt` are rejected (422) here — they belong to the posting and transfer flows, which do not exist yet. A movement that would drive a balance below zero returns **409** and writes nothing.

Balances are keyed per `(warehouse, product, batch)`; batch-less stock is a separate row from batched stock. `ck_stock_balance_nonneg` is the database backstop behind the API's 409.

## Authorization (PRD §2)

| Role | Access |
|---|---|
| `owner` **and** `is_owner=true` | Read and write every warehouse. A role label alone cannot grant Owner authority. |
| `warehouse_staff` | Read and write all warehouses (PRD: "All warehouses' stock levels, movements, batches, expiry"). |
| `finance` | Read all stock; write adjustments (PRD: "stock adjustments … per reason code"). |
| `read_only_auditor` | Read only. |
| `sales_manager`, `district_manager` | **Denied.** PRD grants them *branch-scoped* inventory, but no user→branch assignment table exists. Denied rather than widened to every warehouse. |
| `medical_rep`, `admin` | Denied. |
| `user` / unknown roles | Denied. |

The branch-scoped roles are the one open authorization item in this slice: enabling them needs a `platform.user_branch` assignment table and Eli's decision on who is assigned where.

## What is deliberately not here

Stock cover (`current stock / recent average daily sales rate`), overstock alerts and low-stock alerts (APP_FLOW §5 D3–D5) are threshold/reporting features, not posting blockers, and are deferred. Transfers, receipts and returns are deferred with the purchasing and posting flows. There is no inventory UI in this slice — use the existing `/docs` interface.

## Run locally (existing PostgreSQL must be available)

From `C:/Desktop/Huge system`:

```bash
uv run --with-requirements requirements.txt alembic upgrade head
uv run --with-requirements requirements.txt python -m pytest tests/ -v
uv run --with-requirements requirements.txt uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The migration CLI uses `alembic.ini`; the app uses `DATABASE_URL`. Match their targets explicitly for any non-default environment. These are local-development commands, not a production deployment procedure.
