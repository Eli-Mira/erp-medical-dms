# UQ PROPOSED ANSWERS — Draft for Eli's Approval

**Authoritative sources:** `docs/PRD.md` §10, `docs/DECISION_LOG.md` (D1–D32), `docs/OPEN_QUESTIONS.md`, `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`, `docs/TECHNICAL_REQUIREMENTS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/DATABASE_SCHEMA.md`, `C:/Desktop/Answers.txt`

---

## Proposed Answers Table

| UQ | Question | Proposed Answer | Basis (Citation) | MVP-blocker? | Needs Approval? |
|----|----------|----------------|------------------|-------------|-----------------|
| UQ-1 | Exact role list (9 roles in PRD §2) | **Keep the 9-role matrix as-is for now.** The matrix is explicitly labeled "candidate and subject to confirmation during Phase 1 user interviews" (PRD §2). D30 confirms: "exact role list" is still open. | PRD §2; D30; V2 §19 | **YES — MVP-blocker** | **[ELI APPROVAL NEEDED]** — confirm or adjust before Phase 2 auth build |
| UQ-2 | AR ledger period granularity (747 cols) | **The 747-column `العملاء` sheet is NOT a period-based ledger — it is a customer pivot layout.** Each customer occupies a ~6-column block (`الرصيد, مدين, دون, البيان, المندوب, التاريخ`). Evidence: row 2 has 48 non-empty cells spaced ~6 columns apart, matching 48 customer blocks. Columns are not monthly periods — they are per-customer attribute slots. Model: normalized `finance_ar_ledger(customer_id, entry_date, rep_id, description, debit, credit, running_balance)` (per D23). Period granularity question is resolved by data model change; no per-period column in target schema. | OPEN_QUESTIONS resolution 6a; D23; evidence from openpyxl sampling — row 2 = 48 customer name cells at columns 4,10,16… | No | No (resolved via D23) |
| UQ-3 | Averaging window for stock cover (BR-05) | **Configurable setting stored in `platform_setting` (key = `stock_cover_window_days`), default value TBD.** The spec (V2 §2B.14) states "exact averaging window must be configurable/approved." Proposed: 30-day rolling average as default; adjustable per product or company-wide. Not hardcoded. | V2 §2B.14; BR-05; DATABASE_SCHEMA §3 `platform_setting` table | Deferred — Phase 3 (Inventory module) | **[ELI APPROVAL NEEDED]** — confirm default days value |
| UQ-4 | Overstock threshold (BR-18) | **Configurable setting stored in `platform_setting` (key = `overstock_threshold`), default value TBD.** Spec (V2 §2B.15) says threshold must be configurable, not hardcoded. Proposed: configurable per-product or company-wide, default value to be confirmed. | V2 §2B.15; BR-18; PRD §A-07 | Deferred — Phase 3 (Inventory module) | **[ELI APPROVAL NEEDED]** — confirm default threshold value |
| UQ-5 | Low-stock reorder point (BR-17) | **Configurable per-product setting; no flat company-wide default unless required.** Spec confirms configurable alert; business typically sets per product. Proposed: default 0 (no auto-alert) until per-product reorder points are set in master data import. | V2 §2B.15; BR-18; PRD §A-07 | Deferred — Phase 3 (Inventory module) | [derivable from existing decision] — no specific value hardcoded |
| UQ-6 | UOM conversions (box/pack/unit) actually used? | **Discovery-gated — not included in MVP unless real operations evidence exists.** D13 and D20 confirm: box/pack/unit conversions only if real operations use them. No evidence of box-pack-unit conversion factors in the 7 workbooks (discounts observed are simple percentages, not UOM multipliers). Skip UOM conversion feature in MVP; include `master_uom` table as scaffold only. | D13; D20; Answers.txt | No (discovery-gated) | **[ELI APPROVAL NEEDED]** — confirm whether any sales are done in boxes/packs with conversion |
| UQ-7 | Specific Telegram commands and alert types for Phase 4 | **Start with read-only commands only:** `/daily` (sales + collections summary), `/balance <customer>`, `/lowstock`, `/alert <product>`, `/help`. Write actions deferred until security review. Whitelist authorized users. Source: V2 §9, TECHNICAL_REQUIREMENTS §10. | V2 §9; D6; TECHNICAL_REQUIREMENTS §10 | Deferred — Phase 4 | [derivable from existing decision] — read-only first is D6, write gated pending security review |
| UQ-8 | Exact VAT rate and rule | **Egyptian standard VAT rate = 14% (effective Jan 2024); zero-rated/exempt lines may apply to specific products.** No VAT-specific columns found in any source workbook cell values (data_only scan of all 7 workbooks returned zero matches for "ضريب" or "vat"). Proposed: configure VAT rate in `platform_setting` (key=`vat_standard_rate`, default=14.00%); allow per-product override flag in `master_product`; invoice lines store `vat_rate` per line. **Must validate against any existing printed invoices during migration reconciliation (V2 §2B.5).** | V2 §2B.5; BR-09; Egyptian tax law (2024); workbook scan — no VAT cell data found in any of 7 workbooks | **YES — MVP-blocker** | **[ELI APPROVAL NEEDED]** — confirm 14% standard rate + confirm whether any products are exempt/zero-rated |
| UQ-9 | Credit terms (payment due date, late fees) used? | **Not evidenced in current workbooks.** AR ledger shows running balance with no due-date or late-fee columns (scan of `العملاء` sheet confirmed date field is entry date, not due date). Proposed: store optional `payment_due_date` on customer/master, but do NOT enforce credit terms, late fees, or aging buckets beyond basic current/overdue split in MVP. Credit management scope minimal (D12). | D12; PRD §A-11 (credit management = limited scope); workbook scan — no due-date or late-fee columns in AR ledger | Deferred — Phase 3 (Sales/Credit module) | **[ELI APPROVAL NEEDED]** — confirm whether any credit terms/due dates are actually used in business |
| UQ-10 | Final product/project name | **No evidence of a chosen name.** Proposed: use temporary internal name "Medical Company System" until Eli provides branding. Can update UI title via `platform_setting(key='company_name')`. | PRD §UQ-10; V2 §19 (product name listed as still open) | No | **[ELI APPROVAL NEEDED]** — provide final name |
| UQ-11 | Backend framework, frontend framework, hosting OS | **Backend: FastAPI (Python). Frontend: React + TypeScript + Vite + Material-UI. Hosting OS: Ubuntu Server 24.04 LTS.** Proposal section of TECHNICAL_REQUIREMENTS recommends this stack; V2 §19 lists these as decisions still intentionally open. D21 references D19 (hosting) still open. Proposed: adopt the recommended stack unless Eli has a strong preference. | TECHNICAL_REQUIREMENTS §2 (proposal sections); V2 §19; D21; D31 | **YES — MVP-blocker** | **[ELI APPROVAL NEEDED]** — approve or suggest alternatives |
| UQ-12 | Egypt-specific regulatory compliance (tax authority, e-invoicing) | **Unknown / no evidence in sources.** V2 §10 lists "Egypt-specific regulatory obligations" as an open question; D26 notes "regulatory obligation unknown." Proposed: assume NO e-invoicing requirement for MVP unless Eli confirms. Flag for Phase 6 (go-live) legal review. | V2 §10; D26; TECHNICAL_REQUIREMENTS §14 item 12 | No (flag for Phase 6) | **[ELI APPROVAL NEEDED]** — confirm whether Egypt's e-invoicing law (ITIDA/Fatoora) applies |
| UQ-13 | Is 2FA required? | **Not required for MVP.** V2 §10 lists 2FA as open; SECURITY_MODEL draft does not mandate it. Proposed: password auth + session management only for MVP. Add 2FA in Phase 4+ if business need proven. | V2 §10; D26; PRD §A-01 (auth = email/password) | No (deferred) | **[ELI APPROVAL NEEDED]** — confirm whether 2FA is required now or can be deferred |
| UQ-14 | Approved backup destination and offsite copy method | **Proposed: daily pg_dump to local disk (30-day retention) + weekly upload to free-tier cloud (Backblaze B2) for 90-day offsite copy.** TECHNICAL_REQUIREMENTS §7 recommends this; V2 §19 lists backup destination as still open. Proposed: local + Backblaze B2; Eli can override. | TECHNICAL_REQUIREMENTS §7; V2 §19; D26 | No (configurable, non-blocking) | **[ELI APPROVAL NEEDED]** — confirm or specify preferred backup destination |
| UQ-15 | Arabic/English localization: primary language? Full RTL? | **Arabic primary (RTL default); English toggle as secondary.** All source workbooks are Arabic; company is Egyptian; PRD states "Arabic (RTL) and English (LTR) UI toggle" as acceptance criterion. MUI supports RTL natively. Hijri calendar: NOT required for MVP unless confirmed. | PRD §7 (acceptance criteria); TECHNICAL_REQUIREMENTS §13; D26 | No (built-in, not blocking) | [derivable from existing decision] — Arabic primary is clear from source evidence; English toggle is already specified in PRD |

---

## MVP Blockers Summary

These UQs block the first vertical slice (Invoice → Warehouse Stock → Customer Balance → Collection):

| UQ | Reason |
|----|--------|
| **UQ-1** | RBAC roles must be confirmed before Phase 2 auth platform build (P2.5 already started with placeholder roles) |
| **UQ-8** | VAT rate is required to implement invoice creation and line-level VAT calculation (V2 §2B.5) |
| **UQ-11** | Tech stack decision gates Phase 2 repository initialization and all Phase 3 build work |

Note: UQ-2 (AR granularity) is resolved by D23 — no approval needed; the normalized AR model replaces the wide-column assumption.

---

## Deferred UQs with Target Phase

| UQ | Proposed Answer | Target Phase |
|----|----------------|-------------|
| UQ-3 | Configurable stock-cover window, default TBD | Phase 3 (Module D — Inventory) |
| UQ-4 | Configurable overstock threshold, default TBD | Phase 3 (Module D — Inventory) |
| UQ-5 | Per-product reorder point, default = none until set | Phase 3 (Module D — Inventory) |
| UQ-6 | UOM conversions discovery-gated; scaffold only in MVP | Phase 3 (Module B — Master Data) |
| UQ-7 | Telegram read-only commands first; write gated | Phase 4 (Telegram) |
| UQ-9 | Credit terms optional; no late fees in MVP | Phase 3 (Module C — Sales/Credit) |
| UQ-10 | Internal name "Medical Company System" until branded | Phase 1 (settings) |
| UQ-12 | Assume no e-invoicing for MVP; legal review Phase 6 | Phase 6 (Go-Live) |
| UQ-13 | 2FA deferred; password-only for MVP | Phase 4+ (security review) |
| UQ-14 | Local + Backblaze B2; configurable | Phase 6 (deployment) |
| UQ-15 | Arabic RTL primary, English toggle | Phase 2 (PWA shell — already scaffolded) |

---

*This is a DRAFT for Eli's review and approval. Items marked [ELI APPROVAL NEEDED] require explicit sign-off before the corresponding phase begins. Items marked [derivable from existing decision] are evidence-based proposals that do not require a separate approval gate but can be overridden by Eli.*

---

## Review notes (Lain, 2026-10-16)

Reviewed before integration. Two points for Eli:

1. **UQ-2 is resolved by evidence, but keep it visible.** The 747-column `العملاء` sheet is a customer pivot (48 blocks × 6 cols at D/J/P/…), not a period ledger — so the normalized AR model (D23) is correct and no per-period columns are needed. Since Eli flagged UQ-2 as critical, treat it as a low-effort confirm, not a blocker.
2. **UQ-11 stack vs. existing shell.** The PWA shell already built (P2.7) is **vanilla JS** (`web/index.html` + `sw.js` + i18n JSON), not React. The React + Vite + MUI proposal would replace it. Decide: keep vanilla (faster, already working) or migrate to React (matches the TECHNICAL_REQUIREMENTS proposal). Not invented either way — needs Eli's call.

Everything else is evidence-based and correctly gated. No business rules invented.
