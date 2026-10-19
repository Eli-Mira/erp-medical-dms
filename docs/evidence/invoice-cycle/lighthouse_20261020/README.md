# Lighthouse check (R-35) — 2026-10-20

## Tooling
- `npm install -g lighthouse` succeeded (lighthouse 13.5.0) under the Windows Node runtime.
- The Bash-level `npx lighthouse` cannot reach the WSL-hosted app (`127.0.0.1:8018`),
  so the audit ran through a cloudflared quick tunnel (HTTPS), using the Playwright
  Chromium binary as `CHROME_PATH`.
- No Linux Node/Chrome exists, so this is the exact working combination.

## Results (before → after)
| Category | Before | After |
|---|---|---|
| Performance | 0.85 | 0.83 (tunnel latency noise, TBT 0 ms both runs) |
| Accessibility | 1.00 | 1.00 |
| Best practices | 0.96 | **1.00** |
| SEO | 0.63 | 0.63 |

Metrics (after): FCP 2.3 s, LCP 3.9 s, TBT 0 ms, CLS 0.052.

## Fixes applied for the audit findings
1. **Console error (best practices 0.96)** — `/favicon.ico` returned 404.
   Added `<link rel="icon" href="icon.svg" type="image/svg+xml">`; audit now reports
   zero browser errors.
2. **Cache lifetimes** — static assets now send `Cache-Control: public, max-age=3600`;
   the HTML shell sends `no-cache`.
3. **Transfer size / document latency** — `GZipMiddleware` (minimum_size=500) enabled;
   verified `content-encoding: gzip` on `/app/app.js`.

## Remaining, intentionally unchanged
- **SEO 0.63 / "page is blocked from indexing"** — `noindex` is correct for an internal
  business app; not a defect.
- **Minify JavaScript (est. 7 KiB)** — the PWA ships unminified source on purpose
  (no build step in the approved stack, D37/D46). Not fixed.
- **Render-blocking CSS / server response time** — dominated by the quick tunnel,
  not the application (TBT 0 ms, loopback response < 20 ms).

Report JSON kept out of the repository (contains a live tunnel URL); scores and
actionable audits are recorded here.
