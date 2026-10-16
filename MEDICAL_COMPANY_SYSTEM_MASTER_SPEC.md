# Medical Company System - Master Planning / Lain Handoff

> **Status:** Phase 0 - discovery and planning. This document is **not authorization to start coding** unless Eli explicitly says so.
>
> **Primary rule:** The existing Excel workbooks are the current operational source/specification. Every relevant business feature, rule, formula, relationship, exception and report must be discovered and mapped before it is replaced.

---

## 1. Project intent

Build a **custom business-management system for a medical company** that centralizes the capabilities currently spread across Excel workbooks into a more reliable, maintainable, secure and extensible application.

The goal is **not** to turn Excel itself into an app or clone spreadsheet mechanics. The goal is to preserve the **business capabilities** implemented in the spreadsheets, improve them, and add capabilities that are difficult or fragile in Excel: centralized data, permissions, auditability, dashboards, statistics, automation, safer calculations, better search, stable reporting, multi-user access, mobile access and future integrations.

Working category/name until a better one is chosen:

- **Medical Distribution Business Management System**
- **ERP-lite / Distribution Management System (DMS)**
- Final product/project name: **TBD**

---

## 2. Current decisions / working baseline

These are the decisions already discussed. Treat them as the current working baseline, but Eli may change them during planning.

| Area | Current position | Status |
|---|---|---|
| Build strategy | Build a custom system rather than using ERPNext as the application base | Working decision |
| Open-source ERP use | Use ERPNext and other mature open-source systems as **references** for architecture/workflows/UI ideas | Working decision |
| Code ownership goal | Own/control the application-specific source code, schema, UI and business logic; dependencies remain under their own licenses | Working decision |
| Database | PostgreSQL | Working decision |
| Desktop + mobile | Responsive web application / PWA | Working decision |
| Budget | Zero-cost / free-and-open-source-first | Non-negotiable unless Eli changes it |
| Hosting | Existing always-on company PC in the CEO room | Working decision |
| Remote use | Must work for authorized users who are **not on the same Wi-Fi/network** | Requirement |
| Telegram | Implement before WhatsApp | Working decision |
| WhatsApp | Later phase; do not let it block the core system | Working decision |
| Dashboard | Add useful statistics/KPIs such as sales, collections, profit/loss, balances and trends | Requirement, exact metrics TBD |
| Backend framework | TBD with Eli/Lain | Open |
| Frontend framework | TBD with Eli/Lain | Open |
| Remote-access/tunnel/DDNS solution | TBD after comparing secure zero-cost options | Open |
| Final UI/branding | TBD | Open |

### Important ownership/licensing clarification

"Own the system" means the company/Eli should own or control the **original application-specific code and data model** they create. Open-source runtimes/libraries retain their own copyrights/licenses.

Rules for third-party code:

1. Do not assume "open source" means "copy anything freely without obligations."
2. Record the license of every important dependency/reference before direct code reuse.
3. Prefer permissive dependencies (MIT/BSD/Apache/PostgreSQL-style) where practical, but do not blindly reject other licenses without evaluating the real use case.
4. Do **not** copy GPL/copyleft source from ERPNext or another project into the custom codebase unless Eli explicitly approves that licensing consequence after review.
5. Studying workflows, data concepts, UX patterns and architecture is allowed as reference work; independently implement the chosen behavior.
6. Keep a `THIRD_PARTY_NOTICES.md` / dependency license inventory if the project reaches implementation.

---

## 3. Source Excel workbooks

### Current uploaded workbook names

The current ChatGPT-session copies are:

```text
/mnt/data/الميزانية العمومية 2026.xlsx
/mnt/data/حسابات خاصه.xlsx
/mnt/data/مبيعات 6 اكتوبر 2026.xlsx
/mnt/data/مبيعات الدقهليه 2026.xlsx
/mnt/data/مبيعات الشرقية 2026.xlsx
/mnt/data/مبيعات الغربية  2026.xlsx
/mnt/data/مبيعات الفيوم 2026.xlsx
```

**Important:** These `/mnt/data/...` paths are ChatGPT workspace paths. Eli will provide Lain with the real local/project path. Before analysis, set:

```text
EXCEL_SOURCE_ROOT = <ELI_TO_PROVIDE>
```

Then locate the exact files by name and record the resolved paths in the project documentation.

### Source preservation rules

- Never edit the original Excel source files during discovery.
- Make read-only/copy-on-write working copies if tooling requires changes.
- Preserve original timestamps/checksums where practical.
- Never "fix" suspicious values or formulas silently during extraction.
- Record anomalies and ask for a business decision.

---

## 4. Non-negotiable Excel discovery / no-omission protocol

Before designing the final database or feature set, Lain must perform **full spreadsheet archaeology**.

For every workbook, inspect and inventory:

- every visible sheet;
- every hidden/very-hidden sheet;
- sheet order and naming conventions;
- used ranges and major data regions;
- column/row headers;
- formulas;
- formula patterns copied across rows/columns;
- cross-sheet references;
- cross-workbook links;
- named ranges/names;
- tables;
- data validation/dropdowns;
- conditional formatting **when it carries business meaning**;
- pivot tables/charts/report sheets if present;
- merged cells/labels that identify business sections;
- manual-input areas vs calculated areas;
- totals/subtotals;
- opening/closing balances;
- dates and period logic;
- customer/product/account identifiers;
- duplicate or near-duplicate entities;
- error values or broken links;
- protected/locked sections if present;
- external sources/connections if present;
- macros/VBA if present;
- comments/notes if present;
- formatting conventions that encode status/meaning;
- printed/exported reports the business actually uses;
- manual steps employees perform around the workbook that are not represented by formulas.

### Every existing capability must receive one status

Each discovered workflow/feature must be classified as:

- `KEEP` - same business behavior in the new system;
- `IMPROVE` - same business purpose, better implementation;
- `REPLACE` - replaced by a different workflow that achieves the same or better business purpose;
- `DEPRECATE_PENDING_APPROVAL` - appears unnecessary but **cannot be removed until Eli/business owner explicitly approves**;
- `UNKNOWN_NEEDS_INTERVIEW` - intent cannot be safely inferred from the workbook.

Never silently omit something because it looks redundant, ugly, old, duplicated or badly designed.

---

## 5. Required discovery outputs before implementation

Lain should produce these artifacts before coding the production system:

1. `SOURCE_WORKBOOK_INVENTORY.md`
   - workbooks, sheets, hidden sheets, rough purpose, dependencies.
2. `EXCEL_FEATURE_CATALOG.md`
   - each business feature/workflow/formula/report and its source location.
3. `DATA_DICTIONARY.md`
   - fields, meanings, units, money precision, dates, identifiers, null rules.
4. `ENTITY_DUPLICATE_REPORT.md`
   - suspected duplicate customers/products/accounts and proposed resolution rules.
5. `CURRENT_WORKFLOWS.md`
   - actual workflows, including manual steps and exceptions.
6. `EXCEL_TO_SYSTEM_MAPPING.md`
   - source feature/data -> target module/entity/calculation/UI/report.
7. `OPEN_QUESTIONS.md`
   - anything that cannot be inferred safely.
8. `MIGRATION_RECONCILIATION_PLAN.md`
   - exact checks that prove migration accuracy.
9. The six planning documents listed later in this master file.

Do not start implementing major business modules while material unknowns remain in these documents.

---

## 6. Product requirements - planning scope

The final PRD must answer, at minimum:

### Users / roles

Potential roles to confirm from the company rather than assume:

- CEO / owner
- system administrator
- finance/accounting
- sales manager
- sales representative
- warehouse/inventory
- branch/area manager
- read-only/auditor
- other company-specific roles

For each role define:

- what they need to see;
- what they can create;
- what they can edit;
- what they can void/cancel;
- what they can approve;
- what they can export;
- what they must never see;
- desktop vs mobile use cases.

### Candidate business areas discovered/expected

These are **planning candidates, not a final feature list**. The Excel discovery must prove the actual scope:

- customers / pharmacies / distributors / warehouses / accounts;
- products/catalog;
- pricing and discount rules;
- sales / invoices / sales history;
- collections/payments/receivables;
- balances and statements;
- inventory / stock movement;
- consignment or customer-held stock if the spreadsheets use it;
- branches/areas/governorates/territories;
- representatives and assignments;
- expenses/revenue;
- cash/bank/accounting records;
- profit/loss and management reporting;
- assets/depreciation if present;
- payroll/employee financial data if present;
- purchasing/manufacturing/raw-material logic if present;
- owner/private accounts if present and whether they belong in the same security boundary;
- dashboards/statistics;
- Excel/CSV import/export;
- Telegram integration;
- WhatsApp integration later.

Do not implement any item solely because it appears in this candidate list. Confirm it from sources/users.

---

## 7. Dashboard / analytics direction

The main page should eventually provide useful management information instead of forcing the CEO to open many sheets and manually compare numbers.

Candidate KPIs/charts to validate with real data/business definitions:

- sales today / week / month / year;
- collections today / week / month;
- receivables/outstanding balances;
- revenue;
- expenses;
- gross/net profit or other company-defined profit metric;
- profit/loss trend;
- sales vs collections;
- sales by governorate/area/branch;
- sales by representative;
- top customers;
- highest outstanding customer balances;
- product performance;
- inventory value;
- low-stock/attention alerts;
- customer-held/consignment stock if applicable;
- overdue payments if the business uses due dates/credit terms.

For every KPI, document the exact formula/business definition before implementation. Never guess accounting meanings from a label alone.

---

## 8. Architecture direction

### High-level target

```text
Desktop browser / Installed PWA / Mobile browser
                     |
                     | HTTPS
                     v
             Web application / API
                     |
                     v
                 PostgreSQL
```

The exact backend/frontend framework is intentionally **not locked yet**.

### Architecture requirements

- PostgreSQL is the current database decision.
- The application must support multi-user access safely.
- Users may connect from networks outside the office.
- PostgreSQL must **not** be exposed directly to the public Internet.
- Public traffic should reach the application only through a secure HTTPS entry point.
- Business transactions involving money/stock must use database transactions appropriately.
- The design must support role-based permissions and audit trails.
- The system must have a backup and restore procedure before production use.
- The system must recover cleanly after server reboot.
- The PWA must work well on both desktop and mobile layouts.

### Hosting situation

Available host:

- existing PC in the CEO room;
- intended to stay powered/connected 24/7;
- internet connection available;
- users are **not guaranteed to be on the same LAN/Wi-Fi**.

To decide with Lain:

- OS for server;
- service/container strategy;
- reverse proxy / HTTPS;
- stable public hostname;
- tunnel vs DDNS vs private network vs another secure approach;
- ISP public-IP/CGNAT constraints;
- power/UPS considerations;
- remote administration;
- monitoring;
- backups.

### Zero-cost remote-access requirement

Research and compare zero-cost candidates. Do not lock one in without checking current limits/terms and the company's network conditions.

Examples previously discussed as **candidates only**:

- Cloudflare Tunnel / `cloudflared`;
- DuckDNS + a reverse proxy such as Caddy when direct reachability is available;
- private mesh/VPN options where appropriate;
- other open-source/self-hosted alternatives.

A free temporary development URL is not automatically acceptable as a production hostname.

---

## 9. Telegram first, WhatsApp later

### Telegram

Telegram is the first messaging integration to consider because it fits the zero-cost-first plan better and can be isolated from the core app.

Possible use cases to confirm:

- executive daily summary;
- customer/account lookup;
- outstanding balance lookup;
- low-stock alerts;
- collection/payment alerts;
- exception alerts;
- scheduled reports;
- links back into the main app.

Security rules:

- whitelist/authorize Telegram users;
- do not expose sensitive data to arbitrary bot users;
- log sensitive bot actions;
- minimize data sent through Telegram;
- prefer read-only/reporting commands first;
- require explicit approval before allowing high-impact write actions through chat.

### WhatsApp

WhatsApp is **later**, after the core system and Telegram are stable.

Before implementation:

- evaluate official API cost/limitations/current terms;
- evaluate whether semi-automation is enough;
- avoid making a critical company workflow depend on a fragile unofficial integration without an explicit risk decision;
- define exactly which messages/workflows create measurable value.

---

## 10. Security baseline

This is company financial/operational software. "Zero budget" does not mean security is optional.

Minimum planned controls:

- HTTPS for remote use;
- no public PostgreSQL port;
- role-based authorization;
- least-privilege service/database accounts;
- strong password handling using a mature authentication library/framework;
- session expiration/revocation;
- CSRF/XSS/SQL-injection protections provided by the chosen framework plus secure coding;
- input validation;
- rate limiting for public/auth endpoints;
- secrets outside source control;
- audit log for important edits/voids/approvals;
- safe soft-delete/void patterns for financial/stock history;
- backups;
- restoration tests;
- dependency updates and vulnerability review;
- server firewall/minimal exposed services;
- logs that do not leak passwords/tokens/sensitive information.

Open questions:

- 2FA requirements;
- export/download restrictions;
- owner/private-account separation;
- whether any medical/patient personal data is involved;
- Egypt-specific regulatory obligations applicable to the actual data/business process.

Do not assume patient records exist simply because the business is a medical company.

---

## 11. Database/schema principles

The schema must be derived from actual business concepts discovered from the spreadsheets and users.

General principles:

- one canonical record per real entity where possible;
- stable primary keys that do not depend on Excel row numbers;
- business identifiers can be unique constraints where justified;
- money uses an exact numeric/decimal type, never binary floating point;
- define currency explicitly;
- define quantity precision per domain;
- use timestamps consistently and document timezone;
- preserve transaction history;
- avoid hard deletes of posted financial/stock records unless the business/legal model explicitly requires it;
- use status/void/reversal patterns when appropriate;
- immutable audit trail for sensitive actions;
- normalize repeated workbook structures into relational data, but do not over-normalize at the expense of maintainability;
- calculated values should be derived consistently from source transactions unless a snapshot is deliberately required for audit/performance reasons.

Before schema approval, produce an ER diagram plus a plain-English explanation of every important entity and relation.

---

## 12. Migration and reconciliation requirements

Migration is not complete because data "looks about right." It must be proven.

For each source workbook/sheet/data group, define verification such as:

- source row count vs imported record count;
- distinct customer/product/account count;
- duplicate count;
- total sales;
- total collections/payments;
- opening/closing balances;
- customer-by-customer balance comparison;
- per-governorate/area totals;
- inventory quantities/values;
- accounting totals;
- month/year totals;
- formula output equivalence where the formula represents a business rule;
- date ranges;
- null/blank counts;
- rejected/anomalous rows;
- checksums/hashes for immutable source files where useful.

### Precision rule

Do not round or "clean" financial values just to make migration easier. Define exact decimal precision and rounding rules from the business process. If a source value is `1,284,294.75`, changing it to `1,284,295` is not an acceptable migration unless an explicitly approved business rule says so.

### Migration stages

1. immutable source backup;
2. extraction/inventory;
3. anomaly report;
4. transformation rules approved;
5. dry-run import;
6. reconciliation report;
7. user review;
8. repeat until clean;
9. production migration;
10. final reconciliation + sign-off;
11. retain source archive and migration evidence.

---

## 13. Testing / release gates

Do not report "ready" from build success or a few unit tests.

Required test categories should include, as applicable:

- unit tests for calculations/business rules;
- database constraints;
- transaction/integration tests;
- permission tests;
- end-to-end critical workflows;
- concurrency/race-condition tests for sensitive records;
- migration/reconciliation tests;
- responsive/mobile UI tests;
- export/report tests;
- Telegram integration tests;
- backup restore test;
- server reboot/restart test;
- performance tests with realistic data size;
- security review before public exposure;
- user acceptance testing with actual company users.

### Release gate

A phase is not "done" until its agreed acceptance evidence exists and Eli/business owner signs off.

---

## 14. Six core planning documents

The supplied planning checklist requires six documents before serious build work. Use these names in the project so everyone refers to the same artifacts.

### 14.1 `PRD.md` - Product Requirements Document

Must include:

- project goal;
- users/roles;
- feature list;
- user goals;
- business rules;
- edge cases;
- acceptance criteria;
- out-of-scope items;
- priorities;
- unresolved questions.

### 14.2 `TECHNICAL_REQUIREMENTS.md`

Must include:

- approved stack;
- architecture;
- PostgreSQL strategy;
- hosting/server details;
- remote access/HTTPS;
- backup/recovery;
- supported devices/browsers;
- dependency/license policy;
- Telegram/WhatsApp integration approach;
- performance/reliability targets;
- observability/logging.

### 14.3 `APP_FLOW.md`

Must include:

- navigation map;
- screen-by-screen flows;
- role-specific flows;
- success/failure paths;
- validation states;
- approval/override paths;
- mobile-specific flows;
- authentication/logout/session flows.

### 14.4 `DESIGN_BRIEF.md`

Must include:

- company branding;
- Arabic/English requirements;
- typography/color system;
- component rules;
- table/grid behavior;
- dashboard layout;
- responsive behavior;
- accessibility/usability requirements;
- examples of what the UI should **not** look like.

### 14.5 `DATABASE_SCHEMA.md`

Must include:

- ER diagram;
- entities/tables;
- fields/types;
- keys and constraints;
- relationships;
- calculated/snapshot fields;
- access rules;
- audit model;
- deletion/void/reversal policy;
- migration mapping.

### 14.6 `IMPLEMENTATION_PLAN.md`

Must include:

- stages;
- dependencies;
- deliverables per stage;
- tests/evidence per stage;
- approval gates;
- rollback approach;
- migration schedule;
- go-live plan;
- post-launch stabilization.

---

## 15. Open-source reference projects

### Primary reference discussed

```text
ERPNext
Reference URL: <ELI / LAIN TO ADD>
Purpose: study workflows, architecture, accounting/inventory/customer patterns, permissions, reporting and UX concepts.
Policy: reference only unless a separate explicit code-reuse/license decision is made.
```

### Additional references

Create `OPEN_SOURCE_REFERENCES.md` and add any useful ERP/DMS/CRM/accounting/inventory/PWA/self-hosting projects with:

```text
Project:
Repository URL:
License:
What we want to learn:
Specific modules/files/pages worth studying:
Whether direct code reuse is allowed/desired:
Attribution/notice obligations:
Decision:
```

Do not use star count alone as evidence of quality. Review activity, maintainers, issue history, architecture, security posture, documentation and license.

---

## 16. Proposed project repository documentation structure

This is a planning suggestion; adjust before implementation.

```text
docs/
  00_PROJECT_MASTER_SPEC.md
  01_PRD.md
  02_TECHNICAL_REQUIREMENTS.md
  03_APP_FLOW.md
  04_DESIGN_BRIEF.md
  05_DATABASE_SCHEMA.md
  06_IMPLEMENTATION_PLAN.md
  SOURCE_WORKBOOK_INVENTORY.md
  EXCEL_FEATURE_CATALOG.md
  CURRENT_WORKFLOWS.md
  DATA_DICTIONARY.md
  ENTITY_DUPLICATE_REPORT.md
  EXCEL_TO_SYSTEM_MAPPING.md
  MIGRATION_RECONCILIATION_PLAN.md
  SECURITY_MODEL.md
  BACKUP_AND_RECOVERY.md
  OPEN_SOURCE_REFERENCES.md
  OPEN_QUESTIONS.md
  DECISION_LOG.md
  THIRD_PARTY_NOTICES.md
```

---

## 17. Suggested implementation phase model

The exact phase boundaries can change after discovery.

### Phase 0 - Discovery

- preserve source workbooks;
- inventory every workbook/sheet;
- extract features/business rules;
- interview real users for manual workflows/ambiguous meanings;
- build data dictionary;
- identify duplicates/anomalies;
- produce open questions.

**Exit gate:** no major unknowns that would force the schema/app to be guessed.

### Phase 1 - Planning / architecture

- complete six core docs;
- choose backend/frontend;
- choose hosting/remote-access method;
- design schema;
- define security roles;
- define migration/reconciliation tests;
- prototype risky decisions only.

**Exit gate:** approved technical/product plan.

### Phase 2 - Platform foundation

Potential scope:

- repository structure;
- PostgreSQL migrations;
- authentication;
- roles/permissions;
- audit foundation;
- shared validation/error handling;
- basic layout/PWA shell;
- CI/test foundation;
- development fixtures.

### Phase 3+ - Business modules

Build one coherent business slice at a time, each with tests and Excel/source reconciliation where applicable.

Do not build all modules in parallel before the core data model is proven.

### Telegram phase

Add after enough core data is trustworthy to make Telegram useful.

### Production migration / go-live

Only after:

- migration reconciliation passes;
- backups/restores tested;
- permissions tested;
- deployment/restart tested;
- UAT signed off.

### WhatsApp phase

After stable production operation and an explicit integration/cost/risk decision.

---

## 18. Rules for Lain

1. **Do not start coding simply because this file exists.** Ask whether Eli is authorizing implementation or only planning/research.
2. Use the real Excel workbooks as evidence. Do not infer unseen behavior from filenames alone.
3. Do not remove or merge business features without an explicit mapping and approval.
4. Do not silently repair source data.
5. Do not invent accounting definitions.
6. Do not invent customer/product matching rules.
7. Do not expose PostgreSQL publicly.
8. Do not hardcode secrets/API tokens.
9. Do not make ERPNext a dependency unless Eli changes the current strategy.
10. Do not copy copyleft code into the custom application without an explicit licensing decision.
11. Preserve the zero-cost/open-source-first constraint when comparing tools.
12. Prefer maintainable, boring, well-supported components over novelty.
13. Every sensitive mutation should be transactional, validated and auditable.
14. Every migration claim must be backed by reconciliation evidence.
15. When the source and desired future behavior conflict, document the difference and ask.
16. Maintain `DECISION_LOG.md` so later sessions know which decisions superseded earlier ones.
17. Reply in the language Eli is currently using unless he asks otherwise.

---

## 19. Decisions still intentionally open

Discuss these with Eli before treating them as fixed:

- exact backend framework;
- exact frontend framework;
- monolith vs separately deployed frontend/API;
- containerization strategy;
- server operating system;
- public hostname/domain strategy;
- Cloudflare Tunnel vs DDNS/reverse proxy vs other access method;
- offline PWA behavior;
- exact role list;
- exact accounting scope;
- whether owner/private accounts belong in the same application/database;
- exact Telegram commands and automation;
- WhatsApp approach;
- final dashboard metrics;
- Arabic/English localization requirements;
- printing/PDF/report layout requirements;
- notification strategy;
- backup destination and offsite-copy method;
- 2FA;
- whether the company needs accounting/legal/regulatory controls beyond the current Excel workflows;
- project/product name.

---

## 20. Build-start gate

Before implementation begins in earnest, confirm all of the following:

- [ ] PRD reviewed and approved
- [ ] Technical requirements reviewed and approved
- [ ] App flow reviewed and approved
- [ ] Design brief reviewed and approved
- [ ] Database schema reviewed and approved
- [ ] Implementation plan reviewed and approved
- [ ] Excel source inventory complete enough to avoid major omissions
- [ ] Feature mapping complete
- [ ] Data dictionary complete enough for the first module
- [ ] Migration/reconciliation plan approved
- [ ] Roles/security model approved
- [ ] Hosting/remote-access approach approved
- [ ] Backup/restore plan approved
- [ ] Open-source dependency/license policy approved
- [ ] Pilot scope approved
- [ ] Acceptance criteria approved

If these are not true, continue discovery/planning rather than allowing the implementation to drift through guesses.

---

## 21. One-paragraph mission statement for Lain

> Build a custom, zero-cost/open-source-first medical-company business management system that centralizes the business capabilities currently implemented across the supplied Excel workbooks into a reliable PostgreSQL-backed web/PWA application for desktop and mobile. Preserve every relevant business capability unless an explicit decision changes it; improve reliability, auditability, reporting, statistics and usability; self-host on the company’s always-on CEO-room PC while supporting secure access from other networks; implement Telegram before WhatsApp; use ERPNext and other open-source projects as design/reference material rather than making them the application codebase; and do not start major implementation until spreadsheet discovery, requirements, schema, migration/reconciliation, security and implementation planning are documented well enough that no critical behavior must be guessed.

---

## 22. Immediate next action when Eli gives Lain the Excel path

Do **not** code the app first.

Start with:

```text
1. Resolve EXCEL_SOURCE_ROOT.
2. Hash / inventory the source files without modifying them.
3. Enumerate all workbooks and sheets, including hidden sheets.
4. Produce SOURCE_WORKBOOK_INVENTORY.md.
5. Begin EXCEL_FEATURE_CATALOG.md and DATA_DICTIONARY.md.
6. Record unknown business meanings in OPEN_QUESTIONS.md.
7. Present the discovery findings to Eli before designing the final schema.
```

That discovery output becomes the evidence base for the six planning documents and the eventual implementation plan.
