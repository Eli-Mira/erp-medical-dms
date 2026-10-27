# I1 feature-only integration acceptance

## Scope and acceptance boundary

Owner authorization: `HERMES_ERP_I1_MASTER_EXECUTION_2026-10-26.md` plus the direct I1 request. One coordinator/writer; native Hermes supervised implementation only. This is a **local reversible integration**, not a protected merge, deployment, company-data migration or production approval.

- Worktree: `C:/Projects/ERPWorktrees/erp-i1-20261026`
- Branch: `integration/erp-i1-20261026`
Base: `69d68499fe67919b61fb97e96ad69fd33b27af37` (accepted S1 contact checkpoint).

**Acceptance is conditional on all matching artifacts below:** final native full gate exit 0 with zero failed/error/skipped cases, unchanged inputs and verified UUID DB/container cleanup; exact-byte independent SPEC/QUALITY/SECURITY PASS; and a local `COMMIT_RECEIPT.json` matching this branch's tested/reviewed files. Missing, mismatching or failed artifacts mean NOT ACCEPTED. Read the actual records, not historical totals.

Private durable evidence root: `C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/erp-i1-20261026/`. Native test records live in each stage's `output/<stage>/run.json`, `pytest.log` and `pytest.xml`; wrapper records include `native-result.json`, `owned-cleanup.json`, exact input hashes and effective Docker configuration. The final full gate is `i1_full_asof_final`; `i1_full_1g_final` remains the preserved 766-pass pre-label baseline. The earlier `i1_full_final` is a retained failed run (760 passed, six failed), not acceptance. Exact counts and elapsed time come from that run, not addition of S1/S4 reports. Final review inputs and verdict live in `review-packet-v5/` and `review-v5/`; final Git readback lives in `COMMIT_RECEIPT.json`.

## Included capabilities and provenance

| Source | Integration method |
|---|---|
| Supplier API/PWA `d92cb28bf1400dc2e92c21f09ba8ce5ad21d02db` / `4b1f12a2ea63bbf92096292203d6a1bce3a4f528` | Inherited through the accepted S1 baseline. |
| Customer names `34ee1f12c418a6ca31889a59ced9d4db5bd8d0fe`, lifecycle `cef937b3a2d1ecb83370a4977b3f8998339d9f12`, contacts/privacy `69d68499fe67919b61fb97e96ad69fd33b27af37` | Inherited intact; original seven privacy controls retained unchanged. |
| Supplier boot race `48d4d8bca2f0528836059a1ef8fae1909109b116` | Its navigation guard was already in the lifecycle baseline; verified, not double-applied. |
| Posted-sales `9deb1a97aef3688927ff2a96f52fde2d4d22e8f9`, inventory alerts `e9c3d3907e6f72726f0af2f6e1e748e9f07fa8ff`, D28 summary `b69aaacd9b8deccb9df50d3b39d022a761102947` | Inspected, path-allowlisted per-commit feature diffs applied with three-way content integration. No S4 ancestry merge. Hash-bound transfer patches are in the evidence root. |
| S4 guides `22b6075faa538dd04eaaf256a5ae0e9b251985e1` / `e7ab2cc940e5627a6ec3c14e14e5fccb5f42de56` | Read as integration guidance. Historical evidence and demo-builder scripts were not represented as I1 execution or copied into the delivery. |

Employees can maintain customers and contacts, preserve inactive-customer history and active invoice choices, use supplier maintenance, inspect role-scoped posted sales, filter/sort real warehouse cover/overstock/no-history alerts, and obtain management sales/collections/point-in-time AR without manually consolidating those ledgers. Monetary report descriptions explicitly identify EGP. There is **no invented low-stock policy**.

## Integration repairs and regression evidence

- **D28 settled-customer count:** the original query counted any nonzero ledger entry, even after full payment. Independent grouped raw SQL reproduced `1 != 0`; aggregation now counts nonzero customer net balances as of the selected date. `i1_ar_count_red` and `i1_ar_count_green` are retained.
- **Management read transaction:** response-validation/audit-failure probes showed audit effects surviving a failed request. Validate the complete response before audit/commit and roll back on failure. Both intended REDs and the covering GREEN are retained in `i1_summary_transaction_*`.
- **Report-session isolation:** logout now clears the three imported screens' figures, caches and errors synchronously; success/error completions are token/sequence-bound. Nine corrected browser regressions failed before the fix and passed after it. The first diagnostic had two incorrect warehouse-access expectations; it is preserved as mixed diagnostic evidence, not nine valid product REDs. `i1_report_privacy_red_v2` is the frozen corrected oracle.
- **Warehouse startup and late references:** warehouse staff no longer fail login by requesting invoice-only master references. Backend permissions were not widened; unauthorized lookups remain denied and warehouse labels fall back to IDs where names are not authorized. A captured old warehouse result was separately shown to repopulate a new account's selector; `loadWarehouses()` now fences assignment by the initiating token. Its old-error case was already passing. `i1_warehouse_response_red` preserves both observations.
- **Summary date label:** the as-of filter incorrectly used the invoice-date translation. Both Arabic/English focused browser assertions failed for that exact copy before the change (`i1_asof_label_red`), then passed with byte-unchanged tests (`i1_asof_label_green`). The dedicated `ms_as_of_date` label is now “حتى تاريخ” / “As of date”, with the real accessible input association verified. No report/date calculation changed.
- **No test weakening:** seven S1 contact privacy cases remain byte-identical to the baseline. Original failed attempts, selector/interaction mistakes and all raw evidence remain preserved. New code/test formatting is not claimed as byte-identical historical RED/GREEN; raw pre-format test snapshots remain in the respective verifier packets.

## Required integrated verification

Command from this worktree:

```text
python -X utf8 -I -B C:/Users/emadg/AppData/Local/hermes/audits/medical-dms/erp-i1-20261026/transport_1g.py i1_full_asof_final --chain -- tests/ -q --tb=short -o cache_dir=/tmp/pytest-cache
```

The task-local transport reuses the inspected S1 verifier and pinned nonroot browser image `sha256:63517e092359b1c61ebe768e5f690fdd7e0e883c1782859526fa4724494bf5f6`. Tests run in a read-only, capability-dropped, no-new-privileges, resource-limited container sharing only the verified egressless isolated PG fixture's loopback network namespace. The source packet is mounted read-only; host home, company volumes and Docker socket are not exposed. The approved runner exclusively creates/upgrades/down-one/upgrades/uses/drops its own `dms_cycle_test_<32hex>` database. `medical_dms` is not connected to, including for exploration.

The final command executes the complete `tests/` collection in one native pytest process with normal assertion rewriting and Python optimization explicitly disabled. After observed 512 MiB OOM failures, the owner explicitly approved **1 GiB for the disposable verifier only** through the native clarification response; `VERIFIER_1G_OWNER_APPROVAL.json` preserves that exact response. Memory plus swap is also limited to 1 GiB (no extra swap). All other resource, user, network, filesystem and capability limits stay unchanged. No test assertion, page size, browser launch or approved DB runner is changed. The transport additionally records read-only final cgroup observations. Acceptance requires final `oom_kill == 0`, all 766 previous controls retained and the two new localized date-label controls. Three inherited forged-field cases use collection-time `str(uuid4())` parameters (`tests/test_invoice_cycle_safety.py:324-326`); compare only those three UUID labels through an exact test/field-anchored substitution, retaining raw inventories. No other case identity may be normalized.

Resource history is retained: `i1_browser_crash_repro` directly recorded six OOM kills at the unchanged 512 MiB cap. `i1_browser_pressure_profile` was a cancelled diagnostic after sustained reclaim; its native runner removed its exact UUID DB and the owned exited container was removed and inspected absent. `i1_browser_gc_probe` still failed under OOM. Temporary DOM probes and the unsuccessful GC fixture were withdrawn byte-exactly to the frozen test preimages, not accumulated as speculative changes. No failed run or source packet was deleted. `i1_full_plain` still recorded 762 passed, four failed and six OOM kills; it is NOT accepted. Normal assertion rewriting is restored for the owner-approved 1 GiB run. Only its own complete passing evidence can satisfy acceptance; this document does not assert that a pending run has passed.

The combined suite must cover:

1. All retained S1/S4 API, migration, money, stock, invoice-history and posting-refusal controls, including all seven original contact privacy cases.
2. Independent SQL versus actual HTTP for posted net/VAT/gross, territory aggregates, collections, customer-net AR at dates before/on/after the receipt, real warehouse stock/cover/no-history, and absence of Draft stock/AR effects. New synthetic financial records are retained until the runner drops its UUID database; no immutable ledger/audit history is deleted.
3. Actual owner journeys at **320/390/768/1024/1440**, each in **Arabic RTL and English LTR**: create with contacts, edit, deactivate/reactivate, refresh/persist, supplier navigation/dialog/Escape, sales dates plus explicit Refresh, inventory search/status/sort/empty state, D28 date/keyboard Refresh/error/retry, logout. Each case asserts no document-level overflow and captures four actual view states with locale/direction metadata.
4. Finance/sales-manager/medical-rep/warehouse-staff browser and server role boundaries in both languages; nine report logout/late-response cases plus two stale warehouse-reference cases. Browser contexts are isolated and service workers blocked; no personal Brave profile is used.
5. Scoped Ruff, JavaScript/Python syntax, Git whitespace, patch replay, protected-file/workbook preservation, exact feature-only ancestry/content checks and independent final-byte semantic review. Only the new/changed scope is lint-certified; inherited whole-repository formatting is not a release claim.

## Safety and honest limits

- Rejected H1 `d39788ec4ac68eb2b17d0b2013206975bf87ea25` is **not an ancestor** of this baseline/candidate. Candidate `tools/` bytes remain identical to `4b1f12a`; its rejected controller change is not imported. H1 is NOT ACCEPTED.
- Scheduler `fe0759bcf885` was observed **enabled=false / paused**. No job/configuration/service activation or modification. `POSTING_ENABLED` remains default OFF; production HTTP posting remains refused.
- The original worktrees, their unrelated WIP, seven original workbooks, quarantined company DB/container/volume and protected dependency/configuration files are outside this integration's write scope. No unsafe B1 importer, S2 worker, FreeLLMAPI private-source route, paid fallback, remote push, protected merge or deployment.
- Provider is the existing S1-approved `openai-codex / gpt-6.1-sol` route. Global provider `1` defaults are not used. Independent review must pin that same route with no tools/fallback and included-quota checks; it reuses parent native evidence rather than claiming reviewer test execution.
- This is not staff UAT, physical-device testing, installed/offline-PWA acceptance, public HTTPS/deployment testing, company import/recovery approval, backup/restore approval or production readiness. VAT exceptions, unresolved workbook mappings, salary/accounting policies and go-live controls remain separate owner/business gates.
- No Vertix source, assets or branding were transplanted. The existing clinical navy/teal PWA is preserved; only the feature-specific S4 layout/motion was integrated, with actual reduced-motion checks. No framework/dependency/harness expansion.

## Next scoped decision

Stop at this local I1 checkpoint for owner acceptance before protected integration or production work. The highest-value follow-up is company staff UAT of these exact workflows and read-only reconciliation of outstanding workbook mappings; no new financial/import rule, Telegram/OCR activation or unrelated software slice is implied by this checkpoint.
