# Progress Checklist — Medical Company System

## I1 combined local integration — 2026-10-26

- Current owner authority is the I1 master execution directive; it supersedes old active harness/next-feature pointers below for this candidate only. Worktree `C:/Projects/ERPWorktrees/erp-i1-20261026`, branch `integration/erp-i1-20261026`, accepted H1-free S1 base `69d68499fe67919b61fb97e96ad69fd33b27af37`.
- Inherited customer/supplier/contact/privacy features plus inspected feature-only S4 posted-sales, inventory-alert and D28 deltas are integrated without S4 ancestry. Supplier boot guard and derived REAL_VIEWS registry coexist. No original feature worktree was edited.
- Reproduced/fixed settled-customer counting, failed-summary audit atomicity, imported-report logout/late-response isolation and warehouse-login/reference races. Seven original contact privacy tests remain unchanged. Focused final preparation passed 40/40; this is not a substitute for the complete combined final gate.
- Canonical scope/limits: `docs/I1_INTEGRATION_ACCEPTANCE.md`. Final full native gate `i1_full_asof_final` (after the localized as-of-label RED/GREEN correction) (all cases, normal assertion rewriting, owner-approved 1 GiB verifier only), independent exact-byte review and local commit are valid only through matching records under `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/erp-i1-20261026/`. Do not infer acceptance from earlier S1/S4 counts or this preparation entry.
- H1 remains NOT ACCEPTED; scheduler/posting OFF; no company database/resource changes, original workbook writes, protected dependency/configuration edits, S2/FreeLLMAPI private-source delegation, push, protected merge or deployment. Stop for owner I1 acceptance before any protected integration.

## Customer contact maintenance — S1 isolated slice, 2026-10-25

- Owner authority: S1 customer-contact delivery directive `pasted_content_2026-10-25_11-33-10-789_c4c010.txt`; worktree `C:/Desktop/ERPWorktrees/customer-contacts-20261025`, branch `feature/customer-contacts-20261025`, accepted parent `cef937b3a2d1ecb83370a4977b3f8998339d9f12`; no rejected H1 ancestry.
- Approved field contract: DATABASE_SCHEMA master_customer (`contact_phone varchar(30)`, `address text`), PRD B-01, APP_FLOW B1. One optional phone string and one optional written address, not multiple-contact tables; no international-only pattern, uniqueness, canonicalization or branch/territory reassignment. Omission preserves; explicit null/empty/outer-whitespace clears contact values to NULL. Names retain the B-01 contract.
- Additive `0016_customer_contacts` migration; existing GET/POST/PATCH plus actor-bound, row-locked atomic old/new audit. Unchanged writes do not audit; invalid/forged fields and inactive/unauthorized sessions cannot write. Populated-contact downgrade refuses data loss.
- Existing vanilla PWA gains labeled phone/address inputs and read-only directory columns, using existing translations/styles. Contact-only edits preserve legacy blank names; save/retry/cancel/single-flight, Arabic/English, desktop/mobile and invoice-choice behavior use the actual persisted API.
- Focused contained evidence: 127 API/B-01/lifecycle controls pass; 52 real browser controls pass (new contact cases plus retained customer/supplier coverage). Intended missing-field and legacy-name REDs, a selector ambiguity and a wrong old test filename remain preserved; these are not full-suite/release acceptance claims.
- The first full `contact_full_chain` run is retained as **690 passed / 4 Chromium page-crash failures**, not accepted or classified as definitely unrelated. New contact HTTP fixtures were then given exact disposable-branch/territory cleanup of their mutable synthetic customer rows while retaining immutable audit events; the unchanged contact backend + existing lifecycle-browser composition passed **67/67**. No original assertion, container limit or application behavior was relaxed; a lower-level renderer/OOM cause is not asserted.
- The second full run likewise retained 690/4: fixture cleanup alone did not resolve the browser failures. A bounded 200-customer native reproduction then recorded container `memory.events` OOM kills at the unchanged 512 MiB cap. The product correction bounds table DOM to 50 rows with Previous/Next and per-user tab-session page recall; full authorized API data and active invoice choices are not truncated, and confirmed mutations reveal the customer's page. The unchanged two-case large-directory lifecycle reproduction subsequently passed with zero observed OOM kills. Stronger paging/readback controls remain in `tests/test_contact_render_probe.py`; all earlier failures are retained.
- `contact_full_paged` subsequently passed **696/696** with complete native/wrapper source/workbook/config preservation, fresh migration up/down/up and verified UUID DB/container removal. This is the pre-privacy-correction snapshot, not the final checkpoint. A separate real account-switch browser RED proved old-owner contact leakage to an unassigned finance user after a failed directory refresh. Logout now clears customer caches/forms/choices; directory refresh removes stale rows first and ignores responses from an earlier session; customer mutation completions are session-bound. Integrated contact/privacy coverage passed 18/18, followed by two explicit failed-refresh/late-owner-response privacy controls passing 2/2. Final acceptance includes both new privacy cases.
- The privacy-corrected full snapshot `contact_final_privacy` passed **698/698** with complete cleanup/preservation. Before review, a real two-connection PostgreSQL diagnostic also exposed a write window between the downgrade populated-data check and column removal (intended RED). One `ACCESS EXCLUSIVE` table lock now covers check/removal; the unchanged diagnostic passed, and the integrated 53 contact/backend/migration plus 2 privacy cases passed **55/55**, including fresh up/down/up. This last migration safety correction and its durable regression are included in the final exact-source gate; earlier green snapshots are preserved, not relabeled.
- Bounded S1 recovery revalidated the preserved `contact_final_locked` snapshot (**699/699**) rather than restarting development. Five additional privacy controls exposed four genuine gaps: expiry did not clear contacts, logout waited for a stalled request, and late startup success/error could restore prior customer choices or invalidate the newer account. Current-session 401 responses now invoke shared local teardown; logout clears locally before awaiting the server; startup data/completions/errors are token-bound. The unchanged revised RED privacy module then passed **7/7** (including both original account-switch controls). The first diagnostic attempt also retained two selector/synchronization errors, corrected before the definitive RED; those are not application failures. The final recovery gate includes all 699 prior controls plus these 5, requires one independent review, and stops after the local checkpoint.
- Final exact-source full migration/regression verdict, independent SPEC/QUALITY/SECURITY review and local commit are bound by `review-packet/manifest.json`, `review/validated-verdict.json`, `COMMIT_RECEIPT.json` and `CHECKPOINT.md` under `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/customer-contacts-20261025/`. A missing or mismatching gate artifact is not acceptance.
- H1 remains NOT ACCEPTED; ERP scheduler/posting OFF. No company DB connection, workbook/protected-config edits, unsafe importer, other-session source writes, push, protected merge or deployment.

## Customer lifecycle — S1 local delivery, 2026-10-25

- Owner authority: the S1 continuous-delivery directive and immediate-recovery directive (`pasted_content_2026-10-25_07-58-11-296_78e520.txt`), superseding the older harness-first pointer below for this isolated feature only.
- Worktree: `C:/Desktop/ERPWorktrees/customer-creation-20261025`, branch `feature/customer-creation-20261025`, based on accepted B-01 `34ee1f12c418a6ca31889a59ced9d4db5bd8d0fe`. Rejected H1 `d39788ec` is not an ancestor. Accepted supplier UI hunks from `48d4d8b` are integrated as file-specific changes, not a merge of controller ancestry.
- Basic customer lifecycle: owner-only create, name editing, soft-deactivation/reactivation; required code/Arabic name/existing branch/existing territory; duplicate-code prevention; assigned-territory reads; active-only invoice choices; historical invoice/AR/stock preservation; atomic actor-bound audit and idempotent/no-op handling. No contact/credit-policy expansion or new schema migration.
- Real vanilla PWA: Arabic/English customer form, protected identity/reference fields during name edits, confirmation, single-flight writes, recoverable validation/reference failures, refresh persistence, and desktop/mobile browser checks.
- Native final stage `customer_full_after_review_fix`: **625 passed, 0 failed/errors/skipped**, 319.12s; fresh disposable PostgreSQL, migration up/down/up to `0015_private_accounts`, default posting OFF, source/config/seven workbooks unchanged, UUID database removed. This is local feature/regression evidence, not production or H1 acceptance.
- Append-only private evidence: `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/customer-lifecycle-recovery-20261025/`. Initial independent review `review/validated-verdict.json` returned FAIL on stale invoice choices after a successful deactivation plus failed readback; a native browser regression reproduced it, then passed after the correction. Exact final corrective review and commit disposition are bound by `review-corrected/validated-verdict.json` and `COMMIT_RECEIPT.json` there; a passing test count alone is not review acceptance. Earlier failed candidate/test-fixture/browser captures remain preserved.
- H1 remains NOT ACCEPTED; scheduler and production posting remain OFF; quarantined `medical_dms`, source workbooks, protected config, other sessions and publishing are outside this feature's write scope.

## Active owner request — 2026-10-21: autonomous-development integration (IN PROGRESS)

The owner's latest directive is `pasted_content_2026-10-20_22-57-47-588_741e7a.txt` plus the explicit request to implement a permanent opt-in workflow, not merely document it. Finish this integration before resuming the older next-feature pointer below.

- Implemented project-owned core at `tools/autonomous_development.py`, `tools/autonomous_plugin/{__init__.py,runtime.py,plugin.yaml}` with tests in `tools/autonomous_tests/test_mode.py`. It reuses native Kanban SQLite/claims/review runs, denies unregistered tools and out-of-scope/protected files, keeps reviewers read-only, gates local Git checkpoints on frozen passing results and a separate review run, persists a three-failure budget, and uses locked generation-checked atomic state writes.
- **Safety gates:** `safety_check()` verifies frozen source provenance (HEAD vs locked base commit), approved python3 interpreter, safe verification recipe, and protection gates (POSTING_ENABLED OFF, protected files intact). `setup` command binds the result to `setup_check.provenance` and `safety_ready`; it cannot be manually True.
- **Activation guide:** `docs/AUTONOMOUS_DEVELOPMENT_ACTIVATION.md` documents the full activate/deactivate workflow (setup → verify → enable → daemon → add task).
- **Native persistent continuation:** `daemon_loop()` runs `continue_flow()` at the configured cadence, handles SIGTERM/SIGINT, and persists state atomically. Exposed via the `daemon` CLI action.
- **Real ERP verifier integration:** `verify()` for `kind: erp` runs `scripts/verify_invoice_cycle.py --chain -- tests/`, asserts exit 0 and source bindings unchanged, then validates the resulting `run.json` against the `erp_record_passed()` predicate. Non-ERP tasks run the native unittest suite.
- **Current native evidence:** `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/autonomous-core-20261021-034025/`. Fourteen synthetic native SQLite/Git/process/SDK tests passed in 49.216s; actual process-tree interruption invalidated prior GREEN and resumed correctly; scoped Ruff direct 0/zero diagnostics and native plugin doctor direct 0. The existing 429-pass ERP record was only saved-artifact revalidated by the new receipt predicate, **not a new PostgreSQL execution**. Source hashes before/after matched.
- Native shell-hook subprocesses intentionally scrub worker task/run identity. The rejected transport remains fail-closed; the implementation instead uses the supported in-process plugin hook and supervised verification tool. Do not remove the delegated-child fence or change Hermes core to make subprocess hooks privileged. Tool restrictions are **not an OS sandbox for hostile test code**.
- **Independent core review pending:** `deleg_0be52dd8` / `sa-0-6cd6668a`; reviewer output target is `CORE_REVIEW.json` alongside the above evidence. These five candidate source/test/manifest files are frozen until intake. Parent must verify the actual artifact and hashes, not accept a self-reported verdict. The earlier finite-validation review has been received and dispositioned below; it is not an active waiting/re-review task.
- **NOT ACTIVATED / NOT COMMITTED.** Next integration work: trusted source-bound setup/activation adapter, explicit approved ERP interpreter and real recipe verification, free main/fallback/auxiliary route checks, and native script-only persistent cron admission/continuation with activation/deactivation guide. `safety_ready` must not be manually set merely to bypass activation. Preserve current profile settings and all ERP boundaries. No live worker path, scheduler job or automatic provider spending is certified by the unit tests. OpenCode scoped coding remains blocked; text smokes do not clear it.


## Active execution checkpoint — 2026-10-21

- Branch: `fix/finite-values-20261021`, created from verified base `38a3584dbbdfbb27b4597b805dbc8e7583e8c3bb`. Existing untracked router scaffolding, graph output, `nul` and earlier evidence were preserved.
- Implemented finite-number rejection before comparison/SQL in returns, transfers, marketing spend and private debit/credit. Twenty new parameterized API regressions assert HTTP 422 and no domain/audit writes; existing healthy controls remain.
- Actual test-first records: each endpoint captured intended HTTP-status RED before its guard, followed by covering GREEN. Final-source full runner `finite_full_bound_20261021`: **429 passed, 0 failures/errors/skips**, 71.93s; fresh migration plus empty down/up, default posting OFF, task DB removed and all test-run bindings unchanged.
- Parent revalidated all ten retained test stages, raw log/JUnit hashes, 18/18 matrix rows, seven unchanged workbooks and 132 unchanged non-task bound inputs. Scoped project-cwd Ruff: direct exit 0, zero diagnostics. Review package: 8 files/12 hunks, exact patch replay and final-source hashes verified.
- **Finite gate disposition:** independent current-code SPEC/QUALITY/SECURITY judgment received; qualified parent intake accepted the exact eight-file source checkpoint. Commit `7b7bd64db4588bd6fc2dd7c7e10f6d72f2341c9f` contains only those reviewed/tested files. The reviewer used 34 individual calls against 24 and performed forbidden mechanical/scratch work; its unqualified method certification is NOT accepted. Append-only proof: `docs/evidence/engineering-harness/20261021-v2/{FINITE_REVIEW_INTAKE.json,FINITE_COMMIT.json}`. `FINITE_VALIDATION.json` remains an immutable pre-review snapshot, not an active pending gate. No whole-release/production approval.
- **OpenCode scoped coding POC: BLOCKED**, not substituted with the earlier three successful text smokes. Native agent discovery failed in an isolated fixture; bounded supported API diagnostic also found no custom agent. No unrestricted ERP worker was launched. Exact disposition: `docs/evidence/engineering-harness/20261021-v2/OPENCODE_POC.md`.
- **Next ready task after review/checkpoint:** exercise destination batch metadata conflicts during warehouse transfers; preserve manufacture/expiry metadata instead of silently merging differing batches. Source inspection only so far; no second task source changes yet.
- Quarantined DB, production posting, source workbooks, protected config, publication/deployment and real-chat restrictions are unchanged. Updated capability/backlog matrix: `docs/SPEC_COVERAGE_MATRIX.md`.


## Current checkpoint — 2026-10-17 (supersedes older gate/stack summaries below)

- [x] Eli authorized Invoice Slice 1 and continued Piece 2. Approved stack: **FastAPI + PostgreSQL + psycopg3 + existing vanilla JS/PWA** (D34–D37). Hosting OS remains deferred; no React rewrite.
- [x] Piece 1 schema/calculation baseline: commit `5cb375a` (25 tests then). This is not the complete Invoice Module.
- [x] Piece 2 create/view/replace Draft/void Draft API, territory/role controls, audit and duplicate/version/input validation: `app/sales/{router,repo,schemas}.py`; `tests/test_invoice_api.py` and `tests/test_invoice_boundaries.py`. Committed as `6b6f628`.
- [x] Applied additive migration `0004_invoice_drafts`; minimal territory/warehouse/batch references and API + database posting block. No stock/AR module was built.
- [x] **Inventory Slice 1 (Module D)**: migration `0005_inventory_stock` adds the append-only `inventory.stock_movement` ledger and `inventory.stock_balance` running total per warehouse/product/batch, with atomic movement application and role-gated API (`app/inventory/`). 41 new controls; details in `docs/INVENTORY_SLICE.md`.
- [x] **Receivables (AR) Slice 1 (Module E, AR half)**: migrations `0006` (`platform.user_branch` mapping; posting gates relaxed to require `posted_at`; `posted_by`) and `0007` (`finance.ar_entry` ledger); AR service + role-gated API; and `app/sales/service.py::post_invoice_atomic` — the tested Invoice → Stock → AR transaction. Details in `docs/AR_SLICE.md`.
- [x] Parent native full-suite run: **162 passed**, no failed/skipped cases; raw log/JUnit/runtime/source-hash bindings under `docs/evidence/ar-slice1/final-run/`. Fresh empty database migrated `0001→0007`, downgraded to `0005`, re-applied, then passed the suite: disposable DB removed and absence verified.
- [x] Strict application-vs-Excel comparison: **133 numeric rows** across two complete named transaction sheets, no mismatch skipping; all 7 workbook hashes preserved. Exact coverage/limits: `docs/INVOICE_SLICE_1.md`.
- [x] Scoped inventory review delivered: no blocking code findings. Parent revalidated final hashes/cases and accepted the inventory repair. Reviewer read-only/budget deviations are preserved and its unqualified method certification is **not accepted**; terminal disposition in `docs/evidence/inventory-authorization/VERIFICATION.md` (not a pending re-review loop). Full-system security/release approval remains open.
- [x] Sales routing prerequisite: decoupled invoice sales branch from source-warehouse owner branch. Migration `alembic/versions/0009_sales_source_warehouse.py` (renames `invoice_prepare`/`fk_invoice_warehouse_branch` composite FK), router `_prepare` scope/route guard, `tests/test_invoice_routing.py` (Sharqia/Gharbia source-warehouse scoping). Commit `c50bb02` [skip-ci]; verification evidence committed `2b46e6f`; disposable FK chain: 0009 accepts cross-branch invoice, 0008 rejects; 189/189 tests pass on disposable DB, sources unchanged, DB dropped. Reviewer method deviations preserved, unqualified certification not accepted.
- [x] Posting gate: default-OFF flag `POSTING_ENABLED` (`app/config.py`), `POST /invoices/{id}/post` returns HTTP 409 while OFF and delegates to `app.sales.service.post_invoice_atomic` while ON; committed `ac596eb`. Activation needs explicit approval. **Posting is still HTTP 409 every day; no flag enabled.**
- [x] Inventory authorization repair: `platform.user_branch` resolves actual active warehouse IDs via ownership; managers read only; invoice-backed movement details require invoice branch + territory grants. Shared-route mappings never confer whole-warehouse permission. Native **182 passed** (20 new authorization cases); disposable chain `0001→0008`, down/up, **182 passed**, DB removed. RED/GREEN/final bindings: `docs/evidence/inventory-authorization/`. This corrects the false `893a0d9` completion report; see `docs/INVENTORY_SLICE.md`.
- [x] **Invoice → Stock → AR → Collections local API/test slice:** verified code/evidence commit `d233893425bc23df9d344bd9e0b88c6f501b4828`. Independent current-code SPEC/QUALITY/SECURITY PASS with qualified parent intake; fresh candidate and post-integration full suites **315 passed each**, no failures/errors/skips, unchanged source/config/Excel and removed disposable databases; scoped 17-file Ruff clean. Posting/reversal/collections/receipt void stay OFF outside isolated tests. No active reviewer/implementation queue; old NO_VERDICT and historical worker boundary/evidence-loss rejection are preserved, not reopened or retrospectively certified. Exact proof: `docs/evidence/invoice-cycle/finalization-20261018/{FINAL_ACCEPTANCE.md,REVIEW_INTAKE.md}`.
- [x] **B Master Data slice (local-only):** migration `alembic/versions/0011_master_data_b.py` adds the three confirmed-but-missing references — `master_data.master_supplier` (PRD B-02/G-01), `finance.coa_account` (PRD B-12/E-05, no seeded accounts), `marketing.marketing_kol` (PRD B-13, D22) — plus read-only role-gated lookups `GET /master/suppliers|accounts|doctors` (doctors branch-scoped via `platform.user_branch`). UOM stays gated (D13/D20); no CRUD/import writes; synthetic test data only. Verification: disposable DB migration up→down→up and full suite, sources unchanged, `POSTING_ENABLED` OFF. Decision record: **D39** in `docs/DECISION_LOG.md`; report + artifacts under `docs/evidence/invoice-cycle/<stage>/`.
- [x] **Client prototype (local-only, synthetic demo):** branch `feature/client-prototype` cut from `de41f42` (the `e413f68` invoice UI ancestry was verified first). `scripts/make_demo.py` builds the isolated `medical_demo` DB — 100% synthetic, `DEMO-`-prefixed, totals via `app.sales.calc`, demo accounts `demo_owner`/`demo_rep`/`demo_finance` (`Demo-2026`). PWA gains an Arabic-RTL dashboard plus read-only المخزون / أرصدة العملاء / التحصيلات views over the existing GET APIs; `POSTING_ENABLED=false` at all times; drafts are presented as paperwork only and the posting refusal (409) is demonstrated live, never simulated. Actual browser flow verified end-to-end (login → draft save with authoritative server totals → post gate → stock/balances/collections unchanged). Fixed a latent pre-existing defect: `newDraft()` reset cleared the boot-filled invoice date (422 on every fresh save). Regression: **345 passed / 0 failed** (runner stage `client-proto-20261018`, `unchanged: true`, DB removed). Walkthrough + credentials + limitations: `docs/CLIENT_DEMO.md`; proof: `docs/evidence/invoice-cycle/client-proto-20261018/SUMMARY.md`.

- [ ] **Default local `medical_dms` recovery requires approval:** worker applied an old 0010 and left stamp/schema drift. No parent recovery writes; do not run/deploy this branch against that DB. Proposed forward-only write set and confidential-backup classification: `docs/evidence/invoice-cycle/finalization-20261018/UNBLOCKING.md`. This is separate from the completed local source checkpoint; production activation remains forbidden.
- [ ] Private GitHub publication **BLOCKED**: no remote and gh CLI unauthenticated. Read-only Gitleaks/history scan covered 20 commits/223 unique historical blobs plus current milestone content (439 independent content scans); credentialed development DB URLs and tracked Excel-derived samples need cleanup/clearance before first push. No binary workbook payload found; 316 SHA-256 metadata alerts were false positives, not secrets. No source/history rewrite, repository creation or push. Scope/triage: `docs/evidence/invoice-cycle/finalization-20261018/GITHUB_GATE.md`.
- [ ] Payroll formula remains **UNVERIFIED**; the header-structure test is not salary-formula validation. Stock thresholds and other deferred UQs stay deferred.

The older phase items below are historical records, not renewed claims that the complete platform, mapping, schema or production gate has passed.


> **D29 rule (Eli):** a task is ✅ only when evidence is attached — a file path,
> terminal output, or hash. No empty checkmarks. We never assume something is
> done without verifying it really exists and is fully implemented.

Legend: ⬜ todo · 🔄 in progress · ✅ done · ⛔ blocked · ⏭️ gated/delayed

---

## Phase 0 — Discovery  [gate: ✅ complete per D26]
- [✅] Inventory 7 workbooks + sources → `docs/SOURCE_WORKBOOK_INVENTORY.md`
- [✅] SHA-256 verify sources immutable (2026-10-16, all 7 match baseline) → `docs/SOURCE_HASHES.txt` + `sha256sum *.xlsx`
- [✅] Resolve open questions Q1–Q3 → `docs/OPEN_QUESTIONS.md`
- [✅] Sheet→system mapping with citations → `docs/EXCEL_TO_SYSTEM_MAPPING.md`
- [✅] Current workflows from formulas → `docs/CURRENT_WORKFLOWS.md`
- [✅] Reconciliation approach → `docs/MIGRATION_RECONCILIATION_PLAN.md`
- [✅] Cross-workbook sheet-name duplicates report (86) + placeholders (53) → `docs/ENTITY_DUPLICATE_REPORT.md`
- [✅] Data dictionary → `docs/DATA_DICTIONARY.md`
- [✅] Excel feature catalog → `docs/EXCEL_FEATURE_CATALOG.md`
- [✅] Migration map (sheet→module) → `docs/MODULE_MAP.md`
- [✅] Decisions + evidence resolutions D1–D26 → `docs/DECISION_LOG.md`
- [✅] Phase 0 gate cleared — sources untouched, all questions resolved against evidence.

## Phase 1 — Planning & Architecture  [gate: ✅ build-start approved 2026-10-16]
- [✅] `docs/PRD.md` (390 lines) — roles, BR-01–BR-25, 15 open Qs
- [✅] `docs/TECHNICAL_REQUIREMENTS.md` (555 lines) — stack pending approval (D21)
- [✅] `docs/APP_FLOW.md` (738 lines) — flows A–H, 9 roles, mobile stock-visit
- [✅] `docs/DESIGN_BRIEF.md` (371 lines) — bilingual RTL, print rules
- [✅] `docs/DATABASE_SCHEMA.md` (308 lines) — 25 entities, E=C×(1−D), AR normalized, 40-row mapping
- [✅] `docs/IMPLEMENTATION_PLAN.md` (422 lines) — 8 phases, 7 gates, 11-stage migration
- [✅] Build-start gate: Eli approved 2026-10-16; stack = FastAPI/React/PostgreSQL/CF (pending swap).

## Phase 2 — Platform Foundation  [gate: 🔒 platform readiness]
- [✅] P2.1 Initialize git repo → commits `c5feebb`, `bd7b067`, `1fc5e97` (7 workbooks excluded from git)
- [✅] P2.2 docker-compose.yml (postgres:16 + app) + Dockerfile + .env.dev → committed
- [✅] P2.2b App boots: FastAPI `/health` → HTTP 200 {status:ok, phase:platform-foundation} (TestClient smoke)
- [✅] P2.2c DB reachable: `med_dms_db` healthy; `pg_isready` accepting connections
- [✅] P2.2d Initial platform schema applied: alembic rev `0001_platform` (head); tables `platform_user`/`platform_session`/`platform_setting` verified via `psql \d platform.platform_user` (uuid PK gen_random_uuid(), username UNIQUE, is_owner/is_active, timestamptz now()) — matches DATABASE_SCHEMA §2
- [✅] P2.3 Alembic scaffold + initial schema → `alembic/`, `alembic.ini`, `alembic/versions/0001_platform.py`
- [✅] P2.12 README local-dev setup → `README.md` (committed)
- [✅] P2.4 Auth module: login/me/logout + bearer sessions (24h TTL), INET-validated IP (TestClient "testclient"→NULL). 4/4 tests pass (438205b). app/auth/{router,repo,security,db}.py + tests/test_auth.py
- [✅] P2.5 RBAC: private/owner boundary — /owner/panel via require_owner; non-owner → 403, owner → 200. 6/6 tests pass. app/auth/rbac.py + tests/test_auth.py (D10).
- [✅] P2.6 Audit logger: immutable audit_log + log_audit(); login/logout audited. psql \dt audit.* → audit_log,reason_code; 2 rows (login+logout) verified (438205b). repo.log_audit; alembic 0002_audit_log
- [✅] P2.7 PWA shell: static shell served at /app (manifest+icon+sw.js cache-first), RTL index (dir=rtl/lang=ar), ar/en i18n key parity. 10/10 tests pass. web/ + tests/test_pwa.py (React SPA deferred).
- [⬜] P2.8 System settings scaffold (fiscal year, VAT, currency, numbering)
- [🔄] P2.9 Reason codes: audit.reason_code scaffold created + verified (psql \dt audit.* → reason_code; 438205b). Posting-status enum + import-validation scaffold deferred to Module C (sales_invoice).
- [⬜] P2.10 Global search scaffold
- [⬜] P2.11 Dev fixture loader (seed data matching Excel structure)
- [⬜] P2.12 README with local-dev setup → `README.md`
- Gate: CI green, platform tests pass, security model implemented, backup tested locally, login with RBAC works.

## Phase 3 — Business Modules A→H  [gate: 🔒 per-module]
- [⬜] Module A — Platform (continued): finalize cross-cutting concerns
- [⬜] Module B — Master Data (~2w): Customers, suppliers, employees(min), products, warehouses/branches, UOM(gated), agents, partners, COA, territories. Reconciliation vs source counts.
- [⬘] Module C — Sales (~3w): invoices/sell-in/VAT, HQ rollup (الرئيسية), sold balances (رصيد الارصدة المباعة), price lists (كامل الكمية), under-disposal (تحت التصريف), returns, credit. Net price `E=C×(1-D)` test. Pilot: Dakahlia branch.
- [⬜] Module D — Inventory (~2w): stock by warehouse, movements, batch+expiry, transfers. Reconcile per-warehouse stock.
- [⬜] Module E — Finance (~3w): Cash(النقديه), AR(العملاء 47×747), AP, GL, P&L(الارباح والخسائر), BS(الميزانيه/الموازنه العامه), assets. AR total 2,200,000 test.
- [⬜] Module F — Marketing (~1–2w): KOL/doctor spend, product/brand spend, objective/KPI, sales targets, overstock alerts.
- [⬘] Module G — Purchasing (~2w, discovery-gated): suppliers, PO/GRN; no MRP/BOM until D11 confirmed.
- [⬜] Module H — Analytics + Telegram (~3w): executive KPIs + Telegram bot (read-only first, whitelist). Pilot branch only.

## Phase 4 — Telegram  [gate: 🔒 Telegram functional]
- [⬜] T4.1 Whitelist/authorize Telegram users
- [⬜] T4.2 Read-only commands: balance, stock alerts, daily summary, app links
- [⬜] T4.3 Optional write actions only after security review + explicit approval
- [⬜] T4.4 Audit log all bot actions
- Gate: bot secure, authorized users only.

## Phase 5 — Production Migration  [gate: 🔒 migration sign-off]
- [⬜] M1–M11: 11-stage migration (see IMPLEMENTATION_PLAN §3) with reconciliation at each stage. Precision rule: no rounding financial values.
- Gate: all reconciliations pass; Eli signs off.

## Phase 6 — Go-Live  [gate: 🔒 go-live approval]
- [⬜] Production deploy to CEO-room PC host
- [⬜] DNS/tunnel (CF Tunnel), monitoring, training
- Gate: UAT signed off, remote access verified, Eli sign-off.

## Phase 7 — WhatsApp  [gate: ⏭️ future]
- [⏭️] Deferred — explicit cost/risk decision after production stable.

---

Progress updates: tick items with concrete evidence as work lands. This file is the single source of truth for "what's done" — check here before any assumption.
