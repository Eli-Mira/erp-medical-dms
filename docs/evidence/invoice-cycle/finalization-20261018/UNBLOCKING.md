# ElsebaeyPharma ERP — review unblock and recovery boundary

## Held candidate and exact NO_VERDICT diagnosis

There is **no held commit object**. HEAD is the pre-milestone base `f85b8f964b5b4b54139cbdf614e37a91bd6a45a4` on `milestone/invoice-collection-20261017`; the 17-file implementation/test/runner delta is still uncommitted. Its complete 22-hunk diff is `review.delta.txt`, SHA-256 `37e099d4c503dde8774d121a96dd0b3be00cf4567f6379c445016814200ba378`. Per-file source/diff bindings are in `../review-input/manifest.json`; freshly checked current-source/native-proof bindings are in `preflight.json`.

The prior reviewer `deleg_cc032a64` did **not** log a timeout. Its completed transcript records:

```text
21:17:00 result    last actual diff-read results returned successfully
21:19:09 think     <dots_function_call>
21:19:10 assistant literal <dots_function_call><invoke name="read_file">… markup
21:19:10 final     status=completed
21:19:10 final     end status=completed exit_reason=completed
```

The assistant emitted proposed tool calls as final **text**, not executed tool calls or the required SPEC/QUALITY/SECURITY verdict. `REVIEW.json` was never created; the full trace contains no recoverable complete verdict. Only three of the 17 diff files had actually been read at that point. Therefore the exact acceptance failure is **missing/unparseable final review delivery with incomplete diff coverage**, not an observed application failure, security PASS or proven timeout. The upstream reason the model chose that final text is **not established by this trace**; inventing a timeout/transport diagnosis would be unsupported.

Full log: `C:/Users/emadg/AppData/Local/hermes/cache/delegation/live/deleg_cc032a64/task-0.log` (72 lines); durable private copy: `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/invoice-cycle-20261017/reviewer-trace.txt`. Bound disposition: `../REVIEW_DELIVERY_DISPOSITION.json`. Credential-bearing implementation-worker transcripts remain private/ignored; they are not part of the Git payload.

## Review criteria and finite fallback

The user's renewed instruction explicitly authorizes **one** fresh independent READ-ONLY retry, followed by a documented direct READ-ONLY source-diff review if delivery fails. The already-running fresh reviewer `deleg_62e4d5cd` / `sa-0-9ee89615` is that single retry; no duplicate is launched. This supersedes the previous review-delivery hold, not actual failed security checks. Direct fallback, if needed, is labeled parent/direct review, never independent approval.

Required current-code acceptance:

1. Complete 17-file/22-hunk source-diff coverage: existing gate defaults OFF; full posting/reversal/receipt/receipt-void financial, snapshot and audit transaction; permission/reference/route revalidation; exact Decimal/VAT and server-owned inputs.
2. Stock/AR compensation links and retained originals, immutable terminal history, consistent invoice-first locking, genuine independent-session races and complete late-failure rollback assertions.
3. Parameterized SQL, safe trust boundaries, scoped receipt reads, no secrets/company workbooks/transcripts in commit, source/config/workbook preservation, no default/production DB writes.
4. Native cases must bind the exact candidate source; 315-case saved full suite and 16 overlapping repeat controls are already revalidated, not represented as new execution. Fresh full-suite execution is required by the latest instruction before commit. Missing cases, unexpected skips/errors, a real security finding or changed source cannot be hidden behind headline counts.
5. Commit only the accepted source and task-owned evidence; verify staged bytes and final commit against the tested candidate. Production posting, deployment and default DB recovery remain outside approval.

## Isolation recovery — proposal only; NO recovery writes authorized

### Recorded state, not an assumption of empty/safe data

`../DEFAULT_DB_INCIDENT.json` is a prior **read-only** assessment of local PostgreSQL database `medical_dms`: revision stamped `0010_invoice_collections`; `finance.payment_receipt` exists and had zero rows at that assessment; final AR linkage columns and terminal guard were absent. This does **not** establish today's row counts, that other tables are empty, or that the database contains only synthetic data. Treat all existing operational tables and backups as potentially **real confidential company data**.

The original applied 0010 and the final tested 0010 source differ. `upgrade head` alone is a no-op against that existing stamp and is not a repair. The original downgrade contains `DROP SCHEMA finance`; it is not a safe recovery plan. No stamp reset, downgrade, table/schema/database drop, legacy-row backfill or real business-row mutation is approved.

### Exact proposed write set if recovery is separately approved

| Target | Proposed writes and why | Company-data classification |
|---|---|---|
| `C:/Desktop/Huge system/alembic/versions/0011_reconcile_invoice_schema.py` **(not created)** and `tests/test_schema_recovery.py` **(not created)** | Add a forward-only reconciliation migration, rather than rewriting an already-applied stamp; test both archived-old-0010 and fresh-final-0010 paths on disposable synthetic databases. Fail before business changes if required uniqueness/scope/preconditions are not met. | Code and synthetic fixtures only; no real company rows. File creation belongs to recovery scope and is withheld. |
| `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/recovery-<approved-run-id>/` **(not created)** | Private `medical_dms.before.dump`, schema snapshot, metadata/count/hash manifest and execution/rollback records before any recovery DDL. Keep dumps out of the repo; approval must include this backup/storage location. A PostgreSQL custom dump is **not encryption** by itself; protect/encrypt it using the approved backup process. | Full backup may contain real customers, invoices, AR, authentication data and other confidential records. |
| Local PostgreSQL **`medical_dms`**, `finance.ar_entry`, `inventory.stock_movement`, `sales.sales_invoice`, `sales.sales_invoice_line`, `finance.payment_receipt`, functions/indexes/triggers and `alembic_version` | Reconcile missing objects below transactionally, validate integrity, then advance to a new repair revision. DDL takes locks and affects existing company tables even without UPDATE/DELETE of business rows. PostgreSQL writes its own catalogs/storage/WAL; no direct edits to PostgreSQL data-directory files are proposed. | Potentially real company data; **requires explicit approval** and a controlled maintenance/backup window. |
| Fresh task-owned `dms_cycle_test_*` databases and their private test output directories | Reproduce old/new schemas and populated synthetic controls; verify preservation/transaction rollback and remove only those created disposable databases. No cloning/import of company rows is needed. | Synthetic only. The current milestone's existing disposable verification remains authorized; new recovery implementation is withheld. |
| `docs/evidence/invoice-cycle/<approved-recovery-run>/` and continuity notes | Sanitized commands, schema/object inventories, hashes/counts and verified outcomes, not raw customer/business rows or dumps. | Metadata only; today's planning document is not a recovery execution. |

Exact schema reconciliation set derived from the tested migration versus the archived applied migration:

- **Columns/links:** `finance.ar_entry.{receipt_id,reverses_entry_id}`; `inventory.stock_movement.{invoice_line_id,reverses_movement_id}`, with their receipt/invoice-line/self-reversal foreign keys and reversal uniqueness.
- **Invoice/receipt constraints and indexes:** `sales.sales_invoice.{uq_invoice_receipt_scope,ck_invoice_posting_actor}`; `finance.payment_receipt.{fk_receipt_invoice_scope,ck_receipt_no,ck_receipt_finite}`; indexes `finance.uq_ar_invoice_sale`, `finance.uq_ar_receipt_type`, `inventory.uq_stock_invoice_line_sale`. Existing base receipt table/indexes are preserved, not recreated/deleted.
- **Functions/triggers:** `sales.guard_terminal_invoice`, `sales.guard_terminal_line`, `finance.guard_append_only`, `finance.guard_receipt_history`; triggers `guard_terminal_invoice`, `guard_terminal_line`, `guard_ar_history`, `guard_stock_history`, `guard_receipt_history` on their matching tables. Verify actual definitions before selecting any conditional CREATE/ALTER.
- **Migration version:** advance to a newly tested repair revision only after the schema converges. Do not falsely restamp old schema as correct or change historical financial rows to force constraints through.

Existing historical posted rows lacking posting links are **not** automatically backfilled or reinterpreted. Safe reversal must continue to reject unverifiable history; any historical linkage/backfill policy is a separate explicit data decision.

### What does not require recovery approval

Finishing source review, running the approved runner on fresh synthetic databases, preserving test evidence and committing the verified milestone locally do **not** require modifying `medical_dms`. Keep that default DB quarantined from this branch until recovery is approved and verified. No deployment, production activation or push follows from this source commit.

Never write the source Excel workbooks, `.env*`, `app/db.py`, `app/config.py`, Docker/deployment settings or any production database as part of this task. Unrelated `graphify-out/` and other pre-existing work remain untouched.
