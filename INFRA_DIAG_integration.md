# INFRA_DIAG_integration.md

## int-finance-002 failure (exit 1073807364)
- Stage: int-finance-002, merge commit 1dd37e8fa0f44ae0a75d3493df06fb9102e00d33, tree d1dd17716a658e69ced6caa00404279b8b6a8c20.
- Output ends after Alembic upgrade 0021_cost_quarantine -> 0022_territory_targets. No pytest output, no pytest.xml, no run.json.
- Container ran with --rm; `docker ps -a --filter name=int-finance` shows no stage container. Cannot docker inspect OOMKilled/stop signals.
- Launch command had --rm, so cleanup receipts not written; only docs/evidence/invoice-cycle/int-finance-002/screenshots/ exists.

## Host resources (at diagnosis time)
- FreePhysicalMemory: 3,044,336 KB (~3.0 GB) of 16,028,500 KB (~16 GB). Low free RAM, but not exhausted.
- Disk C: Free 47,576,645,632 bytes (~47.6 GB), Used 432,847,695,872 bytes.
- Docker containers running: erp-lane-tg-pg, erp-verify-pg, freellmapi-docker-freellmapi-1, erp-board-renderer-20261028, med_dms_db.
- No tg-fix2-* or lane-finance-* stage containers currently running. erp-lane-tg-pg is present; lane-finance containers not visible now.

## Most likely cause
Concurrent load / host memory pressure (only ~3 GB free) combined with the full-suite pytest memory footprint is the most likely cause. Container was terminated after Alembic but before pytest collection completed; subsequent diagnostic runs (3 tests) completed fine, indicating the runner works when memory demand is low.
- Evidence for: termination after schema setup, before test execution; later small runs succeed; low free RAM at host.
- Evidence against: no OOMKilled flag available (--rm), no daemon restart evidence, no stop request logged.

## Could not verify
- Exact wall-clock termination time and container uptime (no docker inspect; --rm removed it).
- Launcher's configured timeout value (runner has no explicit timeout flag; terminal background timeout not recorded).
- Docker events for the window (docker events not queried; no events captured).
- Whether OOMKilled was true (container removed).

## Action
Rerun full suite as int-finance-003 with no other Docker work if possible; keep same runner, no code changes. If it terminates again, treat as host capacity limit and report.

## int-finance-003 (rerun, 50 min hang)
- Stage int-finance-003, same merge commit 1dd37e8, same runner, no other stage containers (docker ps showed only infra containers).
- Container int-finance-run4 ran 50 minutes, status running, OOMKilled=false, then manually stopped after no pytest progress.
- Conclusion: full suite exceeds the approved container resource envelope (512 MB, 1 CPU) on this host. Not a code failure. No run.json/pytest.xml produced.
- Action: STOP. Do not fast-forward. Do not merge Telegram.
