# Inventory Slice 1 — stock ledger and balances

## Current authorization checkpoint — 2026-10-17

This section supersedes the historical slice report below. The previous `893a0d9` completion report was incorrect: branch IDs were used as warehouse IDs; assigned managers were over-granted manual writes; shared-warehouse authorization was not covered by its 162 passing tests.

- `sales_manager` / `district_manager`: **read only**, from explicit `platform.user_branch` joined to active `master_warehouse.branch_id`, returning actual warehouse IDs. No applicable grant → 403; foreign/missing warehouse filters → identical 404. Manual opening/adjustment writes stay denied, even when assigned. Existing owner/finance/warehouse_staff/auditor permissions are unchanged.
- Fulfillment is not authority: Dakahlia + Sharqia use Dakahlia; Gharbia may use Dakahlia or Gharbia. `inventory.branch_warehouse` records compatibility only. Territory/route assignments alone never grant a whole warehouse. Explicit assignment to the warehouse-owning branch is required to see its physical stock pool; no per-territory stock balances are invented.
- Invoice-backed ledger details additionally require the invoice's assigned branch **and** `platform.user_territory`, with a matching source warehouse. Other territories' invoice IDs, actors and quantities are excluded in SQL. Unknown/orphan sources are hidden; warehouse-level manual movements remain visible within explicit warehouse grants. Revocations and disabled accounts affect existing sessions.
- Verification: `docs/evidence/inventory-authorization/` retains desired-behavior RED/GREEN logs, final native/disposable-database runs, source/workbook hash bindings and the scoped review/report. The 20 new regression cases cover allowed IDs, assigned write denial, shared routes, territory isolation, foreign warehouse filters, revocation, disabled accounts and deliberate cross-table UUID collision.
- **Posting remains HTTP 409.** AR and the direct atomic transaction were already implemented after the historical report below. PostgreSQL has permitted valid Posted records since `0006`; it is no longer a second disabled-feature gate. No posting flag was added or activated here.

**Next uncompleted prerequisite:** `app/sales/router.py::_prepare` and `fk_invoice_warehouse_branch` still require invoice branch = source warehouse owner branch. Separate Sharqia/Gharbia sales branches cannot yet use every required shared source. Wire and test fulfillment compatibility without widening inventory authority; then implement the requested default-OFF posting flag. Activation still requires Eli's explicit approval.

No live assignments, source workbooks, production deployment or GitHub push were changed. The five-document security workflow (Security, Auth, Data Security, Threat Model, Security Checklist) remains release work; scoped inventory verification is not whole-system sign-off.

---

## Historical first-slice report (superseded where noted above)

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
| `sales_manager`, `district_manager` | **Denied in this slice.** PRD grants them *branch-scoped* inventory; the `platform.user_branch` mapping now exists (added in `0006`), but inventory authorization has not been rewired to use it yet — denied rather than widened to every warehouse. Rewiring is the tracked follow-up. |
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
