# Supplier maintenance — B-02 local API slice

## Source and scope

Owner-authorized October 22, 2026 B Master Data continuation; PRD B-02 and Module B CRUD acceptance; existing `0011_master_data_b` supplier schema; `DATABASE_SCHEMA.md` §13 master-data soft deletion.

This slice is supplier **reference maintenance through the API**, not purchasing, payables, real-data import, a PWA editing screen or production activation. No migration or new dependency is required. Customer/territory/warehouse imports remain separate: unresolved source mappings must not be guessed.

## Access and contract

| Operation | Access | Behavior |
|---|---|---|
| `GET /master/suppliers` | Existing owner/finance/auditor roles | Existing active-only lookup is preserved |
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

## Verification boundary

Use only `scripts/verify_invoice_cycle.py` with new stage labels and fresh disposable `dms_cycle_test_*` databases. Test traces, case counts, hashes, reviews and checkpoint receipts live under the existing `docs/evidence/invoice-cycle/` tree and the private task evidence directory:

`C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/supplier-maintenance-20261022/`

`POSTING_ENABLED` remains default OFF. Quarantined `medical_dms`, original workbooks, protected configuration, OpenCode admission, publication and deployment gates are unchanged. Passing this local API slice is not whole-ERP or unattended-worker approval.
