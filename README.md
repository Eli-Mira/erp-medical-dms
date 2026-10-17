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

## Phases
Phase 0 (Discovery) ✅ · Phase 1 (Planning) ✅ · Phase 2 (Platform) in progress.
See `docs/PROGRESS_CHECKLIST.md` and `docs/IMPLEMENTATION_PLAN.md`.
