# Beta-3 candidate: browser failure history and push/release gates

The owner separates private progress/backup publication (`feature/erp-beta`,
`beta-3-candidate`) from buyer release (`beta-3`). A candidate is not a release.
Release requires the complete exact-tree suite with zero failures and no waivers.
Candidate publication also requires every non-browser control green, an exact-tree
secret scan, one Alembic head, default posting HTTP 409, and remote hash readback.

## Saved-invoice late reply: retained route count was 2, expected 1

- Control: `tests/test_beta3_financial_session.py::test_late_saved_invoice_reply_does_not_replace_login`.
- Preserved full-suite failure on tree `f3486652f91ae836fd4a33f2b2932133de790f87`:
  1114 passed / 1 failed / 0 errors / 0 skipped. Its exact-count precondition failed
  before the late-response/privacy assertions. This is not evidence of a privacy leak.
- The owner-requested bounded triage executed 20/20 isolated passes on pre-repair
  tree `7d0a800df13e9be22ed379d415e02ecfb8c2c8a5` and 20/20 isolated passes on
  `f3486652f91ae836fd4a33f2b2932133de790f87`. Every observed retained count was 1.
  Sanitized request/initiator journals are retained with the native case records.
- The 40 requested target repetitions under concurrent chunk load did **not** run.
  The coordinator observed the wrong chunk path (missing the `beta3-merged-`
  prefix), then closed admission. Its independent load generator passed 72/72;
  those are different controls and do not count as target-under-load evidence.
- Classification: unreproduced in isolation; missing load comparison is parked
  because of the bounded coordinator failure. It is neither a proven product
  regression nor proven load-only flakiness. No two-request sequence was captured;
  none is invented. Another causal run needs a newly bounded authorization.
- The class-wide readiness sweep replaces handler flags/request-observed shortcuts
  with one bounded actual-count helper. **The original `assert len(held) == 1`,
  authorized-response checks, logout/account boundaries and client-consumption
  barriers remain unchanged.** It does not deduplicate, discard or suppress routes.
  No application behavior changes were made for this unreproduced failure.
- Final exact-tree outcomes are recorded separately in the source-bound native
  receipts. This historical failure is not silently skipped or waived. If it
  recurs, candidate parking must name the new case/result; release remains closed.

Private local receipts:
`C:/Projects/ERP-Orchestration/ElsebaeyPharma/evidence/owner-decisions-20261103/triage/`
(`ISOLATION_INTAKE.json`, `TIMEBOX_DISPOSITION.json`, and its explicit timing/path
correction `TIMEBOX_CORRECTION.json`). Original failed runs remain preserved.

## Prior I1 report-readiness failure

`test_i1_late_report_cannot_cross_accounts` previously raised `IndexError` when
reading `held[0]` from an empty retained list. The owner approved defensive readiness hardening
without claiming proven causation. The retained f348 comparison passed 20/20 per
six variants (120/120); the class sweep now uses the same shared helper. Original
privacy assertions and stale-body consumption barriers are preserved, not replaced
by a request event, sleep or network-idle heuristic.
