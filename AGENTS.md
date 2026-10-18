# AGENTS.md — ElsebaeyPharma / Medical Company System

Instructions for AI coding agents (OpenCode, Claude Code, Codex, Hermes). Read this fully before touching anything.

## Project

- **Directory:** `C:\Desktop\Huge system` (this file's directory; always work here)
- **What it is:** Egyptian medical-distribution ERP-lite replacing 7 Arabic Excel workbooks. PostgreSQL + FastAPI + existing vanilla JS/PWA. Arabic/English RTL.
- **Authoritative spec:** `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`
- **Decision record:** `docs/DECISION_LOG.md` (D1–D38) — check before contradicting an earlier decision
- **Current status:** `docs/PROGRESS_CHECKLIST.md`, `docs/evidence/invoice-cycle/CURRENT_STATUS.md`
- **Stack (D37):** FastAPI + PostgreSQL + psycopg3 + existing vanilla JS/PWA. Do **not** rewrite the frontend in React.

## HARD SAFETY RULES — never violate

1. **Never enable production invoice posting.** `POSTING_ENABLED` must default OFF (`app/config.py`). Posting/reversal/collections endpoints must keep returning HTTP 409 outside isolated tests.
2. **Never run tests, migrations or the app against the `medical_dms` database.** It is quarantined (stamp/schema drift from a worker incident). Use only fresh disposable `dms_cycle_test_*` databases via the approved runner.
3. **Never write the 7 source Excel workbooks** (`*.xlsx` in the project root). They are read-only reconciliation inputs with a frozen SHA-256 baseline (`docs/SOURCE_HASHES.txt`).
4. **Never edit** `.env`, `.env.dev`, `app/db.py`, `app/config.py`, `docker-compose.yml`, `Dockerfile`, `requirements.txt` as part of feature work. These are protected files whose hashes are checked by the test runner.
5. **Never merge into `master`.** Work on a named branch.
6. **Never push to GitHub or create a remote.** Publication is blocked pending credential/confidential-data cleanup (see `docs/AGENT_HANDOFF.md` §7).
7. **Never perform database recovery writes** on `medical_dms` without explicit owner approval. No downgrade, stamp reset, schema drop or business-row mutation.
8. **Never modify or delete existing evidence** under `docs/evidence/`. Append new evidence; do not rewrite history.
9. **Never invent business rules.** If the workbooks/spec do not prove a rule, add it to `docs/OPEN_QUESTIONS.md` — do not guess (D29).

## Development rules

- **Verify, never assume (D29).** Confirm a file exists at its exact path and read real content before claiming work is done. A subagent's "completed" summary is not proof.
- **One behavior at a time.** Small end-to-end slice, its failing test, then the smallest implementation. Run covering tests.
- **Server owns financial values.** Amounts, VAT, status, actor, customer and branch come from the server/locked invoice — never from client input. Use `Decimal`, never float.
- **Own the whole HTTP transaction.** Route owns commit/rollback. Assemble the complete response, write the actor-bound audit in the same transaction, then commit. Roll back everything on failure.
- **Revalidate at the financial transition.** Grants, references and routes are rechecked at posting time, not only at draft creation.
- **Keep the existing structure.** Match surrounding patterns (raw parameterized SQL via `sqlalchemy.text()`, services own no commits, routers own transactions).
- **Parameterize all SQL.** Identifiers may come only from fixed internal literals.
- **Tests use real PostgreSQL** on a disposable database; savepoint fixtures prove sequential behavior, not durable commits or concurrency.

## Test commands

Always use the runner (it creates/removes its own disposable database and verifies source/workbook/config hashes):

```bash
"C:/Users/emadg/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" scripts/verify_invoice_cycle.py --stage UNIQUE_NEW_LABEL --chain -- tests/ -q --tb=short
```

- `--stage` must be a **new** unique label; the runner refuses to overwrite an existing stage directory.
- Expected current result: **315 passed**, 0 failed/errors/skips.
- Scoped lint: run Ruff on changed files only (whole-repo has 145 inherited findings; do not claim repository-wide clean).
- Requires a local PostgreSQL reachable at the configured host with CREATE/DROP privileges.

Do **not** run bare `pytest tests/` against the default database.

## Where things live

| Path | Purpose |
|---|---|
| `app/` | FastAPI application (auth, sales, inventory, finance) |
| `alembic/versions/` | Migrations; current head is `0010_invoice_collections` |
| `tests/` | Pytest suites (real-PostgreSQL) |
| `scripts/verify_invoice_cycle.py` | Approved disposable-DB test runner |
| `docs/` | Specs, decisions, slices, checklist |
| `docs/evidence/` | Bound verification evidence — append only |
| `web/` | Existing vanilla JS PWA |

## Current milestone

Invoice → Stock → AR → Collections local API slice is **complete and independently reviewed**: milestone commit `d233893`, closeout `898e034`, branch `milestone/invoice-collection-20261017`. Posting stays OFF. Read `docs/AGENT_HANDOFF.md` before starting any new work.
