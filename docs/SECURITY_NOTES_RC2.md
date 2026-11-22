# RC2 Security Notes & Accepted Decisions (2026-11-22)

Reference: `CLAUDE__RC2_AND_R8_VERDICT_20261122.md` and `HERMES_SECURITY_AND_SPEC_REVIEW_20261122.md` (sealed scan `scan_1259c9e50d4013d8addf2acb`).

## 1. Accepted LOW Findings (By Design — No Code Change)
1. **`POST /entries` (`app/finance/router.py:231`)** — Restricted to global `owner` and `finance` roles (`WRITE_ROLES`), with `POSTING_ENABLED` gate enforced in `ar.record_entry`. Global finance scope across branches is intentional by design.
2. **`PUT /credit-limits/customers/{customer_id}` (`app/credit_limits/router.py:177`, RC3 Wave 3B)** — Restricted to global `owner` and `finance` roles (`WRITE_ROLES`). Global owner/finance scope is intentional by design.

## 2. Dependency Hygiene Classification
- Hermes Security's OSV-Scanner flagged transitive runtime packages (`anyio`, `certifi`, `idna`, `pygments`) and optional Telegram dependency (`aiohttp`) as `CRITICAL` via static lockfile matching. Per Claude's verdict, these are **high-priority static-scan hygiene updates, not runtime exploit proof**, and are now pinned in `requirements.txt` and `requirements-telegram.txt` (`anyio==4.16.0`, `certifi==2026.11.20`, `idna==3.20`, `pygments==2.21.0`, `aiohttp==3.14.5`).
- Built Docker image `erp-rc2-final:531deead` verified `0` runtime advisories in OSV-Scanner v2.7.0 (`pytest==8.4.2` is dev/test-only and deferred to RC3).

## 3. Proxy Header Boundary
- `Dockerfile` now passes `--no-proxy-headers` to `uvicorn`, ensuring `app/auth/router.py` (`RATE_LIMIT_TRUSTED_PROXIES`) is the single authority for `CF-Connecting-IP` / `X-Forwarded-For` client IP extraction. At buyer-site deployment, operators must set `RATE_LIMIT_TRUSTED_PROXIES` to the real reverse-proxy/docker-bridge IP and verify with two client IPs.
