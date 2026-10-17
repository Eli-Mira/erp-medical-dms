# Inventory authorization — verification and review intake

Date: 2026-10-17. Base: `893a0d997cd2e1ddc3f80bb1a77f7640433aacde`.
Scope: repair explicit branch-based inventory authorization only; report the next sales-routing prerequisite. This is not production release approval.

## Result

Inventory authorization is implemented and covered by real PostgreSQL regression controls. Explicit `platform.user_branch` grants resolve active **owned warehouse IDs**. Territory or fulfillment-route assignments do not grant whole-warehouse access. Branch-scoped managers are read-only for manual inventory operations. Invoice-backed movement details additionally require the invoice's branch and territory assignments and matching source warehouse. Missing grants, foreign filters, revoked assignments and disabled accounts are denied.

The previous completion report for `893a0d9` was incorrect. The old suite passed without exercising assigned-manager warehouse IDs or the resulting write/detail over-grants. This repair does not repeat the already completed stock/AR implementation.

## Native evidence

| Gate | Artifact | Actual result |
|---|---|---|
| Wrong warehouse-ID regression | `red-branch-resolution/run.json` | 2 desired assertions failed; direct pytest exit 1 |
| Minimal ID-resolution repair | `green-branch-resolution/run.json` | 2 passed |
| Assigned-manager write over-grant | `red-branch-write-denial/run.json` | 4 failed, 2 passed; actual 201 vs required 403 |
| Manual-write denial repair | `green-branch-write-denial/run.json` | 6 passed |
| Shared-warehouse territory leakage | `red-shared-territory-isolation/run.json` | 2 failed, 6 passed; extra foreign invoice source IDs |
| Territory/branch detail filter repair | `green-shared-territory-isolation/run.json` | 8 passed |
| Foreign-warehouse response contract | `red-foreign-warehouse-hiding/run.json` | 2 failed, 12 passed; actual 403 vs required 404 |
| Foreign-warehouse hiding repair | `green-foreign-warehouse-hiding/run.json` | 14 passed |
| Final application snapshot | `final-verified/{run.json,pytest.xml,pytest.log}` | **182 passed**, 0 failures/errors/skips; direct exit 0 |
| Final fresh database | `final-fresh-db-run/{run.json,pytest.xml,pytest.log}` | **182 passed**, 0 failures/errors/skips; direct exit 0; 1 existing Starlette/httpx deprecation warning |
| Scoped Ruff | `lint.json`, `lint.txt` | Exit 0 for inventory application, new tests and migration 0008. The old inventory test file retains 16 baseline lint findings; no new findings there. |

The final suite adds **20** authorization cases to the previous 162-case suite. Later negative/role/revocation/UUID-collision controls include green-first regression coverage; do not label all 20 as original RED-first tests. Earlier successful runs (`final-run`, `fresh-db-run`) precede the final deterministic-date/format cleanup and are retained but are not the final source snapshot.

Each final raw log/XML hash was revalidated by the parent; each recorded source/test/workbook digest matches current bytes. All 7 workbook hashes were unchanged. The latest intake is **saved-artifact revalidation**, not another native pytest execution.

Disposable chain: empty DB `0001 → 0008_branch_warehouse`; downgrade to `0007_ar_ledger`; upgrade back to `0008`; full 182-case suite; DROP and absence check. Both disposable databases were removed. The developer database was already at 0008 and was not downgraded. The executed driver is preserved as `verify_inventory_db.py`; its output directory is intentionally create-exclusive.

## Review and method disposition

`review-input/manifest.json` binds six changed destination files, six unchanged context files, 11 complete normalized-LF hunks and raw-byte hashes. The parent replayed all hunks against the exact HEAD blobs to the normalized destinations before dispatch. Diff SHA256:

`08b9f5f4c3a0209d35148b941000ae946b5a69ff74405285b507632e4ec46500`

The independent reviewer read the changed destination bodies, found no blocking application defect and returned positive spec/quality/evidence judgments (`REVIEW_ORIGINAL.json`). Its unchanged returned verdict and actual live trace (`reviewer-trace.txt`) are preserved.

**Do not accept that verdict as a compliant read-only method certification.** The parent counted **55 tool entries against a 25-call budget**. The trace also contains temporary patch/replay writes despite a no-write brief, avoidable failed replay attempts, and hashing of context files without demonstrated full-body inspection of all of them. The `evidence_pass`/`checked_files` declarations exceed those demonstrated methods. Successful hashes or native tests cannot retroactively make those methods compliant.

Parent intake: retain the supported semantic observations and negative code findings; reject the unqualified method-certification claim. Parent independently re-read the relevant auth/sales/migration contracts and revalidated the final raw evidence, full current input bindings and case statuses. No application/test/review-input bytes changed during the review. This is a terminal **historical review-method deviation**, not a new runtime defect, not a claim the child obeyed its brief, and not a reason for recursive review/retest. Current inventory implementation acceptance rests on the recorded native controls and parent validation; no whole-system or process-compliance certification is claimed.

## Posting and next task

`app/sales/router.py` and its posting route are unchanged: an authorized request still receives **409**, and shared-territory tests explicitly exercise that refusal before invoking the existing atomic function directly inside rollback-isolated tests. No flag was added or activated; no live permissions or production records were assigned.

**Next uncompleted task:** source-warehouse compatibility for invoices. `app/sales/router.py::_prepare` and `fk_invoice_warehouse_branch` still require source warehouse owner branch = sales branch. Wire/test the Dakahlia/Sharqia/Gharbia routing relationships without merging territory identity or granting warehouse access. Then implement the previously requested default-OFF posting flag and tests. Do not activate it without explicit approval.

GitHub: no remote was configured, no repository was published, and no push was made. The broader secrets/credentials/history/confidential Excel-data sweep remains a separate prerequisite to private publication. Production reconciliations, policy conflicts, backups, UAT and posted reversal remain outside this repair.
