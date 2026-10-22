# Supplier maintenance — B-02 local API and PWA

## Source and scope

Owner-authorized October 22, 2026 B Master Data continuation; PRD B-02 and Module B CRUD acceptance; existing `0011_master_data_b` supplier schema; `DATABASE_SCHEMA.md` §13 master-data soft deletion.

The original `d92cb28` checkpoint delivered supplier **reference maintenance through the API**, without a PWA editing screen. The follow-up below adds that screen; neither scope includes purchasing, payables, real-data import or production activation. No migration or new dependency is required. Customer/territory/warehouse imports remain separate: unresolved source mappings must not be guessed.

## Access and contract

| Operation | Access | Behavior |
|---|---|---|
| `GET /master/suppliers` | Existing owner/finance/auditor roles | Default active-only lookup is preserved; `include_inactive=true` is restricted to the confirmed owner for maintenance |
| `GET /master/suppliers/{id}` | Same existing supplier readers | Retrieve a supplier, including inactive rows; missing ID → 404 |
| `POST /master/suppliers` | Active owner role **and** `is_owner=true` | Validated create, 201; duplicate code → 409 |
| `PATCH /master/suppliers/{id}` | Same owner-only write gate | Explicit partial fields, locked update and audit; can reactivate |
| `DELETE /master/suppliers/{id}` | Same owner-only write gate | Soft deactivate, 204; no physical deletion |

The initial write boundary is deliberately owner-only. Existing read access does not grant finance, auditors, administrators or representatives write access. No role, branch or financial policy is expanded.

- `code`: nonblank trimmed string, maximum 30 characters.
- `name_ar`: nonblank trimmed string, maximum 200 characters.
- `name_en` / `contact_phone`: nullable strings, maximum 200 / 30 characters; `address`: nullable string.
- Updates must be nonempty. Required values cannot be set to null; `is_active` accepts actual JSON booleans only.
- Unknown/system fields are rejected. The server determines ID and audit actor. All SQL values are parameters.

Supplier changes and actor-bound audit records share one transaction. Errors must roll back both. Updates/deactivation lock the supplier row. Deactivation preserves the row/ID and audit history; active-list consumers no longer offer it, while an authorized reader can still retrieve it by ID.

## Owner PWA follow-up

Open **Suppliers** in the existing Arabic/English PWA. Only an authenticated owner role with `is_owner=true` receives Add, Edit, Deactivate and Reactivate controls; finance and auditors remain read-only. Activity is revalidated by the server, not an absent client-side activity flag.

- Add/Edit uses one labelled native dialog. Optional fields can clear to null; server validation and duplicate-code errors keep entered values visible. Save is single-flight and Cancel/Escape cannot imply cancellation while a request is being saved.
- Edit retrieves the selected UUID again and saves through the existing PATCH transaction. Deactivation requires confirmation and preserves the supplier row and audit trail; it is not physical deletion.
- The owner's maintenance list explicitly includes inactive rows so reactivation remains available after reload. Other readers retain the default active-only list. Status is text, not color alone.
- The existing collection limit remains; pagination, purchasing and import are separate work. API data stays network-only; offline mutation or installation acceptance is not claimed. The shell cache is versioned for changed assets.

Browser controls use ordinary login, navigation and the shipped client against a loopback server bound to the approved disposable database. Independent committed-row/audit reads establish persistence; fresh contexts with service workers blocked establish UI behavior only, not offline/install behavior. Screenshots and native receipts are retained with their run.

## Verification boundary

Use only `scripts/verify_invoice_cycle.py` with new stage labels and fresh disposable `dms_cycle_test_*` databases. Test traces, case counts, hashes, reviews and checkpoint receipts live under the existing `docs/evidence/invoice-cycle/` tree and the private task evidence directory:

`C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/supplier-maintenance-20261022/`

`POSTING_ENABLED` remains default OFF. Quarantined `medical_dms`, original workbooks, protected configuration, OpenCode admission, publication and deployment gates are unchanged. Passing this local API slice is not whole-ERP or unattended-worker approval.
