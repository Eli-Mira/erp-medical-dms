# Invoice Slice 1 — Piece 2: draft API

**Updated:** 2026-10-17. **Scope:** local draft-invoice development only. Production posting and posted-invoice reversal are deliberately unavailable.

## Delivery and evidence

- [x] Create/read/full-replace draft API and draft void: `app/sales/{router,repo,schemas}.py`.
- [x] Real PostgreSQL integration controls: `tests/test_invoice_api.py` and `tests/test_invoice_boundaries.py`.
- [x] Forward migration `0004_invoice_drafts`: territory assignments, warehouse/batch references, revision/actor fields and database posting guard. Applied on the dev database.
- [x] Final native run: **91 passed, 0 failed, 0 skipped**, direct exit 0. `docs/evidence/invoice-piece2/final-run/{pytest.log,pytest.xml,run.json}` binds source/test/workbook hashes before and after execution.
- [x] Clean-database migration chain `0001 → 0004` and then-existing suite: **81 passed**, direct exit 0. `docs/evidence/invoice-piece2/fresh-db-run/`. The UUID-named disposable database was removed and absence verified; the dev database was not dropped. Ten additional boundary controls passed separately and in the final 91-case run.
- [ ] Independent API security/correctness review: dispatched against `api-review-input/manifest.json`; pending intake. Two earlier spec/calculation workers timed out and are not accepted deliveries.

The one native warning is a FastAPI/Starlette TestClient HTTPX deprecation. An optional broad inherited Ruff profile initially reported 97 findings (style, unused test bindings and Decimal-constructor suggestions); that is not a clean broad-lint gate. A separately scoped core check (`ruff check --isolated --select E4,E7,E9,F` on the invoice source/tests) passed after replacing a test-fixture import with pytest plugin registration. Hosted GitHub Actions, production Docker packaging, deployment, load/concurrent-request stress, and production release approval were not exercised.

## API contract

Bearer authentication uses existing `/auth/login` sessions. Disabled users are rejected even if their session has not expired. Decimal values are serialized as strings.

| Method and path | Behavior |
|---|---|
| `POST /invoices` | Create draft and lines; calculate server-side totals and product VAT snapshot; audit actor and full new snapshot; 201. |
| `GET /invoices/{uuid}` | Read permitted immutable response snapshot; no recalculation on reads. |
| `PUT /invoices/{uuid}` | Replace a **Draft** only; full draft input plus required integer `version`; row lock + version check; audit old/new; 200. |
| `POST /invoices/{uuid}/void` | Cancel a **Draft** only with `version` and active `reason_id` of category `void`; preserve lines, actor/time/reason and audit; 200. |
| `POST /invoices/{uuid}/post` | Authorized requests return **409 Posting disabled**. No posted state, stock/AR writes or false success audit is produced. |

Invalid input/reference: 422; duplicate `(branch_id, invoice_no)` or stale draft version: 409; unauthenticated/inactive user: 401; denied responsibility: 403; inaccessible/missing invoice or territory: 404. Draft update is PUT, not PATCH. There is no delete endpoint.

Create input: `invoice_no`, `branch_id`, `warehouse_id`, `customer_id`, `invoice_date`, optional `notes`, and 1–500 `lines`. Each line: `product_id`, positive quantity (up to 3 decimal places), optional `batch_id`, optional VAT-inclusive `unit_price` (otherwise product base price), `discount_pct` in 0–100 (up to 2 decimal places), optional notes. Server-owned totals, VAT rate, posting state and actor fields cannot be supplied. Unknown fields, NaN/infinity, excess precision and monetary overflow are rejected.

Customer and warehouse must be active and match the invoice branch; the customer must have a territory. A supplied batch must match the line's product and the source warehouse, with expiry not earlier than invoice date. Batch assignment can be omitted in a draft; final allocation/tracking requirements remain part of the later posting gate.

## Authorization: implemented conservative interpretation

D34 confirms role names and responsibility/assigned-territory restrictions, not every candidate cell of the older permission tables. `PRD.md:19–37` and `APP_FLOW.md:551–599` conflict on Finance voiding and rep pricing. The implementation takes the narrower restriction; this is **not** a claim that every detailed permission below received separate business sign-off.

| Role code | Draft access |
|---|---|
| `owner` **and** `is_owner=true` | All territories; create/read/update/void drafts. A role label alone cannot grant Owner authority. |
| `finance` | Explicitly assigned territories; create/read/update; price override; no void. |
| `sales_manager` | Explicitly assigned territories; create/read/update/void. |
| `district_manager` | Explicitly assigned territories; create/read/update; no void. |
| `medical_rep` | Explicitly assigned territories; create/read/update **own** invoices; no price override or void. |
| `admin`, `warehouse_staff` | No access to this financial invoice API. No automatic administrator financial privilege. |
| `read_only_auditor` | Assigned-territory **Posted** invoices only; never drafts or writes. Since posting is disabled, no posted invoice is available to this role in this slice. |

Assignments use `platform.user_territory`; absence means deny, not global access. Existing legacy roles (`user`, `accountant`, `manager`, `sales`) are not silently elevated or remapped. User/catalog/assignment administration endpoints are outside this piece; test data is isolated and rolled back. Catalog base prices and VAT configuration are DB-side references, not client-controlled tax overrides. Price overrides are limited to Owner/Finance; discount approval thresholds remain unconfirmed and must be settled before real posting.

## Financial behavior and boundaries

- Existing draft arithmetic is retained: `net_price = unit_price × (1 − discount_pct/100)` rounded half-up to 2 decimals; then `line_total = quantity × net_price`, rounded half-up to 2 decimals. VAT is extracted inclusively as `line_total × rate/(100+rate)`, rounded half-up to 2 decimals. **Printed-invoice rounding stage/mode is not yet independently confirmed.** This is not a migration transform or approved production rounding policy.
- Product-configured VAT (14 for applicable products, 0 only for an explicitly configured example/reference) is snapshotted per line. Changing product VAT does not rewrite existing invoices. A full draft replacement intentionally recalculates using current catalog configuration. No blanket medical exemption is assumed or inferred.
- Header grand total/VAT sum stored line values. Discount is the realized residual `total_before_discount − grand_total`, avoiding an inconsistent independently rounded discount sum. `total_net + vat_amount = grand_total` and the discount identity are DB checks.
- Money uses PostgreSQL NUMERIC and Python Decimal; quantity is NUMERIC(12,3). Inputs exceeding the current precision contract are rejected, never silently truncated for import.

## Excel evidence: exact scope, not whole-migration approval

`tests/test_invoice_excel.py` invokes the **real application calculator** on complete numeric transaction rows in:

| Workbook and sheet | Sheet dimension (rows) | Numeric rows compared |
|---|---:|---:|
| `مبيعات 6 اكتوبر 2026.xlsx` / `مخزن الزهراء اكتوبر` | 3916 | 59 |
| `مبيعات الدقهليه 2026.xlsx` / `مخزن السحيلى المنزلة` | 4440 | 74 |

**133 rows**: application net price and line total agree with independently read cached Excel cells with differences strictly below EGP 0.01. No row is skipped because its output disagrees and no mismatch quota is allowed. The data includes 11 historical non-positive-quantity rows in the second sheet; arithmetic comparison does not authorize negative-quantity invoices or implement returns. Other rows are filtered by their numeric vs header/summary/blank layout; unexpected nonnumeric business cells elsewhere require further discovery, not assumed whole-workbook validation.

The original nine source checks remain separate; some are bounded samples. The full-size check proves source identity/dimensions, not complete business coverage. The rollup test now also checks zero-sales rows and exactly binds the known `الرئيسية!C16:E16` residual **16103.56** plus its propagation into row 102. Its cause is **unverified**; a passing anomaly baseline does not repair the source or approve migration. All seven source files still match the frozen hashes; nothing was written to them.

A timed-out worker's partial test permitted skipping large differences with EGP 0.50 tolerance. That method was rejected and replaced with this explicitly bounded, strict check. The worker's partial invoice-total invariant fix was independently inspected and passed in the parent runs; no completed delegated/TDD chronology is claimed for that partial delivery.

**Not verified:** actual printed-invoice VAT breakdown/rounding, all product exceptions, all transaction sheets, a complete imported AR balance, or payroll formulas. Payroll remains **UNVERIFIED**; checking its headers does not validate a salary formula. No payroll code was implemented.

## Security evidence and production gate

This piece maps the five security-document categories—Security, Auth, Data Security, Threat Model and Security Checklist—into the controls above. The full system security-document/workflow and release gates are not being declared complete.

| Threat/control | Implemented evidence | Limit |
|---|---|---|
| Forged totals, VAT, status or actor | Pydantic extra-field rejection, Decimal bounds, server calculation; invalid-input tests | No production tax/exemption sign-off |
| Cross-territory/other-rep access | Role + assignment + creator checks on reads and writes; allowed/denied integration tests | Conservative policy conflicts need business review before production |
| Duplicate/stale edits | DB branch-number unique constraint, UPDATE row locks, required version; conflict tests | No concurrency/load stress claim |
| Partial invoice/audit write | Header + lines + audit committed together; injected audit-failure rollback controls on create/update | No stock/AR implementation yet |
| Accidental real posting | Unconditional API block (409); DB gates `ck_invoice_posting_status` + `ck_invoice_posted_at` (a Posted row must carry `posted_at`) | Posting is enabled only by wiring `post_invoice_atomic` behind the endpoint after sign-off — see `docs/AR_SLICE.md` |

Before production: implement and verify atomic stock + receivables posting/reversal; validate the actual invoice rounding/tax exceptions; settle permission/approval conflicts; complete release/security/backup/hosting inspection and UAT. Local draft development does not grant production release authority.

## Run locally (existing PostgreSQL must be available)

From `C:/Desktop/Huge system`:

```bash
uv run --with-requirements requirements.txt alembic upgrade head
uv run --with-requirements requirements.txt python -m pytest tests/ -v
uv run --with-requirements requirements.txt uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use the existing FastAPI `/docs` interface for this API. No invoice screen or unrelated PWA redesign was added; `web/` is unchanged. The migration CLI currently uses `alembic.ini`'s configured URL; align it with the app's `DATABASE_URL` when targeting any other environment. The fresh-DB proof explicitly supplied its isolated URL through Alembic Config.
