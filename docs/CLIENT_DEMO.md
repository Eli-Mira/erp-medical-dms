# Client Prototype — Demo Guide

Everything in this demo is **synthetic placeholder data**: every code is prefixed
`DEMO-`, every Arabic name contains `تجريبي`, and nothing is imported from any
real workbook, customer list, or financial record. The server always runs with
`POSTING_ENABLED=false`.

## What you will see

- Arabic **RTL** PWA at `http://127.0.0.1:8018/app/` with a demo ribbon at the
  top and five working views: الرئيسية (dashboard), فاتورة جديدة (new draft
  invoice), المخزون (inventory), أرصدة العملاء (customer balances), التحصيلات
  (collections).
- A dashboard whose every number comes from the server (outstanding AR, stock
  units, active products, total collected).
- The general-purpose **English/Arabic toggle** in the header (ت toggles layout
  direction as well).
- An isolated database `medical_demo` on the same local dev Postgres. The app
  database (`medical_dms`) is **never touched** by this demo, and the demo
  database can be dropped and rebuilt at any time by re-running step 1.

## Startup (two commands, PowerShell)

```powershell
# 1) Build / rebuild the synthetic demo database (drops + recreates + seeds it)
cd "C:\Desktop\Huge system"
uv run --with-requirements requirements.txt python scripts/make_demo.py

# 2) Start the prototype server (copy the exact line printed by step 1)
$env:DATABASE_URL="postgresql+psycopg://dms:dms-dev@localhost:5432/medical_demo"; $env:POSTING_ENABLED="false"; $env:DEMO_MODE="1"; uv run --with-requirements requirements.txt uvicorn app.main:app --host 127.0.0.1 --port 8018
```

Then open **http://127.0.0.1:8018/app/** and sign in.

## Showing it on a phone (same Wi-Fi)

The default command binds `127.0.0.1` (PC only). For a phone on the same
network allow it in Windows Firewall and bind to all interfaces:

```powershell
$env:DATABASE_URL="postgresql+psycopg://dms:dms-dev@localhost:5432/medical_demo"; $env:POSTING_ENABLED="false"; $env:DEMO_MODE="1"; uv run --with-requirements requirements.txt uvicorn app.main:app --host 0.0.0.0 --port 8018
```

Find the PC's LAN address (`ipconfig` → IPv4, e.g. `192.168.1.20`), then on the
phone (Chrome/Android or Safari/iOS) open **http://192.168.1.20:8018/app/** and
use **Add to Home screen** — the app series PWA, RTL, standalone window.

## Device support & verification status

- **PC (Chrome/Edge/Firefox)**: fully verified — the complete walkthrough was
  driven in a real desktop browser session in this development run.
- **Phone/tablet layout**: verified with Google Lighthouse's mobile emulation —
  scores **Accessibility 1.0, Best Practices 1.0, SEO 1.0 (zero failures)**;
  responsive CSS collapses to a single column below 720 px. Not yet physically
  touched on a real handset in-house — do one 2-minute phone walkthrough (log
  in, open two views, save one draft) before presenting to the client to
  confirm feel.

## Demo credentials (all synthetic)

| Username       | Role           | Password    | Scope                                    |
| -------------- | -------------- | ----------- | ---------------------------------------- |
| `demo_owner`   | owner          | `Demo-2026` | everything (global)                      |
| `demo_rep`     | medical_rep    | `Demo-2026` | sees only فرع تجريبي أ + منطقة تجريبية أ |
| `demo_finance` | finance        | `Demo-2026` | finance-level reads (global)             |

The demo-mode flag (`DEMO_MODE=1`) also shows this hint box on the login screen.

## Five-minute walkthrough (as demo_owner)

1. **Sign in** — `demo_owner` / `Demo-2026`. The amber ribbon "عرض تجريبي — كل
   البيانات المُعروضة وهمية بالكامل" appears at the top.
2. **لوحة العرض (dashboard)** — read the four stat cards. Verified values after
   seeding: outstanding AR `3300.70`, stock units `2690`, active products `4`,
   collected `800.00`. Below: the two most recent synthetic receipts.
3. **فاتورة بيع جديدة** (the primary button under "ابدأ من هنا") —
   pick عميل تجريبي ١ → the branch fills in automatically (فرع تجريبي أ) →
   pick المخزن التجريبي الرئيسي → add a line: منتج تجريبي أ, quantity `5`,
   discount `10%`. The tape shows the estimate (56.25 for this example) and
   states that **the server is authoritative**.
4. **حفظ كمسودة** — the server recomputes and returns the authoritative totals
   (for this example: before `62.50`, discount `6.25`, net `49.34`, VAT `6.91`,
   grand `56.25`). The screen says plainly: the draft **does not** touch stock
   or receivables.
5. **Honest posting gate** — press ترحيل الفاتورة. The server refuses it
   (HTTP 409, "Posting disabled until stock and receivables can be updated
   atomically"), the badge stays مبدئية. Nothing is simulated.
6. **المخزون** — quantities are unchanged (a draft never reduces stock):
   6 warehouse/product rows totalling `2690` units, all labelled تجريبي.
7. **أرصدة العملاء** — balances are unchanged by drafts: `1910.00` /
   `750.00` / `640.70` / `0.00`, each the sum of its synthetic ledger entries.
8. **التحصيلات** — two pre-seeded receipts (`DEMO-RCPT-001` cash `500.00`,
   `DEMO-RCPT-002` check `300.00`), linked to their synthetic invoices. The
   safety gate means the app will not create new receipts in this demo.
9. Optional: switch to **English** with the header toggle (layout flips to
   LTR), then back to Arabic. Sign out, sign in as `demo_rep` to see branch
   scoping in action (only فرع تجريبي أ data appears).

## What the demo does *not* claim

- Saving a draft is shown as **paperwork only** — no stock movement, no AR
  entry, no rollup change until a successful posting, and posting is never
  simulated (the server's 409 gate is part of the demo).
- Collections and balances shown are **pre-loaded synthetic opening data**
  inserted directly into the demo database (labelled on screen), not output of
  a live posting cycle.

## Known limitations

- One demo Postgres instance assumed locally (the dev container); the seed
  script refuses to run against a non-local host.
- Unbatched stock only (batch/expiry views are a later module); invoice lines
  do not show batch selection.
- No invoice list/search screen yet; the collections view resolves invoice
  numbers by requesting each linked invoice individually.
- Pagination is not implemented on any `/master/*` or `/ar/balances` read
  (whole active list per current scope).
- Bounded demo dataset (2 branches, 2 territories, 2 warehouses, 4 synthetic
  products, 4 synthetic customers, 3 synthetic posted invoices, 2 receipts).
- The browser service worker caches the shell (`medsys-shell-v3`); if assets
  ever look stale, bump `CACHE` in `web/sw.js` or clear site data.
