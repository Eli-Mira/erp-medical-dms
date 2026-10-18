# Agent Handoff — Hermes → OpenCode

**Generated:** 2026-10-18
**Purpose:** Complete, safe transfer of the ElsebaeyPharma ERP (Medical Company System) from Hermes to OpenCode.
**Status:** Local source checkpoint verified and committed. Production OFF. No push. No DB recovery.

> **OpenCode must open this directory:** `C:\Desktop\Huge system`

---

## 1. Repository state

| Item | Value |
|---|---|
| **Project directory** | `C:\Desktop\Huge system` |
| **Current branch** | `milestone/invoice-collection-20261017` |
| **Git HEAD** | `898e034d996019752f9afcee060e7c38d5baa9c5` |
| **Milestone commit** | `d233893425bc23df9d344bd9e0b88c6f501b4828` |
| **Milestone tree** | `158b71380626ec777c58b8f46d8c14200cc19518` |
| **Closeout commit** | `898e034d996019752f9afcee060e7c38d5baa9c5` (docs only) |
| **Branch base / `master`** | `f85b8f964b5b4b54139cbdf614e37a91bd6a45a4` |
| **Worktrees** | One only: `C:\Desktop\Huge system` at `898e034` |
| **Working tree** | Clean except untracked `graphify-out/` (pre-existing, unrelated — leave it) |
| **Alembic head** | `0010_invoice_collections` |
| **Git remote** | **None configured** |
| **Git hooks** | Only Git's default `.sample` files — no local hook enforcement |

### ⚠️ Hash correction

The hash `d235893` is **not a valid object in this repository**. The actual milestone commit is **`d233893`** (full: `d233893425bc23df9d344bd9e0b88c6f501b4828`). Verified with `git cat-file -t d233893` → `commit`, and `git cat-file -t d235893` → `fatal: Not a valid object name`. Use `d233893`.

### Branch history (newest first)

```
898e034  docs: record verified invoice lifecycle checkpoint      ← HEAD, closeout
d233893  [verified] Complete isolated invoice and collections lifecycle
f85b8f9  Progress checklist: sales routing prerequisite verified complete   ← master, branch base
5f2e85d  Sales routing: ruff format cleanup + final checklist state
2b46e6f  Sales routing: verification evidence for source-warehouse decoupling
c50bb02  AR Slice 2: decouple sales invoice branch from source-warehouse owner branch [skip-ci]
```

### The "held cycle commit" — resolution

The milestone work was previously **held pending independent review**. That review has since **completed and passed**, so the hold is resolved:

- **Commit:** `d233893425bc23df9d344bd9e0b88c6f501b4828`
- **Location:** branch `milestone/invoice-collection-20261017`, second commit from HEAD. Reachable directly: `git show d233893`
- **Review status:** independent current-code **SPEC / QUALITY / SECURITY = PASS** (reviewer `deleg_62e4d5cd`, 30/32 tool calls, complete 17-file/22-hunk coverage). An earlier reviewer (`deleg_cc032a64`) returned **NO_VERDICT** — its output was unexecuted tool-call markup, not a verdict. That NO_VERDICT is preserved as history and was **not** treated as approval; a fresh retry supplied the real verdict.
- **Reported 315 tests — verified:** two independent fresh runs on separate disposable databases each returned **315 passed, 0 failed/errors/skips**. Both are native executions, not saved-artifact claims.
- **How OpenCode accesses it:** it is already the checked-out branch. `git log --oneline -2`, `git show d233893 --stat`. No checkout or fetch needed.

### Unmerged work preservation

All milestone work is preserved on the named branch `milestone/invoice-collection-20261017` and is **not merged into `master`**. `master` remains at `f85b8f9`. This branch must not be merged or approved without owner sign-off.

---

## 2. Completed functionality and architecture

### Phase status

Phase 0 (Discovery) ✅ · Phase 1 (Planning) ✅ · Phase 2 (Platform) in progress.

Build order (D30): `A Platform → B Master Data → C Sales → D Inventory → E Finance → F Marketing → G Purchasing → H Executive Analytics/Telegram`.

### Completed modules

| Module | Status | Evidence |
|---|---|---|
| **A Platform** | Auth/session, RBAC (9 roles, D34), audit log, reason codes, posting status Draft→Posted→Voided | `docs/PROGRESS_CHECKLIST.md` |
| **B Master Data (partial)** | Customers, branches, products, warehouses, batches, territories | `docs/DATABASE_SCHEMA.md` |
| **C Sales — Invoice Slice 1** | Validated Draft invoice API, snapshot pricing, VAT-inclusive calc, territory/warehouse scope | `docs/INVOICE_SLICE_1.md` |
| **C Sales — routing** | Sales branch decoupled from source-warehouse owner branch (Sharqia/Gharbia) | `c50bb02`, `docs/evidence/sales-source-warehouse/` |
| **C Sales — posting gate** | Default-OFF `POSTING_ENABLED`; endpoint returns 409 while OFF | `ac596eb` |
| **D Inventory — Slice 1** | Append-only stock ledger + per-warehouse/product/batch balances, non-negative constraint | `docs/INVENTORY_SLICE.md` |
| **D Inventory — authorization** | `platform.user_branch` resolves real owned warehouse IDs; managers read-only; no whole-warehouse grant from shared routes | `docs/evidence/inventory-authorization/` |
| **E Finance — AR Slice 1** | `finance.ar_entry` (balance = Σdebit − Σcredit), atomic posting transaction | `docs/AR_SLICE.md` |
| **E Finance — Invoice→Stock→AR→Collection** | Gated atomic posting, linked append-only reversal, invoice-linked partial/final collections, receipt void | `d233893`, `docs/INVOICE_COLLECTION_SLICE.md` |

### Invoice → Stock → AR → Collections (the current milestone)

| Operation | Endpoint | Behavior |
|---|---|---|
| Post invoice | `POST /invoices/{id}/post` | Locks invoice, revalidates territory/source grants and routes, commits stock + AR + Posted status + audit atomically |
| Reverse invoice | `POST /invoices/{id}/reverse` | Owner/Finance only; appends exact linked stock/AR counter-entries; retains originals; requires active receipts be voided first |
| Collect | `POST /collections` | Owner/Finance only; one invoice per receipt, partial/final allowed, overpayment rejected, customer/branch server-derived |
| Read receipts | `GET /collections`, `/collections/{id}` | Scoped via linked invoice territory/responsibility |
| Void receipt | `POST /collections/{id}/void` | Appends linked AR debit; retains original receipt |

All four mutation paths return **HTTP 409 while `POSTING_ENABLED` is OFF**. Database triggers enforce append-only stock/AR ledgers and immutable terminal invoice/receipt rows.

### Architecture

```
FastAPI routers (own transaction + commit/rollback + audit)
        ↓
Domain services (no commits; caller's transaction)
  app/sales/service.py       post_invoice_atomic, reverse_invoice_atomic
  app/inventory/service.py   append-only stock ledger + balances
  app/finance/ar.py          receivables ledger
  app/finance/payments.py    receipts + void
        ↓
Parameterized SQL via sqlalchemy.text()  →  PostgreSQL
```

- **Serialization point:** the invoice row (`SELECT … FOR UPDATE`), always locked **before** receipt/stock rows. Consistent lock order avoids deadlocks.
- **Frontend:** existing vanilla JS PWA in `web/` (not rewritten — D37).
- **Interactive API surface:** FastAPI `/docs`.

---

## 3. Key business decisions and specifications

Full record: `docs/DECISION_LOG.md` (D1–D38). Highlights an agent must not contradict:

| ID | Decision |
|---|---|
| D1 | `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` is authoritative |
| D2 | Custom system; ERPNext is reference only |
| D3 | PostgreSQL + responsive PWA |
| D4 | Zero-cost / open-source-first — non-negotiable |
| D5 | Host on existing always-on CEO-room PC; PostgreSQL never publicly exposed |
| D6 | Telegram before WhatsApp |
| D7 | Excel workbooks are the operational source of truth; no guessing |
| D10 | Private/Owner Accounts: same DB, separate protected module + permissions/audit boundary |
| D17 | 5 sales workbooks = 5 branches; same-named sheets are branch-scoped |
| D23 | AR ledger = normalized AR entries (the wide Excel layout is a pivot) |
| D24 | Budgeting out of scope |
| D29 | **Never assume something is done without verifying it exists and is fully implemented** |
| D34 | 9 roles: Owner, Admin, Finance, Sales Manager, District Manager, Medical Rep, Warehouse Staff, Read-Only Auditor |
| D35 | AR = transaction ledger + monthly summaries; preserve opening balances and history |
| D36 | 14% VAT-inclusive per existing invoice; rates configurable per product; **verify exceptions before production** |
| D37 | FastAPI + PostgreSQL + psycopg3 + existing vanilla JS/PWA |

**Conservative scope decisions for the current slice** (do not silently widen): API-only via `/docs` (no new UI); Owner/Finance only for new financial mutations; one invoice per receipt; no advances/overpayments; void receipts before reversing a paid invoice; no GL/cash/bank settlement or refund execution; no partial product returns.

**Unresolved business rules:** printed-invoice rounding/tax exceptions, payroll formula (UNVERIFIED), stock thresholds, reversal accounting-period policy. See `docs/OPEN_QUESTIONS.md`.

---

## 4. Exact commands to reproduce tests and verification

### Approved test runner (use this — never bare pytest)

```bash
cd "C:/Desktop/Huge system"
"C:/Users/emadg/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" scripts/verify_invoice_cycle.py --stage UNIQUE_NEW_LABEL --chain -- tests/ -q --tb=short
```

What the runner does and why it is safe:
- Creates a fresh `dms_cycle_test_<32-hex>` database, binds Alembic **and** the app to it explicitly, runs the suite, then drops it and asserts absence.
- Refuses any non-local database host.
- Applies the full migration chain, then `down -1` and back up (`--chain`).
- Hashes all of `app/`, `tests/`, `alembic/`, `web/`, `scripts/`, the 7 `*.xlsx`, `.env*`, compose/Dockerfile/requirements before and after, and **fails if anything changed**.
- Spawns a clean child process to assert `POSTING_ENABLED is False` by default.
- `--stage` must be a **new** label; an existing stage directory is refused (evidence is never overwritten).

**Expected result:** `315 passed` — 0 failed, 0 errors, 0 skipped, direct exit 0.
There is one pre-existing Starlette/anyio `DeprecationWarning`; it is expected and not a failure.

### Targeted subset

```bash
"C:/Users/emadg/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" scripts/verify_invoice_cycle.py --stage UNIQUE_LABEL -- tests/test_invoice_cycle_safety.py -k 'concurrent or mixed_vat or late_failure' -q --tb=short
```

### Scoped lint (changed files only)

```bash
"C:/Users/emadg/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" -m ruff check app tests
```

Whole-repo currently reports **145 inherited findings** (baseline was 169) — no repository-wide clean claim. The 17 changed files are clean. Never use `--exit-zero` as proof.

### Verify the committed snapshot

```bash
git log --oneline -3
git show d233893 --stat
git rev-parse HEAD^{tree}          # expect 158b71380626ec777c58b8f46d8c14200cc19518
git status --short                 # expect only ?? graphify-out/
```

### Evidence locations

| Artifact | Path |
|---|---|
| Final acceptance | `docs/evidence/invoice-cycle/finalization-20261018/FINAL_ACCEPTANCE.md` |
| Review intake + findings disposition | `.../finalization-20261018/REVIEW_INTAKE.md` |
| Reviewer verdict (verbatim) | `.../finalization-20261018/reviewer-original.json` |
| Source integration/readback | `.../finalization-20261018/SOURCE_INTEGRATION.json` |
| Frozen 17-file diff + hashes | `docs/evidence/invoice-cycle/review-input/manifest.json` |
| Native run records (315 each) | `.../resume-candidate-20261018/`, `.../integrated-full-20261018/` |
| Recovery scope proposal | `.../finalization-20261018/UNBLOCKING.md` |
| GitHub gate | `.../finalization-20261018/GITHUB_GATE.md` |
| Commit receipt (private) | `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/invoice-cycle-20261017/commit-receipt-20261018.json` |

---

## 5. Remaining tasks, priorities and unresolved risks

### Priority 1 — Next implementation work

1. **Continue the approved vertical-slice sequence.** Modules remaining per the A→H build order: complete B Master Data, then remaining C Sales (warehouse transfers, returns, statements, sales targets), D Inventory (stock cover/overstock/low-stock), E Finance (treasury/cash+bank, expenses/revenue, P&L + Balance Sheet reporting, payroll lightweight, private/owner accounts isolation).
2. **Resolve production gates before any activation** (none are approved): printed-invoice rounding/tax exception policy; accounting-period/timezone policy for reversals; deployment least privilege; backup/hosting/UAT.

### Priority 2 — Owner approval gates (blocked, do not act)

3. **Default `medical_dms` schema recovery** — see §6. Requires explicit owner approval.
4. **GitHub private publication** — see §7. Blocked.

### Unresolved risks

| Risk | Impact | Status |
|---|---|---|
| Printed-invoice rounding / VAT exception policy unverified | Wrong tax on printed invoices | Open production gate |
| Payroll formula UNVERIFIED (header-structure test ≠ formula validation) | Wrong payroll | Open |
| `medical_dms` schema drift | Local dev DB unusable for this branch | Quarantined |
| Embedded dev DB credentials + Excel-derived samples in Git history | Secret/confidential-data exposure on push | Publication blocked |
| Historical worker isolation/evidence-loss violation | Cannot certify whole-task data isolation | Recorded, not retroactively certified |
| 145 inherited repo-wide Ruff findings | Code-quality debt | Known, unchanged |
| `graphify-out/` untracked | None | Pre-existing; leave alone |

---

## 6. Local `medical_dms` database recovery — requirements and restrictions

**Current state (read-only assessment, `DEFAULT_DB_INCIDENT.json`):** the local PostgreSQL database `medical_dms` is stamped `0010_invoice_collections` but **lacks** the final migration's AR link columns and terminal-history guard. An earlier rejected worker ran its outdated 0010 there despite isolation instructions. This is **migration stamp/content drift** — `alembic upgrade head` is a no-op against the existing stamp and does **not** repair it.

**Restrictions now in force:**
- **Do not run this branch, its tests, migrations or the app against `medical_dms`.**
- No downgrade, stamp reset, `DROP SCHEMA`, table/database drop, or business-row mutation.
- The original migration's downgrade contains `DROP SCHEMA finance` — it is **not** a safe recovery path.
- Treat all existing tables and backups as **potentially real confidential company data**.

**What recovery would require (proposal only — NOT authorized, NOT started):**
1. A **forward-only** reconciliation migration (`alembic/versions/0011_*.py`, not created) that adds the missing columns/constraints/indexes/triggers and advances to a new repair revision — never restamping old schema as correct.
2. A **private encrypted backup** taken first: `medical_dms.before.dump` + schema/count/hash manifest, stored **outside the repository** (a plain custom dump is not encrypted).
3. A controlled maintenance window; DDL takes locks on real company tables.
4. Reconciliation set: `finance.ar_entry.{receipt_id,reverses_entry_id}`; `inventory.stock_movement.{invoice_line_id,reverses_movement_id}`; constraints `uq_invoice_receipt_scope`, `ck_invoice_posting_actor`, `fk_receipt_invoice_scope`, `ck_receipt_no`, `ck_receipt_finite`; indexes `uq_ar_invoice_sale`, `uq_ar_receipt_type`, `uq_stock_invoice_line_sale`; functions/triggers `guard_terminal_invoice`, `guard_terminal_line`, `guard_append_only`, `guard_receipt_history`.
5. Historical posted rows lacking links are **not** auto-backfilled; reversal must keep rejecting unverifiable history.

Full detail: `docs/evidence/invoice-cycle/finalization-20261018/UNBLOCKING.md`.

**Not affected:** running tests on fresh disposable `dms_cycle_test_*` databases requires no approval and is the normal workflow.

---

## 7. GitHub security issue — credentials and Excel-derived samples

A read-only Gitleaks 8.30.1 scan covered **20 reachable commits / 223 unique historical blobs / 439 unique content inputs** (HEAD `f85b8f9` at scan time) plus the milestone payload.

**Findings — first push is BLOCKED:**

1. **Embedded development database credentials** in tracked source and history: `alembic.ini:89` and `app/db.py:14` (plus frozen copies under `docs/evidence/`). Values are not reproduced here. Do not publish them merely because a repository would be private.
2. **Excel-derived confidential samples are tracked in Git:** `docs/inventory.json` contains nonempty `first_data_rows_sample` / `header_rows_sample` / column samples; `docs/analysis.json` retains extraction samples. Source provenance: `tools/inventory_excel.py:145-146`, `tools/analyze_inventory.py:51-52`. **Ignoring `*.xlsx` is not sufficient** — the derived JSON must be sanitized or excluded.
3. No **binary** workbook payload was found in Git content (the `.xlsx` files are gitignored).
4. Scanner noise: of 320 finding records, **316 were quoted SHA-256 metadata hashes** (false positives), 4 were URI-bearing content findings. Findings are not 320 secrets.
5. `gh` CLI is **not authenticated**; no remote exists; nothing was pushed or created.

**Required before any push (needs owner approval):**
- Prefer a **sanitized code-only export** to a new private repository over rewriting this preserved history.
- Exclude/redact confidential data samples, raw operational traces and embedded credentials.
- Review remaining source-derived docs and `docs/evidence/` Markdown.
- Re-scan the **exact outgoing refs/commit** and verify private visibility, then authenticate `gh`.
- No credential rotation or history rewrite is authorized yet.

Sanitized audit artifacts (private): `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/github-prepush-20261018/`.

---

## 8. Safe instructions for continuing development in OpenCode

### Setup

```bash
cd "C:/Desktop/Huge system"
git status                 # expect clean except ?? graphify-out/
git log --oneline -3       # expect HEAD 898e034
```

Ensure a local PostgreSQL instance is reachable (the runner needs CREATE/DROP). Do **not** point anything at `medical_dms`.

### Every task

1. Read `AGENTS.md`, then `docs/DECISION_LOG.md` for the area you touch, then the relevant `docs/*_SLICE.md`.
2. Create a branch off `milestone/invoice-collection-20261017` for new work, e.g. `git checkout -b feature/<name>`. Never work on `master`.
3. Write the failing test first, then the smallest implementation.
4. Run the approved runner with a **new** stage label.
5. Keep `POSTING_ENABLED` OFF; never edit protected files (§HARD SAFETY RULES).
6. Append evidence under `docs/evidence/<area>/`; never rewrite existing evidence.
7. Commit on your branch. Do not merge to `master`, do not push.

### Before claiming anything is done

- The runner exits 0 with the expected case count.
- Source/workbook/config hashes are unchanged (the runner asserts this itself).
- The exact files you claim exist at their exact paths — read them back.
- No protected file was modified (`git diff --name-only` against your base).

### Stop and ask the owner when

- A change would enable production posting, touch `medical_dms`, modify a source workbook, or require a push.
- A business rule is not provable from the workbooks or spec.
- You are tempted to merge into `master`.

---

## Transfer summary

- **Project:** ElsebaeyPharma ERP (Medical Company System) — FastAPI + PostgreSQL + vanilla PWA.
- **Directory OpenCode must open:** `C:\Desktop\Huge system`
- **Branch/HEAD:** `milestone/invoice-collection-20261017` @ `898e034` (milestone `d233893`, base `master` `f85b8f9`).
- **State:** Invoice → Stock → AR → Collections local slice complete, independently reviewed (PASS), 315/315 tests passing on disposable databases, committed and unmerged.
- **Production posting:** OFF.
- **Not done:** master merge, GitHub push, `medical_dms` recovery, production activation — all require explicit owner approval.
- **Hash note:** the milestone commit is `d233893`, **not** `d235893` (which does not exist).
