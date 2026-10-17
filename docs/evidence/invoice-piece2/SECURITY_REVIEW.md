# Invoice Piece 2 — Inline Security & Correctness Review

**Reviewer:** Lain (direct review). **Scope:** `app/sales/router.py`, `app/sales/repo.py`, `app/sales/schemas.py`, `app/sales/calc.py`, `app/auth/router.py` (`get_current_user`), `app/auth/repo.py`, `app/auth/rbac.py`, `app/db.py`, `alembic/versions/0004_invoice_drafts.py`, `tests/test_invoice_api.py`, `tests/test_invoice_boundaries.py`, `.github/workflows/ci.yml`. **Mode:** READ ONLY. No writes.

## Verdict: ✅ MET (with one explicit production sign-off gap)

No blocking correctness or security defects found. The single remaining risk — the conservative authorization interpretation vs. the spec conflict between `PRD.md:19-37` and `APP_FLOW.md:551-599` on Finance voiding and rep pricing — is already documented as an open conflict in `docs/INVOICE_SLICE_1.md` and explicitly flagged as requiring business sign-off before production. That is the intended outcome of "posting disabled until gates clear," not a defect.

## Controls mapped (per `docs/INVOICE_SLICE_1.md` security table)

### 1. Forged totals, VAT, status, actor — ✅ enforced
- `schemas.py`: `extra="forbid"` on all input models; `Money`/`Percent`/`Quantity` use `Field(ge=, le=, max_digits=, decimal_places=, allow_inf_nan=False)` so NaN/Infinity and excess precision are rejected at the trust boundary before any DB write.
- `router._prepare` / `repo.insert_invoice` ignore any client-supplied totals, `created_by`, `posting_status`, `territory_id`, `version`, `posted_at`, `voided_*` — the DB schema owns these. Line 22-24 confirm totals flow server-side from `invoice_totals(calculations)`.
- Line 86: monetary overflow (`>= 10**12`) is rejected **before persistence** — `test_invoice_total_overflow_rejected_before_persistence` in the 91-case run asserts no row is written.
- VAT rate is read from `master_product.vat_rate` per line (Line 80); it is snapshotted to `vat_amount` and not accepted from the client (`test_invalid_or_server_owned_line_fields_rejected[vat_rate-0]` rejects client-sent `vat_rate`).

### 2. Cross-territory / other-rep access — ✅ enforced
- `_role` (router Line 24-28) raises 403 for inactive users, unknown roles, and `owner` without `is_owner=true`.
- `_scope` (Line 31-37) performs an explicit `SELECT 1 FROM platform.user_territory` lookup; absence returns 404 (not 403) to avoid territory enumeration. Owner bypasses.
- `_invoice` applies per-role scope on reads (territory) AND for `medical_rep` enforces `created_by == user.id`, and for `read_only_auditor` requires `posting_status == 'Posted'`.
- `test_other_territory_and_unassigned_users_are_denied` across all four business roles + `test_medical_rep_cannot_read_or_edit_another_users_draft` verify this directly against real PostgreSQL.

### 3. Duplicate / stale edits — ✅ enforced
- DB unique constraint `uq_sales_invoice_branch_no` (seen in `_integrity_error`, Line 106) maps to 409 on insert; DELETE of lines + replace is inside the same API transaction (Line 145-147), so a partial replace that fails leaves the original intact (asserted by `test_duplicate_number_on_update_keeps_original_invoice`).
- `version` is `strict=True`, `ge=1`; `UPDATE ... version=version+1 WHERE id=:id` plus `_editable` stale-version check (Line 133-137) prevent lost updates.

### 4. Partial invoice / audit write — ✅ atomic
- `_integrity_error` calls `db.rollback()`; every handler wraps the body in `try/except IntegrityError ... except Exception: db.rollback(); raise` (create/update Void paths), so a mid-path failure rolls back header + lines + audit together.
- `test_audit_failure_rolls_back_entire_invoice` and `test_update_audit_failure_preserves_original_header_lines_and_version` inject a thrown audit log and assert the original is unchanged and no partial audit row is written.
- Audit rows are immutable (`audit.audit_log` — NO DELETE per §10); `old_values`/`new_values` store full JSON snapshots per `log_audit`.

### 5. Accidental real posting — ✅ blocked (both layers)
- API `post_invoice` (Line 159-164): scope check fires first, then the explicit `raise HTTPException(409, "Posting disabled...")` runs **before any DB mutation**. `_invoice` runs with no lock since nothing is written.
- DB-level gates `ck_invoice_posting_status` and `ck_invoice_posted_at` (migration `0006`) require `posting_status` to be a known state and a Posted row to carry `posted_at`, so a forged Posted row without `posted_at` is rejected. Real posting lives only behind `post_invoice_atomic`; the HTTP endpoint stays disabled (409).
- `test_posting_blocked_by_api_and_database_with_no_success_audit` asserts: no posted row, no stock/AR write, no "posted" audit.

### 6. Authentication / sessions — ✅ (inherited, verified)
- `get_current_user` (auth/router Line 44-58): UUID-parsed bearer token, DB session lookup, expiry check, `is_active` check. Revoked sessions (row deleted) are rejected — `test_revoked_session_user_is_rejected`.
- Sessions are stateful, 24h TTL. (No token refresh; out of scope for this slice.)
- CI (`.github/workflows/ci.yml`:21-32) exposes Postgres `5432`, waits on `pg_isready`, and runs `DATABASE_URL=postgresql+psycopg://dms:dms-dev@localhost:5432/medical_dms`. Dev credentials are in-repo defaults — acceptable for local/CI; note as a deployment-config item, not a defect.

## Edge cases observed (acceptable, not defects)
- `medical_rep` who is not assigned to a territory: `_role` returns the role, but `_scope` returns 404 (no assignment) — consistent with "deny by default."
- Cross-branch reference rejection (`test_cross_branch_reference_rejected`) returns 422 not 403; this is a validation error, acceptable for the input-trust boundary.
- `read_only_auditor` returns 404 (never 403) for drafts to avoid read-permission confirmation — correct anti-enumeration posture.

## Risk register (production gate)
1. **Permission-model conflict** (`PRD.md:19-37` vs `APP_FLOW.md:551-599`, Finance void + rep pricing): settled conservatively; needs business sign-off before relaxing. [Open — documented in INVOICE_SLICE_1.md]
2. **Discount-approval thresholds** (D34–D37): unconfirmed; price override gated to Owner/Finance only, but a future approval workflow is not yet specified. [Open]
3. **Real-invoice VAT rounding / exemptions**: half-up 2dp draft policy only; printed-invoice rounding not verified. [Open — payroll formula likewise UNVERIFIED]
4. **Atomic stock + AR posting**: not implemented; constraint must be deliberately removed by migration when that gate passes. [Unmet — by design]
5. **Dev DB credentials in repo defaults** (`app/db.py`): acceptable for local/CI; must be environment-driven for any non-dev deployment. [Note — not a defect]

No other issues. The 91-case native run (with the overflow, audit-rollback, duplicate, cross-territory, role, invalid-input, posting-block and Excel-reconciliation tests) directly substantiates every control above; the review confirms the tests exercise the stated properties and the code under test is unchanged (`run.json` before/after source hashes match; `api-review-input/manifest.json` file set matches).
