# AGENTS.md — ElsebaeyPharma / Medical Company System

Instructions for AI coding agents (OpenCode, Claude Code, Codex, Hermes). Read this fully before touching anything.

## Project

- **Directory:** `C:\Desktop\Huge system` (this file's directory; always work here)
- **What it is:** Egyptian medical-distribution ERP-lite replacing 7 Arabic Excel workbooks. PostgreSQL + FastAPI + existing vanilla JS/PWA. Arabic/English RTL.
- **Authoritative spec:** `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`
- **Decision record:** `docs/DECISION_LOG.md` (check before contradicting an earlier decision)
- **Module map / flow:** `docs/MODULE_MAP.md`, `docs/APP_FLOW.md`, `docs/Excel feature mappings` (locate actual paths; do not assume absent)
- **Current status:** `docs/PROGRESS_CHECKLIST.md`, `docs/evidence/invoice-cycle/CURRENT_STATUS.md`, `docs/AGENT_HANDOFF.md`
- **Stack (D37, latest explicit owner decision):** FastAPI + PostgreSQL + psycopg3 + existing vanilla JS/PWA. Do **not** rewrite the frontend in React unless complexity justifies it (D37). Architecture or framework replacement requires an explicit request.

## Architecture discrepancy (flagged, not resolved here)

`docs/TECHNICAL_REQUIREMENTS.md` still proposes a Django REST Framework-style i18n approach and a React + TypeScript + Vite + MUI frontend, and `docs/UQ_PROPOSED_ANSWERS.md` records UQ-11 as "approved" for that stack. These conflict with D37 and the stack above, which mandate FastAPI + vanilla JS/PWA. **Do not migrate frameworks during this task.** Reconcile those documents against D37 before any framework work; treat D37 as authoritative until Eli changes it.

## Mission and scope

Build a simple, reliable Arabic web/PWA application that preserves the company's actual Excel business workflows and implements explicitly approved additions. Make everyday work easier on desktop and mobile. Optimize for correct behavior, clear interfaces, maintainability and timely delivery.

- Follow the current user request and latest explicit owner-approved decisions.
- For existing business behavior, inspect the actual workbook, sheet, relevant cells, formulas and links. Keyword matches alone do not establish a workflow.
- Section 2B contains 18 additions, not the complete requirements. The A–H module map does not approve every possible ERP capability.
- Distinguish confirmed requirements, proposals, unresolved rules, deferred work and exclusions. Assistant-generated suggestions are not owner approval.
- Every added business feature needs workbook evidence or an explicit approved request. Record its source briefly in the existing feature mapping.
- Resolve material conflicts explicitly. Do not silently change financial rules, remove required capabilities or "correct" source data.
- Keep scope tied to actual Excel workflows and explicitly approved additions. Do not create more planning documents or expand features.

## Business invariants (do not violate)

- Sales territory and source warehouse are separate.
- Routing: Dakahlia and Sharqia use Dakahlia warehouse; Fayoum uses Fayoum; 6 October uses 6 October; Gharbia may use Dakahlia or Gharbia according to the actual transaction.
- Company warehouse stock and customer-held stock are separate. Sell-in and sell-through are separate.
- Transfers are inventory movements, not sales. Invoices and payments are separate. Products and batches are separate.
- Draft invoices do not change stock or receivables. Never imply otherwise in the UI or demo.
- Preserve approved batch, expiry, returns, VAT and zero-quantity print rules.
- Use exact decimal handling and server-authoritative financial calculations. Do not invent rounding, numbering, payroll, credit or accounting policies.
- Payroll scope is lightweight salary records/payments, without advanced HR. Preserve protected owner/private accounts. UOM conversions, full manufacturing/MRP/BOM and other gated extensions require their approved business rules.

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

## Keep the product simple

- Organize screens around daily tasks: customers, sales, collections, stock, accounts and reports. Group related actions and avoid duplicate navigation.
- Keep technical administration secondary and role-appropriate.
- Hide empty or broken prototype screens from ordinary navigation. Preserve their requirement status in project documentation.
- Clearly label approved simulated previews. Do not count them as implemented workflows or mix simulated results with real backend results.
- Use plain Arabic labels and actionable validation messages. Keep implementation details out of normal user flows.
- Support usable desktop and mobile layouts: touch-friendly controls, readable tables, working drawers, keyboard access and no unintended clipping.
- Treat responsive layout, PWA installation and offline operation as separate capabilities. Claim each only when implemented and tested.

## Protect data and verified work

- Preserve original Excel files. Use synthetic fixtures and isolated demo/test databases.
- Do not access, repair, migrate, stamp or reset quarantined `medical_dms` without explicit owner authorization for that operation.
- Keep `POSTING_ENABLED=False` until explicitly authorized otherwise.
- Use the approved disposable-database verification runner and its documented commands. Confirm isolation before database tests; never run tests against an unidentified/default database.
- Preserve transactions, authorization, territory/warehouse isolation, audit history and approved void/reversal behavior.
- Keep credentials and real company records out of Git, fixtures, screenshots and logs.
- Do not merge into master, push, deploy or expand public access without the relevant authorization. Authorization already granted does not need to be requested again.

## Test commands

Always use the runner (it creates/removes its own disposable database and verifies source/workbook/config hashes):

```bash
"C:/Users/emadg/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" scripts/verify_invoice_cycle.py --stage UNIQUE_NEW_LABEL --chain -- tests/ -q --tb=short
```

- `--stage` must be a **new** unique label; the runner refuses to overwrite an existing stage directory.
- Scoped lint: run Ruff on changed files only (whole-repo has inherited findings; do not claim repository-wide clean).
- Requires a local PostgreSQL reachable at the configured host with CREATE/DROP privileges.

Do **not** run bare `pytest tests/` against the default database.

## Where things live

| Path | Purpose |
|---|---|
| `app/` | FastAPI application (auth, sales, inventory, finance) |
| `alembic/versions/` | Migrations |
| `tests/` | Pytest suites (real-PostgreSQL) |
| `scripts/verify_invoice_cycle.py` | Approved disposable-DB test runner |
| `docs/` | Specs, decisions, slices, checklist |
| `docs/evidence/` | Bound verification evidence — append only |
| `web/` | Existing vanilla JS PWA |

## Verify the requested behavior

- Run checks appropriate to the change and all existing mandatory repository gates. Avoid repeating unchanged checks without a reason.
- Test financial, stock, permission and migration changes with meaningful assertions and focused regression coverage.
- For UI tasks, actually use a browser: interact with forms, save, reopen and verify resulting state. API calls and DOM-presence tests are insufficient evidence of UI completion.
- Match records by their identifiers. The first returned balance or stock row is not proof of the selected customer/product/warehouse.
- Verify calculations against representative source cases with understood fields and formulas.
- Verify print layout and contents, not merely the existence of a Print button.
- For responsive changes, test desktop and mobile viewports. Label emulation separately from physical-device testing.
- Verify public access through the actual HTTPS URL, including login, assets and API requests. Diagnose connectivity with commands and logs rather than assumptions about Windows, WSL or localhost.
- If browser tooling is missing, use or install approved official testing tools in an isolated development environment while preserving protected manifests.
- If blocked, report the exact command/error or quote the actual permission rule. Do not substitute a different check and claim the original passed.

## Work efficiently

- Inspect the current branch, pending changes and relevant existing implementation before editing. Preserve unrelated work.
- Read only the documentation and code relevant to the task. Reuse prior verified findings unless files changed or evidence is missing.
- Choose the smallest useful increment that completes the requested user task. Keep plans brief and then implement.
- Reuse FastAPI, PostgreSQL, Alembic and the existing vanilla JavaScript PWA. Architecture or framework replacement requires an explicit request.
- Prefer existing components and APIs. Avoid speculative modules, generic abstractions, unnecessary dependencies and unrelated refactoring.
- Continue autonomously with authorized, reversible implementation and verification. Do not repeatedly ask permission for ordinary steps.
- Ask one focused question only when an unresolved business decision blocks correct behavior. Continue independent work meanwhile.

## Skills and subagents

- Discover and apply relevant available skills. If unavailable, continue with equivalent direct work and state any material limitation.
- Delegate focused independent work only when it improves quality or saves time. Prevent overlapping edits.
- Use focused independent review for changes to money, stock, migrations or authorization, and follow existing required review gates.
- Verify subagent findings before integration. Failed review blocks integration; inconclusive review needs diagnosis or another verification method, not endless waiting.
- Never fabricate skill usage, reviewer approval, screenshots or test results.

## Finish and report honestly

- Review the final diff, complete applicable checks and commit when authorized.
- Update the existing decision log or progress document only when needed. Avoid creating competing specifications or copying the backlog into this file.
- Keep AGENTS.md stable: no transient commit hashes, test counts, temporary URLs or current-task status.
- Report concisely: what the user can now do, source requirement, changed files/commit, actual verification and remaining limitations.
- Distinguish implemented, tested, untested, deferred and blocked.
- Complete authorized work instead of stopping after a plan or repeatedly waiting for a go-ahead.
EOF
echo "written"