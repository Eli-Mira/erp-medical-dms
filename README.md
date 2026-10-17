# Medical Company System

Egyptian medical-distribution ERP-lite replacing 7 Arabic Excel workbooks
(1 finance + 1 private-accounts + 5 branch sales). PostgreSQL + PWA,
Arabic/English RTL. Zero-cost / open-source-first (D4).

## Sources of truth
- `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` — authoritative spec
- `docs/DECISION_LOG.md` — all decisions (D1–D32)
- 7 `*.xlsx` source workbooks (SHA-256 in `docs/SOURCE_HASHES.txt`)

## Local dev setup
Uses Docker for PostgreSQL + a uvicorn service.

```bash
docker compose up --build   # starts db (5432) + app (8000)
curl http://localhost:8000/health   # -> {"status":"ok",...}
```

Run tests locally:
```bash
docker compose exec app uv run pytest -q
```

## Invoice Slice 1 — draft API

Current contract, permissions, exact Excel coverage and remaining production gates:
`docs/INVOICE_SLICE_1.md`. Posting is disabled in both API and database; use the
existing `/docs` interface to exercise draft endpoints. No PWA redesign.

From the project root with PostgreSQL running locally:

```bash
uv run --with-requirements requirements.txt alembic upgrade head
uv run --with-requirements requirements.txt python -m pytest tests/ -v
uv run --with-requirements requirements.txt uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The migration CLI uses `alembic.ini`; the app uses `DATABASE_URL`. Match their
targets explicitly if not using the default local development database.
These are local-development commands, not a production deployment procedure.

## Inventory Slice 1 — stock ledger and balances

Movement types `sale`, `return` and `transfer_*` are rejected here; they belong
to the posting and transfer flows. Balance cannot go below zero (API 409,
database `ck_stock_balance_nonneg`). Contract, roles and the deferred
branch-scoping item: `docs/INVENTORY_SLICE.md`.

## Receivables (AR) Slice 1 — ledger + atomic posting transaction

`finance.ar_entry` (balance = Σdebit − Σcredit, matching Excel العملاء) and the
`platform.user_branch` mapping are in. `post_invoice_atomic` performs the
Invoice → Stock → AR transaction and is tested, but `POST /invoices/{id}/post`
still returns **409** — posting is not enabled through the API. Contract, roles
and evidence: `docs/AR_SLICE.md`.

## Phases
Phase 0 (Discovery) ✅ · Phase 1 (Planning) ✅ · Phase 2 (Platform) in progress.
See `docs/PROGRESS_CHECKLIST.md` and `docs/IMPLEMENTATION_PLAN.md`.
