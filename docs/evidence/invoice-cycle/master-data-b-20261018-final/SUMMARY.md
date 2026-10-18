# B Master Data slice — verified evidence (2026-10-18)

## What this is

The three master-data references that the planning docs confirm but **no
migration had ever created** — suppliers, a minimal chart of accounts, and the
doctor/KOL list — plus the read-only role-gated API they need. Structure only:
no accounting policy was invented, no accounts were seeded, no real supplier,
doctor, or financial records were loaded, and the UOM table stays gated
(D13/D20). Production posting remains disabled.

## Delivered

- **Migration `0011_master_data_b`** (`down_revision = 0010_invoice_collections`):
  - `master_data.master_supplier` — PRD B-02 / G-01, D11. Planning column
    `status` is realized as the implemented `is_active` soft-delete flag
    (DATABASE_SCHEMA §13, D39a). Unique `code`, whitespace-only codes rejected.
  - `finance.coa_account` — PRD B-12 / E-05, D14. `account_type` constrained to
    `asset`/`liability`/`equity`/`revenue`/`expense`; self-parent rejected;
    `ix_coa_parent`. **No accounts or codes are seeded** — the workbook shows a
    P&L/BS structure, not a coded chart of accounts, so seeding one would invent
    accounting policy (D29, D39b).
  - `marketing.marketing_kol` — PRD B-13, D22 (`حسابات خاصه.xlsx::Sheet1`).
    Specialty stays inline (no specialty master table exists); `branch_id` FK to
    `master_data.master_branch`; `ix_kol_branch`.
  - `downgrade()` drops only the three tables it created. The empty `marketing`
    schema is left in place: `CREATE SCHEMA IF NOT EXISTS` keeps re-upgrade
    idempotent, and dropping a schema this migration does not own could destroy
    objects created out-of-band.
  - **No UOM table** (D13/D20), no CRUD, no write endpoint, no import.

- **Read-only lookups** (`app/master/router.py`, schemas in
  `app/master/schemas.py`), all parameter-bound, all capped at `limit ≤ 500`:
  - `GET /master/suppliers` — `owner`/`finance`/`read_only_auditor`.
  - `GET /master/accounts` — same roles; optional `account_type` filter
    (invalid type → 422 via `Literal`).
  - `GET /master/doctors` — `owner`/`sales_manager`/`district_manager`/
    `medical_rep`/`read_only_auditor`; non-global callers are limited to their
    `platform.user_branch` grants, and an explicit `branch_id` narrows within
    the grant — it can never widen it. A doctor with no branch is never offered
    to a branch-scoped caller. Territory, branch and warehouse grants stay
    distinct (D39d).
  - `q` is a literal substring search: `%`, `_` and `\` are escaped, so user
    input cannot act as a LIKE wildcard or an unterminated escape. Applied
    consistently to `/master/products` as well.
  - `_require(user, allowed)` centralizes the role/`is_active`/`is_owner`
    checks; `_role()` keeps the pre-existing endpoints on the same path.
  - **Preserved:** the existing `/master/branches|warehouses|customers|products`
    contract is unchanged (the internal `PRODUCT_LIMIT_*` constants were renamed
    to `LIMIT_DEFAULT`/`LIMIT_MAX` with identical behavior; nothing else
    imported them).

- **Docs updated to the implemented contract** (D29 makes the docs the column
  contract): `DATABASE_SCHEMA.md` §3 (`master_supplier` → `is_active`,
  `created_at`), §6 (`finance_coa_account` + `created_at`, type domain, no
  seeds), §12 (per-reference read matrix replaces the vague "global read");
  `DECISION_LOG.md` **D39a–e**; `PROGRESS_CHECKLIST.md`.

## Independent review

An adversarial, read-only review subagent inspected the migration, router,
schemas, tests and docs against PRD B-02/B-12/B-13/G-01, DATABASE_SCHEMA
§3/§6/§8/§12/§13, and D11/D13/D22/D29/D34, and reported findings with
`file:line`. It found **no authorization hole** (fake-owner elevation, missing
`is_active`, branch-scope leaks, explicit-`branch_id` bypass, SQL injection and
unbounded result sets all cleared) and confirmed that the absence of UOM tables,
write endpoints and seeded rows is itself the requirement. Confirmed defects
were fixed:

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 1 | medium | Role gates for the three new endpoints were not traceable to an authoritative doc, and §12 said "master data: global read" | Documented the per-reference read matrix in `DATABASE_SCHEMA.md` §12; recorded as D39d |
| 2 | low | `downgrade()` ran `DROP SCHEMA IF EXISTS marketing` | Schema no longer dropped (table-only downgrade) |
| 3 | low | Column drift vs docs (`status`→`is_active`, unlisted `created_at`) | §3/§6 updated to the implemented column set |
| 4 | low | `ck_*_code` used `btrim`, so a tab/newline code passed; untested | Constraint now `code ~ '[^[:space:]]'`; whitespace-code assertions added for both tables |
| 5 | low | `q` not escaped for LIKE metacharacters (search semantics only; scope clause always ANDed) | `_like()` escapes `\`, `%`, `_`; new literal-search test |

Test-adequacy gaps the reviewer flagged were closed rather than argued away:
`district_manager` and `read_only_auditor` are now exercised on the new
endpoints (with the managers' doctor lists asserted **empty**, not merely 200),
an explicit out-of-grant `branch_id` request is asserted empty, and the database
invariants now also cover unique COA/KOL codes, whitespace-only codes, and
self-parent on **UPDATE**.

## Verification

Approved disposable-DB runner only; `medical_dms` was never touched.

```
uv run --with-requirements requirements.txt python scripts/verify_invoice_cycle.py \
  --stage master-data-b-20261018-final --chain -- tests/ -q --tb=short
```

- **345 passed, 0 failed, 0 errors, 0 skipped** (baseline 334 + 11 new;
  `counts` in `run.json`). Full-suite time 79.4 s.
- `--chain`: migration `0011` upgraded → downgraded one revision → re-upgraded
  on the disposable DB with no error.
- `"unchanged": true` — every source file, protected file (`app/db.py`,
  `app/config.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`,
  `.env.dev`) and the 7 read-only workbooks hash-match after the run.
- `"default_off_exit": 0` — `POSTING_ENABLED` is still off by default.
- `"removed": true` — the disposable `dms_cycle_test_*` database was dropped.
- TDD trail: `master-data-b-red` (10 failed / 0 passed, `UndefinedTable`),
  `master-data-b-20261018` (regression caught — see below),
  `master-data-b-check` / `master-data-b-fix-check` (scoped debug stages),
  `master-data-b-20261018-final` (this stage).

### Regression found and fixed

The first full-suite run (`master-data-b-20261018`) failed one previously
verified test: `test_invoice_cycle_safety.py::test_populated_downgrade_refuses_without_losing_history`.
Its final assertion hard-coded `version_num == "0010_invoice_collections"`, but
a downgrade to `0009` now traverses the new head `0011` first, so the aborted
transaction leaves the version at `0011_master_data_b`. The guard behavior
itself was intact (`RuntimeError: history must be preserved` was still raised
and `state(life) == before` still held). Fixed by comparing against the head
captured before the downgrade instead of a hard-coded revision, so the next
migration cannot break it again. That run is kept as evidence of the catch.

## Files changed

| File | Change |
|------|--------|
| `alembic/versions/0011_master_data_b.py` | new migration (3 tables + indexes + checks; table-only downgrade) |
| `app/master/schemas.py` | `SupplierOut`, `AccountOut`, `DoctorOut` |
| `app/master/router.py` | three read endpoints, `_require`, `_like`, `LIMIT_*` |
| `tests/test_master_data_b.py` | new — 11 tests |
| `tests/conftest.py` | `test_master_data_b` added to the disposable-DB guard |
| `tests/test_invoice_cycle_safety.py` | head-agnostic assertion (regression fix) |
| `docs/DATABASE_SCHEMA.md`, `docs/DECISION_LOG.md`, `docs/PROGRESS_CHECKLIST.md` | contract + decision record |

No merge, no push, no deploy, no posting activation.

## Open business-policy questions

1. **Chart of accounts content** — which account codes/names to load, and
   whether the COA is company-wide or branch-scoped. Structure exists; content
   is unseeded because seeding it would invent accounting policy (D29/D39b).
2. **Supplier numbering** — no numbering scheme is documented. Implementations
   must not assume one (`code` is unique but freely assigned).
3. **Doctor `المنطقة`/`التخصص` mapping** — Sheet1 carries area and specialty as
   free text; no confirmed mapping to branches/territories or a specialty list
   exists, so both stayed as raw attributes.
4. **`admin` role** — D34 lists Admin, but no master-data read set includes it
   (pre-existing convention, not introduced here). Confirm intent.
5. **CRUD + Excel import** — Module B's acceptance criterion mentions
   CRUD-manageable entities and importing the doctor list; this slice delivered
   structure + reads only. Writes/import need the same owner sign-off as any
   policy-bearing change.

## Remaining risks

- Endpoint lists are `limit`-capped but have no offset/cursor — consistent with
  the pre-existing `/master/*` endpoints, and the tables are small by
  construction (doctors ≈100 rows per D22 evidence). Revisit if the KOL list
  grows or an import lands.
- `downgrade()` will hard-drop the three tables if run on a populated database;
  it is a development-only operation and, consistent with migrations 0001–0010,
  no data guard is added. Dependents fail safe (no `CASCADE`).
- The three tables are empty in every environment. Nothing consumes them yet —
  the PWA does not render suppliers/COA/doctors.
- GitHub publication is still blocked (embedded dev credentials, tracked
  Excel-derived samples, no remote); the branch exists locally only.

## Next recommended task

Browser-based validation of the Invoice UI against these APIs with synthetic
data (owner-approved), before any further schema work.
