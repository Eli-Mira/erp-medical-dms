# Invoice → Stock → AR → Collection milestone

Authority: Eli's 2026-10-17 seven-item request. Base `f85b8f9`; branch `milestone/invoice-collection-20261017`. This is a local API vertical slice, not production activation or a UI redesign.

## Global constraints

- Do not enable production posting or modify real company data.
- Keep `POSTING_ENABLED` default OFF. Do not edit deployment/configuration/environment files or old evidence.
- Run all DB tests/migrations only through `scripts/verify_invoice_cycle.py`: fresh task-owned `dms_cycle_test_*` databases, explicit Alembic/application URL, synthetic fixtures, verified removal.
- Preserve accepted inventory authorization and sales routing; fulfillment compatibility never confers inventory access.
- Preserve Decimal/VAT-inclusive snapshot calculations. No invented tax/rounding policy, no GL/AP/payroll/returns redesign, no dependency additions.
- One implementation owner; parent owns test runner, evidence intake/checkpoint and commits. No subagents, Git mutation, installs, daemons, publication or real-DB access by implementer.

## Scope and conservative decisions

1. Preserve existing flag wiring to `post_invoice_atomic`; fix missing endpoint transaction/response/audit/error handling, rather than rebuilding it. Successful HTTP posting commits Stock + AR + Posted status + audit together. Duplicate/non-Draft/insufficient-stock conflicts return 409 and change nothing. Always return complete invoice snapshots including lines.
2. Retain existing posting roles and territory controls; revalidate active references, explicit warehouse grants and route compatibility at posting time (revocation after draft creation must not be bypassed). Owner is global; Finance retains existing territory requirements for invoice operations. Forbidden/missing resources must not leak across scope.
3. Add safe full posted-invoice reversal, distinct from draft void, behind the same OFF-by-default gate. Owner/Finance only for this slice. Require current version and active void reason; retain original header/lines/VAT/posting metadata. Append exact stock and AR counter-entries linked to originals; flip status to Voided with actor/time/reason. Prevent repeat reversal/reposting and terminal-row edits/deletes. All changes plus audit atomic.
4. Collections/Payments: invoice-linked receipts (one invoice per receipt, any number of partial receipts), exact positive two-decimal amount, receipt number, date, cash/check/transfer method and optional note. Derive customer and branch from locked Posted invoice, never from client-supplied financial authority. Owner/Finance writes; scoped reads reuse invoice/AR responsibility rules. Database-backed unique receipt number per branch, server-owned status/actor/totals. POST/GET/list plus receipt void with reason/version: append AR counter-entry, retain original receipt, never delete history. All writes behind the same feature gate.
5. Serialize posting/reversal/collection/payment-void on the invoice row. Reject overpayment (including concurrent attempts) and payment against Draft/Voided invoices. Refuse invoice reversal while active receipts remain; user can void receipts first, preserving full audit trail. No cash/GL ledger exists yet; receipt records a collection, not bank settlement/refund execution.

Ruling: API workflow via existing `/docs`, no new UI — matches current vertical-slice delivery and avoids unrequested design work; cost if wrong is a later UI task.
Ruling: Owner/Finance reversal and payment writes; managers do not gain new financial mutation rights — conservative while approval policy remains unresolved; cost if wrong is narrower access until explicitly approved.
Ruling: Single-invoice receipts, reject overpayment, void receipts before reversing paid invoices — no invented allocation/refund policy; cost if wrong is that bulk allocations/advances/refunds require a later extension.

## Task 1 — Implement and exercise the complete API lifecycle (sole worker)

Read app sales/finance/inventory/auth helpers, migrations and tests before editing. Callers and FK/trigger dependencies belong to scope. Use test-driven-development: one meaningful RED → minimal GREEN behavior at a time, record inherited green-first behavior honestly. Never revert accepted code to manufacture RED.

Owned files: `app/sales/{router,service,schemas}.py`; `app/finance/{ar,router,schemas,payments,payment_router}.py` (new payment modules only if helpful); `app/main.py` only if registering a payment router; `alembic/versions/0010_invoice_collections.py`; `tests/test_posting_flag.py`, `tests/conftest.py`, new `tests/test_invoice_cycle.py`, `tests/test_collections.py`, `tests/test_invoice_reversal.py`. Other files only after parent steering.

Required regression groups:
- Real HTTP posting persists across an independent DB connection; stock deduction, correct customer AR debit, VAT-inclusive total and snapshot unchanged. Mixed VAT rates/discounts/batches where applicable.
- Missing/forbidden/disabled user; role, territory and warehouse grants/revocation; invalid route; flag OFF and default OFF. Production env/config not edited.
- Duplicate posting, concurrent posting, stock race, insufficient stock after an earlier line succeeded, late AR failure, audit failure: prove whole rollback with fresh reads, no orphan movements/AR/audit/status change.
- Reversal exact stock+AR compensation with retained original VAT/header/line snapshots and metadata; reason/version/role/scope/flag checks; duplicate/concurrent reverse; audit/late failure rollback; paid-invoice denial; no direct posted amount/line/ledger mutation/delete. Add appropriate narrow DB constraints/immutability guards without a new authorization system.
- Payment partial/final amounts; balances and receipt reads; duplicate number across same branch; invalid/malformed amounts/method/references and forged fields; Draft/Voided invoice denial; overpayment/concurrent payments; role/scope/read leakage; payment void and duplicate void; late/audit failure rollback.
- Full Invoice → Stock → AR → partial/final Collection → payment void → invoice reversal cycle, assert persisted amounts/audits/original rows and repeat transaction rejection. Include real independent transactions for concurrency, not a shared savepoint session.
- Preserve existing tests; adapt obsolete expected uncaught exceptions to the now-safe HTTP conflict contract, not weaker assertions. Baseline lint is not clean; do not use `--exit-zero` as proof of lint success.

Deliver source/tests plus immutable raw RED/GREEN logs under `docs/evidence/invoice-cycle/` via the runner, and a concise report `docs/evidence/invoice-cycle/IMPLEMENTER.md` with exact test commands/cases, chronology, changes, concerns. Do not commit. Maximum 120 tool calls; if blocked, report exact state rather than looping.

## Task 2 — Parent verification and independent review

Parent reads exact delta and reports, runs covering and complete suites on fresh isolated DBs, up/down/up migration chain (including data-preserving rollback or explicit safe refusal with populated records), real concurrency controls and unchanged configuration/workbook hashes. Capture raw logs, JUnit case identities/status buckets, source hashes/argv/exit codes, database absence and default-OFF verification. Run actual Ruff without `--exit-zero`, report baseline vs task findings accurately. One independent scoped spec/quality/security review of complete task-relative diff; maximum one correction wave and one scoped follow-up if needed. Do not reopen previous inventory reviews.

## Task 3 — Evidence and verified commit

Update current checklist and session continuity with tested snapshot, review disposition and explicit remaining production gates. Commit only verified milestone-owned changes/evidence; no source workbook, secret, environment file, unrelated reformat or push.

## Preflight interface/conflict scan

| Producers/consumers | Shared file/interface | Finding |
|---|---|---|
| Posting / reversal | sales service/router, stock/AR, invoice lock | Same transaction owner; use exact compensations, no independent commits in services. |
| Reversal / payments | invoice lock, receipt status, AR entries | Refuse paid-invoice reversal until receipt void; same lock order avoids overcollection and reversal races. |
| Payments / AR | finance schemas/entries | New linked receipts coexist with legacy manual AR entries; do not silently rewrite prior ledger behavior. |
| Implementer / parent | tests/runner/evidence | Parent sole runner owner, worker sole application/test owner; runner binds each test snapshot and removes only DB it created. |
| Task 1 internal | tests, source, migration | Work matches required assertions; no production toggle or real migration. |
| Task 2 internal | unchanged final source | Parent tests then one independent review; one bounded correction wave if needed. |
| Task 3 internal | report/commit | Completion requires all acceptance groups; unresolved gates remain visible. |
