# Final current-code acceptance — invoice-collection-20261017

Read this brief first. Then successfully load `requesting-code-review` and `database-security` before source inspection. This is an independent semantic review, NOT implementation or a review of an earlier review.

## Scope and authority

Eli renewed the seven-item proceed/test/document/commit request on 2026-10-18. Implemented behavior and its native tests are unchanged. The only open commit prerequisite is an independent current-code SPEC, QUALITY and SECURITY judgment. One review is commissioned for that missing judgment; prior NO_VERDICT and isolation/history violations remain rejected. No production or default-local-DB recovery is authorized.

Root: `C:/Desktop/Huge system/docs/evidence/invoice-cycle/`.

Inputs (literal absolute paths):
- `C:/Desktop/Huge system/docs/evidence/invoice-cycle/review-input/manifest.json` — exact 17-file/22-hunk inventory and frozen source/context paths.
- `C:/Desktop/Huge system/docs/evidence/invoice-cycle/finalization-20261018/preflight.json` — parent read-only proof of current/frozen/protected hashes, full regenerated/replayed diffs and saved raw native records. Reuse this mechanical proof; do not claim you executed it.
- `C:/Desktop/Huge system/docs/evidence/invoice-cycle/finalization-20261018/review.delta.txt` — COMPLETE concatenation of all 17 frozen per-file diffs, 4,719 lines, SHA256 `37e099d4c503dde8774d121a96dd0b3be00cf4567f6379c445016814200ba378`. Read the whole file in five pages of at most 1,000 lines. All assertion bodies for new lifecycle/race tests are included. Inspect assertions, not just names/counts.
- Frozen context paths from manifest: binding milestone plan, PARENT_REPORT, DEFAULT_DB_INCIDENT, app/sales/{repo,calc,schemas}.py, app/auth/router.py, app/finance/router.py, app/config.py. Use frozen full owned source if diff context is insufficient.

## Required judgment

Assess all seven current-code requirements: flag-gated atomic posting; test-only flag enablement/default OFF; persisted stock/customer AR/VAT/permissions/duplicate/rollback controls; linked append-only posted reversal; scoped invoice-linked collections/void; complete mixed-VAT lifecycle; evidence adequacy for the current tested snapshot. Check transaction/audit atomicity, consistent lock ordering, genuine independent-session races, immutable history/provenance, input validation, scoping and SQL safety. Report actual defects with exact file/symbol/line and reasoning, separately from optional improvements or untested production policy.

The observed native proof is 315 passing cases plus 16 overlapping repeated controls, with disposable DB cleanup, default OFF and protected source/workbook/config bytes unchanged. Whole-repo lint remains failing with 145 inherited findings (169 baseline); changed-file scope is clean. Do not rerun completed tests.

The original worker applied an old 0010 to default local medical_dms, deleted some evidence and exceeded budget. That schema's stamp/content drift and historical evidence loss remain whole-milestone/deployment blockers. Current passes cannot retrospectively certify isolation. Judge current code separately; never issue a blanket whole-task PASS or infer unchanged real data. Commit/publication is not your operation.

## Strict tool envelope and output

Only `read_file`, `skill_view` and frozen-input `search_files` are permitted. NO terminal/execute_code, imports, application/test/migration execution, DB access, network, browser, Git mutation, file writes, installs, daemons, credentials, real workbook contents, other project/profile paths or subagents. The parent will persist your returned verdict, so you need not write any file.

Maximum 32 individual tool invocations (a batch counts its inner calls). Reserve the final response; at cap report exact omissions without exceeding it. Return actual schema-valid JSON, not tool-call markup. `passed=true` only if all current-code gates are PASS, all 17 files/22 hunks are covered and no blocking current defect/required assertion gap remains. Return coverage, source/test evidence per gate, checks not performed, reused evidence and separate whole-milestone blockers. Parent intake is not your independent judgment. Inherited runtime model/provider: gpt-6.1-sol/openai-codex; no shared configuration changes are allowed.
