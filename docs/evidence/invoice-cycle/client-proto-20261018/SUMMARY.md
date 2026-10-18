# Evidence — client prototype stage `client-proto-20261018`

Date: 2026-10-18 · Branch: `feature/client-prototype` (cut from `de41f42`,
which includes the `e413f68` invoice UI — ancestry verified before branching).

## 1. Scope delivered

- `scripts/make_demo.py` — creates/reseeds the isolated local DB
  `medical_demo` (synthetic-only, `DEMO-` prefixed codes, names labelled
  تجريبي; seeded via `app.sales.calc` so all totals satisfy the DB's internal
  consistency CHECKs; refuses non-local hosts; never touches `medical_dms`).
- Read-only views (Arabic-first, RTL) + demo dashboard in the PWA:
  الرئيسية، فاتورة جديدة، المخزون، أرصدة العملاء، التحصيلات — all fed by the
  existing APIs; unfinished features are not exposed (nav lists only working
  views).
- `POSTING_ENABLED=false` enforced in the demo runbook; draft saving is
  presented as paperwork only; posting is never simulated.
- `app/config.py` `DEMO_MODE` flag (same `_env_flag` pattern) + `GET /meta`
  in `app/main.py` — presentation-only (login demo hint), relaxes nothing.
- Service worker cache bumped `medsys-shell-v2 → v3`.

## 2. Seed verification (script self-check, zero constraint failures)

invoices 3 (Posted) · stock_balances 6 · ar_entries 7 · receipts 2 ·
collections_sum 800.00 · totals_ok 0 · ar_sums_ok 0.
Synthetic balances: DEMO-C01 1910.00, DEMO-C02 640.70, DEMO-C03 750.00,
DEMO-C04 0. Values cross-checked by hand: 1500 + 910 − 500 = 1910 ✓,
940.70 − 300 = 640.70 ✓, 250 + 500 = 750 ✓.

## 3. Regression (approved runner)

```
{"database": "dms_cycle_test_f32aca17a13044c6a4e587e5d61b2b9a", "exit_code": 0,
 "counts": {"passed": 345, "failed": 0, "error": 0, "skipped": 0},
 "unchanged": true, "removed": true, "default_off_exit": 0}
```
345 passed in 80.46 s — equals the post-B-slice baseline (334 + 11). Chain
up→down→up OK; sources/protected files unchanged; disposable DB dropped.

## 4. Actual browser flow (Chromium via built-in browser control)

`POSTING_ENABLED=false`, `DEMO_MODE=1`, running against `medical_demo`.

| # | Step (real clicks/inputs in the page) | Verified result |
| - | ------------------------------------- | --------------- |
| 1 | Open `/app/` | `dir=rtl`, title نظام الشركة الطبية, demo hint shown on login card (`/meta` demo_mode true) |
| 2 | Sign in `demo_owner` | Header shows demo_owner/owner; nav = 5 buttons; amber banner visible |
| 3 | Dashboard loads | statAR 3300.70 · stock 2690 · products 4 · collected 800.00 · 2 recent receipts — all server values |
| 4 | New invoice: customer DEMO-C01 → branch auto-fills فرع تجريبي أ → warehouse DEMO-WH1 → line: منتج تجريبي أ ×5 @10% | preview 62.50 / 6.25 / 49.34 / 6.91 / 56.25 |
| 5 | حفظ كمسودة | `201 Created`; draft view shows **server totals identical** (client sends no totals); scope note "المسودة لا تخصم من المخزون" rendered; status badge مبدئية |
| 6 | Press ترحيل الفاتورة | honest server refusal rendered: "Posting disabled until stock and receivables can be updated atomically" (409); status stays مبدئية |
| 7 | Overview after the draft | stock still 6 rows / 2690 units; balances still 1910.00 / 750.00 / 640.70 / 0.00; collections still 2 / 800.00 — **draft touched nothing** |
| 8 | Language toggle | AR→EN flips `dir=ltr`, nav becomes Home, ribbon English; back to AR restores and home re-renders |
| 9 | Server log (`/app` history) | two 422s (stale-shell defect below), then 201, then 409, reads 200 — matches steps above |

Server process then stopped cleanly (`demo server stopped`).

### Caught & fixed during browser testing

- **Latent defect since `e413f68`**: `newDraft()` `form.reset()` cleared the
  boot-filled date/number, so any fresh draft saved with an empty date and got
  422 `invoice_date: input is too short`. Fix: `newDraft()` now restores
  `todayLocal()` + generated invoice number after reset (also makes the
  dashboard→invoice path work). Step 5 above is the proof of the fixed flow.

### Evidence limitations

- `browser.screenshot` could not capture (desktop window not visible in this
  environment); interaction evidence above is DOM-level assertions on the real
  Chromium page + the server access log. Visual review by the client should be
  part of the walkthrough in `docs/CLIENT_DEMO.md`.
- No viewport-size matrix was tested (only default window + RTL/LTR toggle).

## 5. Safety posture

- Same disposable-DB runner discipline as all prior stages (new unique label,
  dropped DB, `unchanged: true`).
- `medical_dms` untouched (scripts connect only to `postgres` maintenance DB
  and `medical_demo`).
- No `.env*` file modified; `DEMO_MODE` only set as a process env in the demo
  runbook; `POSTING_ENABLED` remains false everywhere in this demo.
- Synthetic data only; no real company/doctor/supplier/financial record and no
  Excel dumps anywhere in the demo path.
