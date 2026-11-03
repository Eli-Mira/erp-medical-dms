# Known limitations — Beta

Updated2026-10-30. The owner accepts existing evidence for14 legacy DONE rows; add Beta labels only, no re-reconciliation. Remaining incomplete rows retain their E2E gates. A Beta label does not turn an incomplete feature into completion. FEATURE_MATRIX.md owns current counts, closure order and evidence.

## Master-data import baseline — owner160695

CORE.07 is limited to **master-data import baseline**: 5 branches and 12 products admitted, with 14 extraction rejects. Reject reporting contains reason categories and counts only: `NON_PRODUCT_ROW` 3; `MISSING_OR_INVALID_PRICE` 11. No default prices are invented. Evidence is retained under orchestration `evidence/beta3-owner-20261102/owner160695/import-native-01/` with the earlier disposable-verifier admission receipt.

**Sales, collections and balance reconciliation are not included.** This baseline does not certify VAT policy, opening balances, customer/warehouse mapping, production migration, a general staff import UI or financial reconciliation. Original workbooks remain read-only; the fresh aggregate report ran without database or network access, and prior verifier insertion is separate saved evidence.

## Financial behavior

- **Invoices cannot be posted in the normal build. POSTING_ENABLED=False stays the repo default and stays OFF in demo/hosting.** Only the owned disposable-DB test harness enables positive posting/collections/reversal for E2E evidence; actual default-config409 proof is also required. Drafts do not affect stock or AR.
- Beta remains alongside Excel, not accountant-approved real financial operation. Money is Decimal/EGP; no guessed VAT/cost/accounting mappings or unbalanced journals.
- The owner seed and14 exact C1 files are integrated in local beta checkpoint54ea1e78b7eec5eb38c32d49a59a674c8709c5ec, with29 native cases, repeat-seed and clean0021 chain evidence revalidated; SPEC/QUALITY/SECURITY PASS plus automatic LICENSE PASS. Quarantine staff browser proof is still open; this checkpoint is not full-row acceptance.

## Accepted legacy rows — Beta scope and limits

Owner accepts these existing14 rows without re-reconciliation. Each is a Beta feature alongside Excel, not production-release approval.

| Row | Beta entry / retained limit |
|---|---|
| 2B.1 — Beta accepted | Territory and source warehouse remain separate; existing routing evidence is owner-accepted, not re-reconciled. |
| 2B.2 — Beta accepted | Warehouse routing never grants user access; explicit branch grants remain authoritative. |
| 2B.4 — Beta accepted | Zero-quantity print rules retain accepted legacy evidence; physical printer and server-PDF acceptance are not implied. |
| 2B.5 — Beta accepted | Server-calculated per-line VAT uses exact amounts; production rounding/exemption policy still needs accountant approval. |
| 2B.6 — Beta accepted | Batch identities/expiry/metadata are preserved; physical inventory acceptance is not implied. |
| 2B.8 — Beta accepted | Sell-in is stored separately from customer sell-through; ordinary financial posting remains OFF. |
| 2B.9 — Beta accepted | Customer-held stock and sell-through persist online; no offline synchronization is claimed. |
| 2B.10 — Beta accepted | Online customer stock visits are accepted; offline writes, full edit CRUD and physical-device UAT remain excluded. |
| 2B.11 — Beta accepted | Sell-through is calculated and checked by server/database; no invented delivery or return mappings. |
| 2B.13 — Beta accepted | Existing representative/month/product target read/upsert scope only; territory-target UI expansion is not claimed. |
| 2B.14 — Beta accepted | Stock cover uses the configured sales window; absent sales history stays unknown, not a fabricated rate. |
| 2B.15 — Beta accepted | On-read overstock alerts use configured policy; scheduled Telegram delivery is a separate open feature. |
| CORE.01 — Beta accepted | Existing customer lifecycle/scoped UI is accepted; bulk Excel import remains separate and open. |
| CORE.08 — Beta accepted | Existing browser printing is accepted at legacy scope; no server PDF or physical-printer certification. |

## Pending Beta workflows — not accepted as-is

| Row | Current gap |
|---|---|
| CORE.03 — Beta pending | The full posting cycle and default409 now pass; draft/reopen/print browser proof, visible Beta labeling and final source-bound review/commit are still open. |
| CORE.04 — Beta pending | The partial/final collection/void/AR cycle and ordinary409 now pass; staff balance/history browser proof, Beta labeling and final review/commit remain open. |
| 2B.7 — Beta gate verified | Real near-expiry filter, exclusions, scoped roles, reload, empty/error/recovery and Arabic/English mobile/desktop paths pass the contained browser gate. This is read-only warning/filter functionality, not an inventory write workflow or physical-device acceptance. |
| CORE.05 — Beta gate verified | Real sales/collections/AR/stock KPIs, explicit report date, drilldowns, scope and error/recovery pass the contained browser gate. Only supported metrics are displayed; normal invoice/collection posting remains disabled. |
| CORE.10 — Beta pending | Final canonical-seed contained/local E2E and applicable final-source reviews remain open. Public HTTPS is explicitly Phase2 step3, not a Beta prerequisite. |
| 2B.17 — Beta accepted | Real UUID product links can be selected, saved and reopened; pending lookups preserve current selection. Single-browser duplicate-submit protection only; cross-client persisted idempotency is excluded. Final SPEC/QUALITY/SECURITY PASS and integrated source-bound tests accepted. |
| 2B.16 — Beta accepted | Current authorized owner/finance/sales-manager create/edit/reopen spend with existing scope and exact Decimal strings; finance doctor-reference denial is preserved rather than widened. Null-reference scope retains prior semantics. Actor audit is atomic. Final SPEC/QUALITY/SECURITY PASS and integrated source-bound tests accepted. |
| 2B.18 — Beta accepted | Real objective/KPI/result/follow-up create/edit/reopen, per-kind list/detail generation guards and session teardown are tested. Spend and objective remain separate transactions; no fabricated ROI or persisted ABA-proof revision. Final SPEC/QUALITY/SECURITY PASS and integrated source-bound tests accepted. |
| 2B.3 — Beta accepted | Confirmed owner and finance can create exact batched transfers, see both balances and reopen history. Metadata/actor audit and no sales/AR effects are verified. Existing warehouse_staff catalog-reference denial is preserved; this role has no new form access. No backend permission widening, persisted cross-client idempotency or new stock policy. Catalog choices are limited to500 active products and the history view to the latest50 transfers. |
| CORE.02 — Beta gate verified | Confirmed active owners can create with explicit exact price/VAT, edit names, search, soft deactivate/reactivate and reopen. Existing staff catalog access is unchanged; staff maintenance rights, later price/VAT editing, tax-policy expansion and physical-device acceptance are excluded. |
| 2B.12 — Beta quarantine intake | Owner/finance and permitted sales-manager intake creates an audited quarantined return, with typed UUID/date/exact quantity validation and no saleable-stock, invoice or AR effect. Non-global managers require assigned customer territory AND separately granted owned warehouse; global inventory roles retain their existing reads. Existing district-manager/auditor history is reachable without create access. Warehouse staff retain backend history/intake permission but the master-reference catalog still denies their PWA create form; no catalog permission is widened. No approval, release, refund or financial settlement is included. Catalog selection is limited to500 active products; history uses existing offset pagination. Unknown writes remain locked in the same tab across logout/reload until reconciled; there is no shared server/cross-client idempotency key. Final independent review and integrated acceptance are tracked by the orchestration receipt, not implied by this limitation entry. |
| CORE.06 — Beta gate verified | Existing owner authority maintains current users' roles, activation and branch grants with atomic audit and session revocation; self-lockout/last-owner guards remain. No account provisioning, passwords, owner-flag/transfer or territory editing. Concurrent race drills remain hardening work; unchanged self-save currently signs out locally and the save notice can overstate a no-op's audit/revocation. |
| CORE.09 — Beta pending | The 13 shallow unit tests pass, but SQL targets the wrong schema, signed group IDs are dropped, /help crashes, and role scope/read-only DB/log safety/live service proof are absent. |
| CORE.07 — master-data import baseline | 5 branches and 12 products admitted; 14 rejects reported by category/count only. Sales, collections and balance reconciliation are not included; no general import UI or production/accounting approval is claimed. |

## Demo and external services

- C2 reuses owner seed86d369759343873a24441a2f5847521068a6e8ab, not a replacement seed. Native admission has29 passes, equal repeat-seed digest/counts, one0021 head with up/down/up, and a real-HTTP scenario whose normal invoice/collection writes return409. Same-source evidence is retained in checkpoint54ea1e78b7eec5eb38c32d49a59a674c8709c5ec; the full ERP/workbook suite is not claimed.
- Public/demo data must be freshly synthetic. No original workbooks, company/customer data, Git history, env files or credentials enter public/model packets. C9 original-data reconciliation stays local/read-only/aggregate-only.
- Telegram's13 original config/template tests pass in isolation, not live. Real-schema scoped UUID queries, signed group IDs, /help, a real read-only DB role, safe logging and private/group live tests remain open. Only the NEW token privately provisioned in the env file may be runtime-loaded; token values and token-bearing URLs must never reach console/logs/prompts.
- Hosting Beta closes with contained/local E2E plus applicable SPEC/QUALITY/SECURITY and automatic LICENSE gates. Public HTTPS, public access-gate/rate-limit checks and opening the tunnel remain Phase2 step3; the owner decides the domain. No tunnel is opened for Beta closure.

## Browser-test readiness — owner-authorized hardening

Owner classification: "pre-existing flaky readiness race, 1 of 120 on both the pre-repair and the repaired tree, not a regression from the privacy fix; mechanism not proven."

**Native count correction:** the retained 20-repetitions-per-variant comparison is **119 passed / 1 failed of 120** on pre-final-repair executable source and **120 passed / 0 failed of 120** on staged tree `124efb0c45eb1fa0eb643b9aed501405c7168034`. The earlier merged full suite separately had 1114 passes / 1 failure of 1115; it was not a 120-case run. Thus the quoted "1 of 120 on both" is not a measured result. Two callback probes each passed 120/120 without capturing the empty-list interval. This is owner-authorized defensive fixture hardening, not proof of a mechanism or a new product repair. The pre-existing failure means a regression from the privacy fix is not established.

The test now waits on the actual held-route list, explicitly asserts interception, and waits for enabled controls; it uses no `networkidle` or sleeps. Existing privacy assertions, client-consumption barriers and frozen oracles remain unchanged. Evidence: orchestration `evidence/beta3-owner-20261102/owner163704-causal-sequence-01/CAUSAL_INTAKE_02.json`. A further failure parks this single test with its reason under the owner's disposition, rather than starting another causation cycle; excluded coverage must remain explicit in release receipts.

## Scope and proof limits

- Expiry/dashboard receipt: orchestration evidence/speedup-20261030/ui-browser-05 (33/33 real-HTTP/PG/browser cases, Arabic/English at390/1440); ui-roles-green-01 adds15/15 contained function controls, including the unchanged backend-role boundary. Earlier failed harness attempts remain preserved. Final source-bound review/commit is tracked in the orchestration board, not inferred from this table.

- Product/roles integration proof: product56 focused,75 neighboring PostgreSQL regressions and8 browser cases; roles41 focused,44 neighboring regressions and6 browser cases, all passing on the integrated Beta source. Counts are separate compositions with overlap, not one full suite. Independent product combined review and roles SPEC/QUALITY/SECURITY pass; automatic LICENSE checks pass. Evidence:orchestration evidence/speedup-20261030/products-roles-integrated-composition-01/. Dynamic product labels need refresh after a live language switch. Full Phase2/physical-device/public-hosting approval is not implied.

- Accepted Beta screens must visibly show **Beta**. The14 legacy DONE rows' existing evidence is owner-accepted; labels only, no re-reconciliation. No PARTIAL row is accepted by changing its label.
- Browser emulation is not physical-device acceptance. Existing zero-quantity source assertions are not print-media/output proof; browser print is not server-PDF support. Online PWA evidence is not offline write/sync.
- Dashboard Beta reuses genuine supported sales/collections/AR/stock-alert KPIs; no fabricated profit/ROI. WhatsApp, OCR/new server-PDF dependencies, deferred history cleanup and generic post-beta hardening are not silently included in the28-row milestone.

- Marketing accepted Beta proof:28 focused/50 neighboring real-PG controls,6 ordinary browser cases and10 genuine held-response browser regressions, all passing on source03 and the integrated Beta source. Failed reviews01/02, async RED02 (0/10) and12 U+0000 create/update assertion failures remain preserved. NUL input now receives422 before SQL with unchanged business/link/audit rows. Three source-bound independent reviews PASS; this is scoped Beta acceptance, not a full-suite claim. Arabic390/English1440 application/session tests disable service workers; no installed-PWA/offline/device acceptance. Async selection, type/open ordering, refresh/save and old-owner-success after scoped login are exercised.

- Transfer candidate proof:13 contained Node controls,57 neighboring real-PG tests and13 combined HTTP/browser cases (12 owner/finance AR390/EN1440 browser cases plus one HTTP-only warehouse-role catalog-denial control). Earlier fixture failures01/02 are preserved; they do not approve a warehouse-staff PWA workflow. Unknown write results keep a browser-session pending lock and require reconciliation, not blind retry. Separate browser sessions still lack a shared idempotency key. No full-suite/physical-device/public-hosting claim.

- Accepted transfer repair: the raw review01 included a real populated-session teardown defect despite failing the manifest intake schema. Both desired logout controls failed before the fix, then passed unchanged after transfer references, form data, history, balances and notices were cleared at session end. Pending markers and uncertain-outcome locks survive teardown. Integrated Beta evidence:13/13 Node controls,57/57 neighboring PG controls,15/15 combined HTTP/browser controls including both real-logout cases; marketing session-retention10/10. Corrected full-manifest combined review02 PASS, no fallback approval used. Live language switching still needs screen refresh for composed labels. Not a full-suite, warehouse-staff browser, device or public-hosting acceptance.

- Returns candidate evidence:15 contained handler controls,30 real-PG/API validation/scope cases,93 neighboring PostgreSQL regressions and18 real-HTTP/Playwright cases. Browser journeys cover Arabic390/English1440 owner/finance intake, actual reopen/reload, SQL quantity/actor/audit/no-financial-side-effect checks, consumed held-body logout/account-switch isolation and a credential-free ambiguous-write lock across reload. These overlapping groups are not a full-suite total; no physical-device, offline, public-hosting or warehouse-staff PWA-create acceptance is claimed. Earlier failed source/oracle/fixture runs remain preserved; final review/integration must bind the exact source and tests.
