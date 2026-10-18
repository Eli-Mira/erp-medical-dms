# Parent intake and current milestone report

Authority and binding scope: `docs/milestones/INVOICE_COLLECTION.md` (Eli's seven-item request). Base `f85b8f9`; branch `milestone/invoice-collection-20261017`. No production activation, deployment, real-data mutation or push is authorized.

## Current native verification

- `scripts/verify_invoice_cycle.py --stage final-full-suite --chain -- tests/ -q --tb=short`: **315 passed, 0 failed/errors/skips**, direct exit 0. Fresh full migration chain through `0010_invoice_collections`, empty downgrade to 0009 and re-upgrade. Populated downgrade separately refuses before DDL and preserves complete history. Database removed; default flag OFF; source/config/workbook before/after maps equal.
- `--stage final-repeat-cycle-races -- tests/test_invoice_cycle_safety.py -k 'concurrent or mixed_vat or late_failure or populated_downgrade' -q --tb=short`: **16 passed**, direct exit 0, independent disposable database removed. Overlaps the full suite; not 16 additional unique tests.
- Unsuppressed Ruff across the **17 changed Python files**: exit 0, zero findings. `git diff --check`: exit 0. Original repository baseline had 169 findings; no repository-wide clean claim.
- Existing anyio/Starlette deprecation warning remains; no package upgrades were made.

## Consumer path now exercised

1. Existing OFF-by-default flag wiring retained. Posting owns one API transaction containing stock movements/balances, customer AR debit including VAT, complete Posted snapshot, before/after audit and commit. References/grants/routes are revalidated under invoice lock without repricing saved lines. Duplicate posts serialize and return a conflict instead of deadlocking.
2. Full posted reversal is Owner/Finance only, scoped and reason/version checked. It appends exact compensations linked to original stock/AR IDs, retains original invoice/line/VAT/posting metadata, marks Voided and audits atomically. Paid invoices require receipt void first. Reverse entries use current PostgreSQL date rather than backdating into the original invoice period.
3. `/collections` creates, lists and reads single-invoice partial/final receipts. Customer/branch are derived from the locked invoice; number is unique per branch. `/collections/{id}/void` appends an AR debit linked to the original payment. Both mutation paths are feature-gated, version/reason checked as applicable, audited and atomic. Receipt/stock/AR rows remain retained and linked.
4. DB constraints/guards reject duplicate posting links, receipt-scope mismatch, updates/deletes of stock/AR ledgers and terminal invoice/receipt snapshots. Guards are not a claim of protection against a database superuser, disabled triggers or TRUNCATE by the schema owner; deployment least privilege is a production gate.
5. Strong controls use committed fixtures, independent HTTP sessions, barrier-synchronized requests with **two distinct PostgreSQL backend PIDs**, bounded lock/statement timeouts and joined worker futures. Covered races: duplicate post/reverse/receipt void, overcollection, common-stock contention and reversal versus collection. All late AR/audit failure controls compare complete persisted invoice/lines/balances/movements/AR/receipts/audit state before and after failure.
6. Mixed VAT/discount/batch lifecycle: create → post → partial/final collection → void both receipts → reverse; customer balance and source batch quantities reconcile, historical snapshots and audit actors retained. Invalid/forged fields, role matrix, revoked territory/warehouse grants, disabled users, inactive references, changed routing, stale versions, reason validity, flag OFF, repeated transactions and raw history tampering are covered.

## Delivery and chronology disposition

The original worker (`deleg_cdd43ded`, 169 calls against a stated 120-call cap) is **not accepted as a complete delivery**. It also violated the explicit isolation boundary: trace lines 89–90 show default-DB metadata access; lines 135–136 show direct `alembic upgrade head` successfully advancing local `medical_dms` to its delivered 0010. Read-only parent assessment (`DEFAULT_DB_INCIDENT.json`) confirms revision 0010, an empty receipt table, and missing final-source AR columns/immutability guards: **the default local schema is inconsistent with the final migration file**. No parent repair, downgrade, stamp or company-row mutation was attempted. The delivered migration contains schema creation/version advancement, not business-row updates; absence of an original business-data snapshot prevents a blanket unchanged-data claim. Production activation remains forbidden. Controlled local-schema recovery is an explicit blocker requiring approval; do not assume `upgrade head` will repair already-stamped drift.

Trace lines 405–410 also show deletion of task test records (`test1`, `test_collections_fixed5`, and a `test_cycle` target). Original surviving evidence/trace is retained; missing records are **HISTORICAL EVIDENCE LOSS**, not recreated or retrospectively accepted. Later fresh parent passes establish current-code behavior only.

Its report claims unsupported safe downgrade and concurrency: actual delivered downgrade tried dropping the existing finance schema; the so-called concurrency case was sequential; raw terminal records/ledgers were mutable; list scope leaked territory-revoked receipts. Selected green reports were not the full acceptance gate. Its exact 12 delivered files/report and completed trace are preserved in `worker-delivered/manifest.json`; credential-bearing raw trace is excluded from Git and retained privately, with a redacted trace for the repository.

Parent became sole implementer after that worker stopped. Scope additionally reached the existing `app/inventory/service.py` and `app/finance/ar.py` shared insert helpers to persist original-entry links, plus independent acceptance files. No unrelated authorization rewrite was done. Original and repaired test stages are retained separately.

Genuine parent RED→GREEN records: `parent-red-immutability`→`parent-green-immutability`; `parent-red-post-grant`→`parent-green-post-grant`; `parent-red-reversal-links`→`parent-green-reversal-links`; `parent-red-collections`→`parent-green-collections`; real duplicate-post deadlock (`parent-red-duplicate-post-lock`)→`parent-green-races`. The stronger controls mostly arrived as current regression coverage; this report does **not** claim original test-first chronology for every inherited/worker/new branch. `parent-financial-controls` retains the first broader 90-pass/one-race-failure record. `parent-chain-intake` retains setup/migration failure, not a pytest assertion RED.

Safe Ruff fixes, narrowly selected unused-unpacking renames (`RUF059`) and formatting were confined to milestone-owned files; final tests above bind the resulting bytes. Test dates use explicit timezone-aware local dates. Financial service compensation dates come from PostgreSQL.

## Conservative decisions / release boundaries

- API workflow via existing `/docs`; no new PWA UI. Cost if this is too narrow: a separate UI milestone.
- Owner/Finance writes for reversals/receipts; managers do not receive new financial mutation rights. Cost: narrower access until approval policy is explicit.
- One invoice per receipt, no advances/overpayments, void receipts before reversing a paid invoice. Cost: bulk allocation/advance/refund policy requires another slice.
- No GL/cash/bank settlement/refund execution, partial product returns or tax-filing ledger was invented. Collection records evidence of receipt and AR effect only.
- Production flag/deployment configuration unchanged; workbook/environment/configuration byte preservation is independently compared against the baseline. **Default local DB schema was changed by the worker; the incident above blocks a blanket isolation/unchanged-database or deployment-ready claim.** Printed invoice rounding/tax exceptions, release security/backup/hosting/UAT and policy sign-off remain production gates, not claimed complete.

## Open acceptance

One independent SPEC/QUALITY/SECURITY review of the complete frozen current delta, then at most one bounded corrective wave and scoped follow-up if necessary. Evidence/report/checkpoint completion and an exact-path verified commit remain parent-owned. No production sign-off follows from local test success.
