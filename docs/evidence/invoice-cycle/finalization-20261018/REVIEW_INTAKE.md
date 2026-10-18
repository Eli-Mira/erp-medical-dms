# Parent intake — current-code review accepted; release not approved

Review: `deleg_62e4d5cd` / `sa-0-9ee89615`; delivered JSON is preserved in `reviewer-original.json`. **Current-code SPEC / QUALITY / SECURITY: PASS.** Coverage matches all 17 files / 22 hunks and complete diff SHA-256 `37e099d4c503dde8774d121a96dd0b3be00cf4567f6379c445016814200ba378`. This is the single fresh retry authorized by the user. It delivered a usable verdict; no further reviewer or direct fallback is needed.

## Independent method intake

Parent inspected the completed trace once: **30 individual invocations**, within the 32-call cap. Only read_file, skill_view and frozen-input search_files were observed. The five diff pages cover lines 1–4719. All **53 bound review inputs** independently rehashed unchanged. No worker terminal/import/execution, DB connection, network, Git mutation or file write was observed. The child explicitly reused parent native/mechanical proof; these were not independent child executions.

Method deviations are retained rather than silently certified: brief and skill loads were batched, not strictly serialized as requested; two guessed context paths did not exist (sales/router.py and app/db.py), then the reviewer found/read the correct frozen sources. No actual protected app/db.py contents were read in those failed lookups. This does not establish blanket perfect method compliance. Actual complete delta coverage and semantic judgment remain supported.

Original private trace SHA-256: `d9a7ab267a9d42c0c68ebcb5f60a1ff272bf5d52f32e4a5162222b5404d9fabb`; path `C:/Users/emadg/AppData/Local/hermes/cache/delegation/live/deleg_62e4d5cd/task-0.log`. Parent retains a durable private copy with the commit receipt.

## Findings disposition — no source changes

| Finding | Disposition and evidence |
|---|---|
| Concurrent reason deactivation | **NOT A DEFECT as described.** Both `app/finance/payment_router.py:192` and `app/sales/router.py:446` explicitly select the active reason `FOR SHARE`; that row lock lasts through commit/rollback and blocks concurrent UPDATE/deactivation. PostgreSQL official Explicit Locking §13.3.2 confirms FOR SHARE conflicts with UPDATE/FOR NO KEY UPDATE. The minor missed this existing control. No unsafe removal/reordering or invented repair was made. |
| Service CURRENT_DATE query | **Intentional / non-blocking.** Compensations use PostgreSQL's current date while retaining original dates. Do not replace this with untrusted caller-supplied financial dates merely to save one query. |
| Service reacquires invoice lock | **Intentional / non-blocking.** The shared service retains its locking contract even when invoked outside an already-locked HTTP route. No need to remove a safety invariant for a redundant query. |
| Fixed identifier interpolation | **NOT a demonstrated injection.** Field names come from fixed internal tuples; values are bound parameters. Adding a redundant runtime allowlist has no identified trust-boundary benefit. |

Reference for the first disposition: official PostgreSQL 18 documentation, `https://www.postgresql.org/docs/18/explicit-locking.html`, Row-Level Locks/FOR SHARE. This was source/documentation review, not an additional native reason-race experiment.

## Editorial corrections (original verdict unchanged)

- Several citations (conftest 1572+, runner 4564+, race 3517+) are concatenated diff line numbers, not the named source files' line numbers. Resolve via the five-page complete diff and function names; no requirement was omitted because of that editorial offset.
- “No subprocess in the 17-file delta” is too broad: the trusted runner intentionally launches pytest and a clean default-OFF child process (`scripts/verify_invoice_cycle.py:134-141,172-182`). Application mutation code does not add arbitrary process execution; the runner uses fixed argv, no shell, and an explicit disposable target. Do not endorse the inaccurate unqualified phrase.
- Customer/branch are derived in the locked-invoice HTTP route; the receipt service receives and revalidates those server-owned values.
- `app/sales/schemas.py` was in fact read as frozen context at the end of the trace, despite the checklist saying “not inspected beyond diff.”
- Existing whole-repository embedded credentials and confidential Excel-derived exports are a **separate blocked publication gate** (`GITHUB_GATE.md`), not cleared by this delta-level security PASS.

## Acceptance progression

Fresh candidate native run `resume-candidate-20261018` is PASS: 315 cases, no failures/errors/skips, exact source/config/Excel bindings preserved, default OFF, task DB removed. Three UUIDv4-only case labels were reconciled transparently; no tests/source were changed.

The unchanged accepted source is eligible for staging on the existing milestone branch, followed by the user's required final full-suite run and exact staged/committed-byte readback. This intake does not claim those later operations already happened.

**Release/deployment remains NOT READY.** Historical worker isolation/evidence-loss rejection remains unchanged; default local `medical_dms` schema recovery requires separate approval; first GitHub push is blocked pending credential/data cleanup and authentication; production activation is forbidden. No additional review is commissioned to improve historical/report prose.
