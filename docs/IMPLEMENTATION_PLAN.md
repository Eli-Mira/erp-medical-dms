# IMPLEMENTATION PLAN — Medical Company System

> **Authoritative references:** `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (authoritative), `MODULE_MAP.md`, `MIGRATION_RECONCILIATION_PLAN.md`, `DECISION_LOG.md`, `OPEN_QUESTIONS.md`, `EXCEL_TO_SYSTEM_MAPPING.md`, `DATA_DICTIONARY.md`, `CURRENT_WORKFLOWS.md`.
>
> **Status:** Phase 0 discovery complete. All open questions resolved (D26). Build-start gate pending final sign-off per V2 §20.
>
> **Build-start gate:** The build MUST NOT proceed until all six core planning documents (PRD, Technical Requirements, App Flow, Design Brief, Database Schema, this Implementation Plan) plus Security Model, Backup Plan, Dependency Policy, Pilot Scope, and Acceptance Criteria are reviewed and approved by Eli (V2 §20). This document is an implementation plan, not authorization to code.

---

## 1. Overview

This plan governs the sequential delivery of a custom, zero-cost/open-source-first medical company business management system. The system centralizes capabilities from seven Arabic Excel workbooks into a PostgreSQL-backed PWA (desktop + mobile). Telegram is prioritized; WhatsApp is deferred.

**Build order:** A → B → C → D → E → F → G → H (Platform → Master Data → Sales → Inventory → Finance → Marketing → Purchasing → Executive Analytics/Telegram).

**Key constraints:**
- Zero-cost / open-source-first (non-negotiable).
- PostgreSQL as the sole production database.
- PWA for desktop and mobile access.
- Hosting on the existing CEO-room PC (always-on).
- PostgreSQL never exposed directly to the public internet.
- Secure remote access via a zero-cost tunnel/proxy (TBD after secure review).
- Telegram integration before WhatsApp.
- Migration must be proven via 11-stage reconciliation (V2 §12).

---

## 2. Phase Model

| Phase | Name | Purpose | Gate |
|---|---|---|---|
| Phase 0 | Discovery | Excel archaeology, evidence collection, open questions resolution | ✅ Complete (D26) |
| Phase 1 | Planning & Architecture | Six core docs + security model + backup plan + dependency policy + pilot scope + acceptance criteria + build-start sign-off | 🔒 Build-start gate (V2 §20) |
| Phase 2 | Platform Foundation | Repository, auth, RBAC, audit, schema migrations, PWA shell, CI | 🔒 Platform readiness gate |
| Phase 3 | Business Modules A–H | Build one coherent business slice at a time (A→H per MODULE_MAP.md) | 🔒 Per-module gate |
| Phase 4 | Telegram | Telegram bot integration (commands, alerts, read-only first) | 🔒 Telegram functional gate |
| Phase 5 | Production Migration | 11-stage migration + reconciliation | 🔒 Migration sign-off gate |
| Phase 6 | Go-Live | Deploy to production host, DNS/tunnel, monitoring, training | 🔒 Go-live approval |
| Phase 7 | WhatsApp | Deferred — only after stable production operation + explicit cost/risk decision | 🔒 Future gate |

---

## 3. Stages & Dependencies

### Phase 1 — Planning & Architecture (~2 weeks)

**Deliverables:**
1. `docs/PRD.md` — Product Requirements Document
2. `docs/TECHNICAL_REQUIREMENTS.md` — Stack, architecture, hosting, remote access, backup, devices/browsers, dependency/license policy, Telegram/WhatsApp approach, performance targets, observability
3. `docs/APP_FLOW.md` — Navigation map, screen flows, role-specific flows, validation/approval paths, mobile flows, auth/session flows
4. `docs/DESIGN_BRIEF.md` — Branding, Arabic/English requirements, typography, color, components, tables/grids, dashboard layout, responsive behavior, accessibility, UI anti-examples
5. `docs/DATABASE_SCHEMA.md` — ER diagram, entities/tables, fields/types, keys/constraints, relationships, calculated/snapshot fields, access rules, audit model, deletion/void/reversal policy, migration mapping
6. `docs/IMPLEMENTATION_PLAN.md` — This document
7. `docs/SECURITY_MODEL.md` — Roles, RBAC matrix, private/owner boundary, least-privilege, session rules, audit logging, encryption, secrets management
8. `docs/BACKUP_AND_RECOVERY.md` — Backup schedules, retention, restore tests, offsite strategy
9. `docs/DEPENDENCY_POLICY.md` — Open-source dependency license policy, vulnerability review cadence, THIRD_PARTY_NOTICES.md
10. `docs/PILOT_SCOPE.md` — Which branch/module is the pilot (recommended: Dakahlia sales workbook → Sales module C)
11. `docs/ACCEPTANCE_CRITERIA.md` — Per-module and per-phase acceptance criteria

**Evidence / Tests:**
- Evidence: All source workbooks inventory complete, SHA-256 hashes immutable (SOURCE_HASHES.txt).
- All open questions resolved (OPEN_QUESTIONS.md).
- Cross-linking between MODULE_MAP.md, EXCEL_TO_SYSTEM_MAPPING.md, and this plan verified.

**Approval Gate:**
- Eli explicitly signs off on all 11 deliverables before Phase 2 begins (V2 §20).

---

### Phase 2 — Platform Foundation (~3–4 weeks)

**Scope (per V2 §17):**
- Repository structure (monorepo or separate frontend/API repos)
- PostgreSQL migration framework (e.g., Alembic or similar)
- Authentication (mature library, strong password handling)
- Role-based authorization (RBAC) with private/owner accounts boundary
- Audit timeline foundation
- Shared validation and error handling
- Basic PWA shell (responsive layout, Arabic/English scaffolding)
- CI/test foundation (GitHub Actions or equivalent)
- Development fixtures (seed data matching Excel structure patterns)
- System settings scaffold (fiscal year, VAT, company info, currency, numbering)
- Posting status (Draft → Posted → Voided)
- Reason codes scaffold
- Import validation scaffold (preview, duplicates, rejected rows)
- Global search scaffold

**Dependencies:** Phase 1 sign-off (all six core docs + security model + backup plan + dependency policy + pilot scope + acceptance criteria approved).

**Deliverables:**
- Initialized repository with CI pipeline
- `alembic/` migrations directory with initial schema migration
- Auth module (login, session, logout)
- RBAC module (role matrix, permission checks)
- Audit logger (creates/edits/approves/voids logged)
- PWA manifest + service worker (offline-capable skeleton)
- Development fixture loader
- README with local dev setup instructions

**Tests / Evidence:**
- Unit tests for authentication, RBAC checks, audit logging
- Database constraint tests (no duplicate keys, decimal precision enforcement)
- Transaction/integration test for a basic create-then-void flow
- Permission tests verifying private/owner accounts boundary (D10)
- PWA manifest validates; service worker loads without errors
- CI passes on all test runs

**Approval Gate:**
- Platform readiness gate: CI green, all platform tests pass, security model implemented, backup script tested locally, developer can spin up a local instance and log in with role-based access.

**Rollback Approach:**
- All schema changes are migration files. To rollback: run `alembic downgrade <revision>` and verify data integrity. Keep migration history intact; never delete old migration files.
- If a migration breaks data, revert to the previous migration + restore from backup.

---

### Phase 3 — Business Modules A–H (~12–16 weeks)

**Build order:** A → B → C → D → E → F → G → H

**Important:** Do not build all modules in parallel before the core data model is proven. Each module builds on the previous module's outputs. One coherent business slice at a time, each with tests and Excel/source reconciliation where applicable.

#### Module A — Platform (Continued)
Already covered in Phase 2. Finalize any remaining cross-cutting concerns.

#### Module B — Master Data (~2 weeks)
**Scope:** Customers, suppliers/vendors, employees (minimal), items/products, warehouses/branches, UOM (box/pack/unit only if used per D13), agents, partners, chart of accounts (minimal COA for finance), territories/regions.
**Dependencies:** Module A (platform).
**Deliverables:** Master data CRUD endpoints, import validation, duplicate detection UI.
**Tests / Evidence:**
- CRUD tests for each entity type.
- Uniqueness constraints validated (branch-scoped by `(workbook_branch, entity_id)` per D17).
- Import validation: preview, duplicates flagged, rejected rows logged.
- Reconciliation: compare normalized master data counts against Excel source (distinct customer count, distinct product count, warehouse list vs workbooks).
**Approval Gate:** Master data import reconciles within tolerance; no duplicate collisions.

#### Module C — Sales (~3 weeks)
**Scope:** Sales transactions by branch/warehouse, HQ rollups (`الرئيسية`), sold balances (`رصيد الارصدة المباعة`), price lists (`كامل الكمية`), under-disposal view (`تحت التصريف`), per-warehouse sheets mapped by branch context. Credit management integration.
**Dependencies:** Module B (Master Data).
**Deliverables:** Sales transaction CRUD, price list management, HQ rollup computation, branch-scoped reporting, net price logic `E=C*(1-D)` preserved (D18).
**Tests / Evidence:**
- Net price formula unit test: `E = C*(1-D)` for sampled discount values (0.28–0.30).
- HQ rollup recompute test: branch totals match Excel `الرئيسية` for sampled rows.
- Branch scoping test: same-named sheets across workbooks do not collide (D17).
- Sales reconciliation: row counts + key totals vs source per branch.
- Credit management: limits, holds, aging (minimal per D12).
**Approval Gate:** Sales module reconciles against at least one branch workbook (pilot branch recommended: Dakahlia).

#### Module D — Inventory (~2 weeks)
**Scope:** Stock by warehouse, movements, allocations, `كامل الكمية`/`تحت التصريف` alignment, recons. Batch tracking, expiry-date tracking (V2 features 6, 7). Warehouse-to-warehouse transfers (V2 feature 3).
**Dependencies:** Module B (Master Data), Module C (Sales feeds inventory movements).
**Deliverables:** Stock level management, movement logging, transfer workflow, batch/expiry tracking, FEFO-ready infrastructure.
**Tests / Evidence:**
- Stock movement tests: transfer decreases source, increases destination, preserves batch info.
- Batch/expiry queries return correct remaining stock by batch.
- Zero-quantity invoice items hidden on printed output (V2 feature 4).
- Inventory reconciliation: per-warehouse stock totals match Excel sources.
**Approval Gate:** Inventory balances reconcile against source workbooks for pilot branch.

#### Module E — Finance (~3 weeks)
**Scope:** Cash (`النقديه`), AR (`العملاء` - wide 747 cols), AP, GL, Chart of Accounts, Balance Sheet (`الميزانيه`/`الموازنه العامه`), P&L (`الارباح والخسائر` + `الايرادات`/`التكاليف`/`المصروفات`), Fixed/Current Assets (`الاصول الثابته`/`الاصول المتغيره`), distributions.
**Dependencies:** Module C (Sales feeds AR/invoices), Module G (Purchasing feeds AP).
**Deliverables:** Cash ledger, AR ledger (wide columnar period mapping), AP ledger, GL, P&L reports, Balance Sheet reports, asset registers.
**Tests / Evidence:**
- AR ledger reconciliation: debit-credit balance matches Excel `العملاء` row totals (opening balance 2,200,000 validated per OPEN_QUESTIONS resolution).
- P&L totals reconcile against Excel `الارباح والخسائر`.
- Balance Sheet aggregates reconcile against Excel `الميزانيه`/`الموازنه العامه`.
- Cash ledger balances reconcile against Excel `النقديه`.
- VVAT calculation validation (V2 feature 5): consistent across products, stored per invoice line, validated against existing invoice output.
**Approval Gate:** All finance reconciliations pass; BS/P&L formulas match Excel samples within tolerance.

#### Module F — Marketing (~1–2 weeks)
**Scope:** Doctor/KOL marketing-spend tracking (V2 feature 16), product/brand-linked marketing spend (V2 feature 17), marketing activity objective + result/KPI tracking (V2 feature 18), sales targets by representative/territory/product/period (V2 feature 13).
**Dependencies:** Module B (Master Data: doctors, products, territories, reps).
**Deliverables:** Marketing spend entry, objective/result tracking, sales target management, KPI dashboards.
**Tests / Evidence:**
- Marketing spend records link correctly to doctor/KOL and product/brand.
- Sales targets comparable against actual performance.
- Stock-cover calculation (V2 feature 14): `Stock Cover = Current Stock / Recent Average Sales Rate` — configurable averaging window.
- Overstock alerts (V2 feature 15): configurable threshold, flagging works.
**Approval Gate:** Marketing module functions with sample data; stock-cover and overstock alerts verified.

#### Module G — Purchasing (~2 weeks, discovery-gated depth)
**Scope:** Suppliers, purchase orders, goods received notes, supplier payments. Raw materials and manufacturing discovery-gated per D11 — build only what Excel proves is used.
**Dependencies:** Module B (Master Data), Module D (Inventory receives stock).
**Deliverables:** PO/GRN workflow, supplier payments, stock-in movements on GRN.
**Tests / Evidence:**
- PO→GRN→stock increase flow tested.
- Supplier payment reconciliation against Excel sources (where purchasing data exists).
- Purchasing depth confirmed against D11 gating criteria.
**Approval Gate:** Purchasing reconciliation passes for existing data; MRP/BOM/PO scope approved before deeper build.

#### Module H — Executive Analytics / Telegram Integration (~3 weeks)
**Scope:** Cross-module executive dashboards, Telegram bot integration (read-only commands first, then selective write actions).
**Dependencies:** Modules A–G complete (analytics reads from all modules; Telegram needs trustworthy data).
**Deliverables:** Executive dashboard (KPIs, trends, sales by branch/rep, top customers, outstanding balances, inventory value, low-stock/overstock alerts), Telegram bot with whitelist, read-only commands (balance lookup, stock alerts, daily summary, links to app).
**Tests / Evidence:**
- Dashboard KPIs match aggregated module data.
- Telegram bot: whitelist enforced, sensitive data not exposed to unauthorized users, audit log for bot actions.
- Remote access tested via selected tunnel/proxy solution.
**Approval Gate:** Dashboard data accurate; Telegram bot secure and functional for authorized users only.

---

### Phase 4 — Telegram (~included in Module H, detailed here)

**Scope:**
- Whitelist/authorize Telegram users.
- Read-only commands first: balance lookup, stock alerts, daily summary, links back to app.
- Optional write actions (e.g., create sales invoice) only after explicit approval and security review.
- Log all sensitive bot actions.
- Minimize data sent through Telegram.

**Deliverables:**
- Telegram bot with configuration management.
- Command reference documentation.
- Security review for bot exposure.

**Tests / Evidence:**
- Unauthorized user blocked from sensitive commands.
- Audit log contains bot action entries.
- No password/token leakage in logs.

**Approval Gate:** Telegram security review passed; bot operational for pilot users.

---

### Phase 5 — Production Migration (~3–4 weeks, 11 stages)

**Reference:** V2 §12 migration stages (immutable backup → extraction → anomaly report → approved transformation rules → dry-run import → reconciliation report → user review → repeat until clean → production migration → final reconciliation + sign-off → retain archive).

**Migration Schedule:**

| Stage | Description | Evidence Required |
|---|---|---|
| 1 | Immutable source backup | SHA-256 hashes frozen (SOURCE_HASHES.txt already created) |
| 2 | Extraction/inventory | Row counts, sheet mappings, external link resolution |
| 3 | Anomaly report | Documented anomalies, duplicates, missing data |
| 4 | Transformation rules approved | Approved rules for data cleaning, branch scoping, cross-workbook consolidation |
| 5 | Dry-run import | Import into staging database; no production impact |
| 6 | Reconciliation report | Structural checks, aggregate checks, finance checks, security/boundary checks (per MIGRATION_RECONCILIATION_PLAN.md) |
| 7 | User review | Business owner/Eli reviews reconciliation report |
| 8 | Repeat until clean | Iterate stages 3–7 until reconciliation passes |
| 9 | Production migration | Import into production database during maintenance window |
| 10 | Final reconciliation + sign-off | Full reconciliation report; Eli signs off |
| 11 | Retain source archive | Source workbooks archived with migration evidence |

**Tests / Evidence:**
- Source row count vs imported record count (per module).
- Distinct customer/product/account count match.
- Total sales, total collections/payments match.
- Opening/closing balances match.
- Customer-by-customer balance comparison passes.
- Per-governorate/area totals match.
- Inventory quantities/values match.
- Accounting totals match.
- Month/year totals match.
- Formula output equivalence for business-rule formulas (`E=C*(1-D)`, `E=B-C-D`).
- Date ranges match.
- Null/blank counts within tolerance.
- Rejected/anomalous rows documented.
- Precision rule enforced: no rounding of financial values unless explicitly approved (V2 §12 precision rule).

**Approval Gate:** Migration sign-off gate — final reconciliation report approved by Eli; all 11 stages complete.

**Rollback Approach:**
- Before production migration: full database backup taken.
- If migration fails or reconciliation does not pass: restore from pre-migration backup; do not attempt partial fixes in production.
- Archive the failed migration run for analysis.

---

### Phase 6 — Go-Live (~1 week)

**Pre-requisites:**
- All phases 1–5 complete with approval gates passed.
- Backup/restore tested.
- Permissions tested.
- Deployment/restart tested.
- UAT signed off.

**Deliverables:**
- Production deployment on CEO-room PC.
- HTTPS endpoint via approved zero-cost tunnel/proxy.
- Monitoring and logging active.
- User training materials (if needed).
- Operational runbook.

**Tests / Evidence:**
- Server reboot/restart test: application recovers cleanly.
- Backup/restore test: full restore verified.
- Remote access test: users outside office network can access via HTTPS.
- UAT sign-off from business users.
- Performance test with realistic data size passes.
- Security review before public exposure passed.

**Approval Gate:** Go-live approval by Eli.

**Rollback Approach:**
- If critical post-deployment issues arise: revert to previous stable version (keep previous deployment artifact); restore database from last known-good backup.
- Maintain rollback decision log.

---

### Phase 7 — WhatsApp (Deferred)

**Scope:**
- Evaluate official API cost/limitations/current terms.
- Evaluate whether semi-automation is sufficient.
- Define exactly which messages/workflows create measurable value.
- Avoid making a critical company workflow depend on a fragile unofficial integration without explicit risk decision.

**Prerequisites:**
- Stable production operation confirmed (post-launch stabilization complete).
- Explicit integration/cost/risk decision by Eli.
- Security review completed.

**Approval Gate:** WhatsApp gate — only after explicit approval; must not block core system.

---

## 4. Approval Gates Summary

| Gate | Trigger | Required Sign-Off |
|---|---|---|
| Build-start gate | Phase 1 deliverables complete | Eli approves all 6 core docs + security model + backup plan + dependency policy + pilot scope + acceptance criteria (V2 §20) |
| Platform readiness gate | Phase 2 complete | CI green, all platform tests pass, security model implemented, backup tested |
| Per-module gate (A–H) | Each business module complete | Module tests pass, Excel/source reconciliation passes, acceptance criteria met |
| Telegram functional gate | Phase 4 complete | Bot security review passed, authorized users tested |
| Migration sign-off gate | Phase 5 complete | 11-stage migration reconciliation approved, Eli signs off |
| Go-live approval gate | Phase 6 complete | UAT signed off, deployment tested, remote access verified |
| WhatsApp gate | Phase 7 considered | Explicit Eli approval after production stability confirmed |

---

## 5. Rollback Approach

**General principles:**
- Every database change is a migration file; never alter production schema directly.
- Before any migration or import, take a full database backup.
- Keep previous deployment artifacts for at least 30 days after go-live.
- If a module fails post-deployment, revert to the previous stable module version.
- If migration fails, restore pre-migration database from backup; do not patch in production.

**Per-phase rollback:**
- **Phase 2 (Platform):** Revert migrations + restore backup.
- **Phase 3 (Modules):** Disable module; revert to previous module version.
- **Phase 5 (Migration):** Restore pre-migration database backup; re-attempt migration after analysis.
- **Phase 6 (Go-Live):** Revert deployment to previous version; restore database if schema changes occurred.

---

## 6. Go-Live Plan

**Timeline:**
1. **Week N-1:** Final UAT with business users; fix critical defects.
2. **Week N:** Production deployment during agreed maintenance window.
3. **Week N+1:** Post-launch stabilization (monitoring, bug fixes, user support).
4. **Week N+2–4:** Hypercare period — daily check-ins, rapid defect resolution.

**Deployment checklist:**
- [ ] Production database migrated (Phase 5 complete).
- [ ] HTTPS endpoint live (tunnel/proxy configured).
- [ ] Monitoring and logging active.
- [ ] Backup schedule configured and tested.
- [ ] User accounts created with appropriate roles.
- [ ] Operational runbook handed to company IT/admin.
- [ ] Eli signs go-live approval.

---

## 7. Post-Launch Stabilization

**Duration:** 4 weeks hypercare, followed by standard maintenance.

**Activities:**
- Daily monitoring of errors, performance, and user feedback.
- Rapid defect resolution (SLA: critical = 24h, high = 72h, medium = 1 week).
- User support via agreed channel (Telegram, in-app, or in-person).
- Weekly review of system health (database size, backup integrity, error rates).
- Collect feature requests; prioritize for next iteration.
- Document lessons learned.

**Transition to maintenance:**
- After 4 weeks of stable operation, transition to standard maintenance mode.
- Establish regular backup verification schedule.
- Schedule periodic security review (quarterly).
- Plan for dependency updates and vulnerability patches.

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Excel source data anomalies (duplicates, missing values) | Medium | High | Thorough anomaly report (Stage 3); reconcile before migration |
| External workbook links unresolved | Medium | Medium | Flag broken links; recompute consolidations from local copies |
| Zero-cost tunnel/proxy limitations | Medium | Medium | Evaluate multiple options; have fallback plan |
| User resistance to new system | High | Medium | Involve users in UAT; provide training; gather feedback early |
| Performance degradation with large data | Low | High | Performance tests with realistic data size before go-live |
| Security breach (leakage of financial data) | Low | Critical | RBAC + private accounts boundary + audit logs + security review before public exposure |

---

## 9. References

- `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (authoritative spec)
- `MODULE_MAP.md` (build order A→H)
- `MIGRATION_RECONCILIATION_PLAN.md` (migration stages, reconciliation checks)
- `DECISION_LOG.md` (D1–D26 decisions)
- `OPEN_QUESTIONS.md` (all resolved)
- `EXCEL_TO_SYSTEM_MAPPING.md` (Excel → System mapping)
- `DATA_DICTIONARY.md` (field definitions)
- `CURRENT_WORKFLOWS.md` (inferred workflows from formulas)
- `SOURCE_WORKBOOK_INVENTORY.md` (workbook inventory)
- `ENTITY_DUPLICATE_REPORT.md` (duplicate detection results)
- `C:\Users\emadg\CrossDevice\Desktop\Answers.txt` (Eli's answers to open questions)

---

> **Next action:** Complete Phase 1 deliverables (six core docs + security model + backup plan + dependency policy + pilot scope + acceptance criteria) and obtain Eli's build-start sign-off per V2 §20 before proceeding to Phase 2.
