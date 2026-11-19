# KNOWN ISSUES — RC1 (draft, Lain)

Build source: fresh clone of f64/RC1, never the dirty base tree.

## Limiter peer bucketing — UNVERIFIED
**Issue (UNVERIFIED):** limiter keys on `request.client.host`; behind a tunnel or proxy all clients may share one peer bucket.
**Verification step:** two-client test — send requests from two distinct client IPs through the proxy/tunnel and confirm each gets its own bucket (distinct 429 thresholds). Until run, this stays UNVERIFIED, not a finding.

## Other known issues (from pack)
- Old compose publishes db 5432 and app 8000 on all interfaces (RC1 fix: **COPY web/ + 127.0.0.1 binds only**).
- Trivy HIGH finding.
- Container runs as root.
- Requirements unpinned.
(USER/HEALTHCHECK/pinned requirements go here, not in RC1.)

## RC1 image lacks alembic/ and scripts/ (UNVERIFIED impact)
Observed in the fresh-clone build of the RC1 branch: image contains /app/app, /app/requirements.txt, /app/web only. `alembic upgrade head` and `python scripts/seed_demo_fresh.py` cannot run inside the image; performed via a mounted read-only checkout. Decide whether to add a separate migration step or accept as documented limitation. No protected-file change made.
