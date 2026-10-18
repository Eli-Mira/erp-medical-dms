# Requirements coverage — client prototype (`feature/client-prototype`)

Sources: `AGENTS.md`, `docs/PRD.md`, `docs/APP_FLOW.md`, `docs/DESIGN_BRIEF.md`,
`docs/TECHNICAL_REQUIREMENTS.md`, `docs/EXCEL_FEATURE_CATALOG.md`,
`MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`, `docs/DECISION_LOG.md` (D1–D39e),
`docs/AGENT_HANDOFF.md`. Statuses are verified against the running app, not assumed.

Legend: **REAL** = wired to a live backend endpoint · **PROTO** = interactive prototype
preview, clearly labelled "نموذج أولي / Prototype", simulated state kept separate from
server results · **DEFERRED** = postponed by a recorded decision · **MISSING** = honest gap.

## Navigation model
APP_FLOW §1 sidebar tree replicated as-is, grouped by module; role-filtered (§10).
Mobile: hamburger drawer (AF:67) + bottom quick-nav <640px (DESIGN_BRIEF §8).

| Sidebar item (source) | Screen | Status | Backend | Gap notes |
|---|---|---|---|---|
| 🏠 Home | Dashboard | REAL | `/ar/balances`, `/collections`, `/inventory/stock`, `/master/products`, `/ar/entries` | KPI tiles + AR aging strip + recent receipts + quick actions; "sales revenue" KPI derived from ledger entries (no invoice list endpoint) |
| Platform → Auth | Login / session | REAL | `/auth/login, /logout, /me` | 2FA (A1) not implemented |
| Platform → Settings | System settings | PROTO | — | No settings endpoints (A2: fiscal year, VAT config, numbering) |
| Platform → Org Structure | Territories/warehouses | REAL (partial) | `/master/branches`, `/master/warehouses` | Hierarchy tree (A3) is a labelled preview inside the same page |
| Platform → Audit | Audit log | PROTO | — | No audit read endpoint (A7) |
| Platform → Alerts | Alerts center | PROTO | — | Alert types listed per A8 with simulated samples |
| Platform → Import | Excel import | PROTO | — | A9 upload/validate flow mocked |
| Platform → PWA | Install/offline status | REAL | serviceWorker info | Shows live SW/cache/offline state |
| Master → Customers | Customer directory | REAL | `/master/customers` | Read-only; create/edit (B1) not in backend slice |
| Master → Products/Catalog/Pricing | Product catalog | REAL | `/master/products` | Pricing tiers / secondary UOM (B2) absent |
| Master → Reference Sets | Reference sets | PROTO | — | B3 |
| Master → Batches & Expiry | Batches | PROTO | — | No batch model (B4); FEFO described |
| Master → UOM | Units of measure | PROTO | — | B5 |
| Master → Credit Management | Credit limits | PROTO | — | B6; limits not seeded in demo DB |
| Sales → Invoices / Sell-In | Invoice desk | REAL | `POST /invoices`, `GET /invoices/{id}`, `POST …/post` (409 gate) | List/search endpoint MISSING backend-side; PDF print (C1) missing; reopen via locally-registered draft IDs (prototype registry, real data) |
| Sales → Warehouse Routing | Routing rules | PROTO | — | C2 |
| Sales → Transfers | W×W transfers | PROTO | — | C3 |
| Sales → Returns | Returns + credit notes | PROTO | — | C4 |
| Sales → Receivables / Statements | AR balances + ledger card | REAL | `/ar/balances`, `/ar/entries` | Aging 0-30/31-60/61-90/90+ computed from real entries; statement export missing |
| Sales → Sales Targets | Targets vs actual | PROTO | — | C6 |
| Sales → Stock Visits | Mobile visit form | PROTO (interactive) | — | C7 workflow fully mocked: auto sell-through, collection field, saved locally only, labelled |
| Inventory → Stock Ledger | Movements | REAL | `/inventory/movements` | D1 |
| Inventory → Stock Balances | Balances | REAL | `/inventory/stock` | D2 |
| Inventory → Stock Cover | Cover days | PROTO | — | D3 |
| Inventory → Overstock Alerts | Overstock | PROTO | — | D4 |
| Finance → Cash & Bank | Cash/bank | PROTO | — | E1 |
| Finance → Expenses & Revenue | Expenses | PROTO | — | E2 |
| Finance → P&L & Balance Sheet | Statements | PROTO | — | E3 |
| Finance → Payroll | Payroll run | PROTO | — | E4 (formula documented in preview) |
| Finance → Chart of Accounts | COA directory | REAL | `/master/accounts` | Read-only |
| Finance → Collections | Receipts | REAL | `/collections` (void via gate → 409) | New-receipt entry blocked by gate by design |
| Marketing → KOL / Doctor Spend | Doctor directory | REAL (directory) | `/master/doctors` | Spend ledger (F1) is a labelled preview on same page |
| Marketing → Product / Brand Spend | Brand spend | PROTO | — | F2 |
| Marketing → Objectives & KPIs | Campaigns | PROTO | — | F3 |
| Purchasing → Suppliers | Supplier directory | REAL | `/master/suppliers` | Read-only (G1) |
| Purchasing → Material Purchases | PO flow | PROTO | — | G2 |
| Analytics → Cross-Module Dashboard | See Home | REAL (partial) | see Home | H1 drill-downs via links |
| Analytics → Telegram Integration | Alerts channel | PROTO | — | H2; D6 sequencing |
| (WhatsApp) | — | DEFERRED | — | H3 "Future"; D6 — intentionally not in sidebar |

## Cross-cutting requirements (DESIGN_BRIEF)
| Requirement | Status | Evidence |
|---|---|---|
| Light clinical theme, navy #0F2942 / sapphire #2563EB tokens (§2.2, §4.2) | REAL (retheme) | `styles.css` token block = brief §4.2 verbatim |
| Cairo/Inter/JetBrains Mono type stack (§4.1) | REAL | Google Fonts CDN + fallbacks |
| RTL-first, logical properties, `<bdi>`/`dir=ltr` for Latin codes (§3) | REAL | `styles.css` logical props; codes wrapped |
| Currency `ج.م x,xxx.00`, tabular numerals, zero → `—` (§3.3, §6.2) | REAL | `fmt()` + `.num` |
| Status badges draft-amber / posted-emerald / voided-rose (§5.3) | REAL | `.badge.*` tokens |
| Sticky table headers, zebra rows, numeric end-alignment (§6) | REAL | `.grid-table` |
| Mobile <768px tables → stacked cards (§8.2) | REAL | `data-label` card fallback |
| Touch targets ≥44px, bottom action zone (§8.2) | REAL | `@media` sizing rules |
| Ctrl+K global search (§9.2) | REAL | Palette searches nav + customers + products (live) |
| Draft/Posted/Voided lifecycle visible per doc (§5.3, A4) | REAL | Draft view + 409 gate message |
| Print stylesheet (§11) | PROTO | Basic `@media print`; full invoice PDF missing |
| Roles: owner/finance/rep nav scoping (§10) | REAL (client-side) | Role→module map (server enforces grants) |

## Safety posture (unchanged, verified)
- `POSTING_ENABLED=False` — post/receipt-void/return paths surface the server 409; success is never simulated.
- Drafts explicitly state they do not touch stock or receivables; previews never call sales/finance write APIs.
- Demo DB `medical_demo` only; `medical_dms` untouched; all names `DEMO-…` / `تجريبي`.

## Verification record (filled after the corrected build)
- Regression: runner stage `client-proto-fix-20261018` → 345 passed / 0 failed (backend untouched).
- Browser: workflows (login, nav, selection, validation, save/reopen, linked records) — see `docs/evidence/invoice-cycle/client-proto-fix-20261018/pytest.log` and `run.json` (345 passed; disposable DB; `POSTING_ENABLED=false`).
- Responsive: DOM-audit at 390 / 768 / 1440 (emulation) + Lighthouse mobile — emulation only, **no physical-device pass was possible in this environment**.
- Remote: public HTTPS URL re-verified end-to-end after the fixes.
