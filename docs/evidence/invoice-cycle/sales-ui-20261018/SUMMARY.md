# Sales UI slice — verified evidence (2026-10-18)

## What this is

The first functional Sales UI on the existing vanilla-JS PWA, plus the minimal
read-only master-data API it genuinely needed. No framework, no rewrite, no new
business module; production posting stays disabled.

## Delivered

- **Backend (new, read-only):** `app/master/{__init__,schemas,router}.py`
  expose `GET /master/branches|warehouses|customers|products`, scoped
  identically to invoice creation:
  - owner (with `is_owner=true`) sees everything; other roles are limited to
    `platform.user_territory` (customers) / `platform.user_branch`
    (branches, warehouses);
  - warehouses keep the owned-or-routed rule (`master_warehouse.branch_id`
    OR `inventory.branch_warehouse`);
  - customers must be active, territory-assigned **and** have a non-null
    branch (invoice create requires `customer.branch_id == invoice.branch_id`);
  - roles outside the invoice read set are rejected 403.
  Registered in `app/main.py`.

- **Frontend (rewritten PWA shell):** `web/index.html`, `web/app.js`,
  `web/styles.css` — sign-in (`/auth/login` → `/auth/me`), RTL Arabic default
  with an English toggle, customer / branch / source-warehouse / product
  selection, a line editor (quantity, discount %), client-side **estimated**
  totals, and draft creation via `POST /invoices`; the saved-draft view shows
  the **server** totals and the invoice status. Validation errors surface in an
  alert region and handle both FastAPI 422 detail lists and 401/403/404/409
  string details. `POST /invoices/{id}/post` is reached only through the
  server's guarded route and its 409 is displayed — the gate is neither
  bypassed nor reimplemented. Read-only auditors can browse but the create
  controls are disabled.

- **Supporting:** i18n dictionaries expanded with identical key sets;
  `web/sw.js` shell list updated (cache v2).

## Verification

Approved disposable-DB runner, stage `sales-ui-20261018`:

- **334 passed, 0 failed / 0 errors / 0 skips**; full migration up → down-one →
  up to head `0010_invoice_collections`.
- Disposable `dms_cycle_test_*` created and dropped; source/config/Excel hashes
  unchanged during the run; `POSTING_ENABLED` still resolves OFF in a clean
  process.
- New tests: `tests/test_master_api.py` (scope parity with invoice create,
  owned-or-routed warehouses, territory scoping, role denial including
  `owner`-with-`is_owner=false`, null-branch exclusion, auditor read-only,
  server-priced draft, closed posting gate) and `tests/test_pwa_invoice_ui.py`
  (controls present, endpoints wired, i18n parity, no server value injected as
  HTML, assets served). `tests/conftest.py` guard extended to `test_master_api`
  so it can only run against the disposable database.
- Raw artifacts: `run.json`, `pytest.xml`, `pytest.log` (this directory).

## Deliberately NOT done

- Posting stays OFF; no merge to master; no push; `medical_dms` untouched.
- No price-override UI (the server always prices from the product base price).
- No invoice edit / void / drafts-list UI.
- No product search or paging (the endpoint caps at 100 rows).
- No collections / payments / stock UI.

## What remains for the full Invoice → Stock → AR → Collections workflow

1. **Master Data (B)** is still largely absent: real customers, products,
   branches, warehouses and territories must be loaded (read-only Excel import)
   before the selects hold real data; suppliers, chart of accounts and the
   doctor/KOL list remain unbuilt.
2. **Invoice lifecycle UI:** drafts list/search, edit and void; decide a real
   invoice-numbering policy (the client currently suggests `INV-<epoch8>`).
3. **Batch selection** per line (`batch_id` exists server-side; the UI omits
   it) and product search/paging for catalogs larger than 100 rows.
4. **Posting activation** — a separate owner-authorized gate; the UI already
   targets the guarded endpoint.
5. **Stock / AR / Collections UI** (balances, receipts, receipt void) plus
   role-aware navigation.
