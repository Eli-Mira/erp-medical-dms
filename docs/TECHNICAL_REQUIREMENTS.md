# Technical Requirements

**Project:** Medical Company System (ERP-lite / Distribution Management System)  
**Status:** PROPOSAL — pending Eli's approval before Phase 1 build work begins.  
**Reference:** `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` (authoritative), `DECISION_LOG.md`, `OPEN_QUESTIONS.md`, `MIGRATION_RECONCILIATION_PLAN.md`, `MODULE_MAP.md`, `EXCEL_TO_SYSTEM_MAPPING.md`.  
**Date:** 2026-10-16  

---

## 1. Approved Constraints (Do Not Override)

| Constraint | Status |
|---|---|
| Zero-cost / open-source-first budget | Non-negotiable unless Eli changes it (D4) |
| PostgreSQL as the database | Working decision (D3) |
| Responsive web app / PWA (desktop + mobile) | Working decision (D3) |
| Hosting on existing always-on CEO-room PC | Working decision (D5) |
| Must support users outside the office network | Requirement (D5) |
| PostgreSQL never exposed publicly | Requirement (D5, §8) |
| Telegram before WhatsApp | Working decision (D6) |
| ERPNext and other OSS projects as reference only | Working decision (D2) |
| No guessing from Excel workbooks; evidence-based discovery | Non-negotiable (D7) |

---

## 2. Recommended Tech Stack (PROPOSAL)

> ⚠️ **This section is a recommendation, not a decision.** Eli must approve before Phase 1 build starts. Alternatives are listed for each layer.

### 2.1 Backend

**Proposal: Python + FastAPI**

| Criteria | Rationale |
|---|---|
| Zero-cost | Python and FastAPI are MIT-licensed open source |
| Async native | Native async/await; fits PostgreSQL async drivers (`asyncpg`) |
| Auto-generated API docs | Built-in Swagger/ReDoc reduces frontend-backend integration friction |
| Rich ecosystem | Pydantic (validation), SQLAlchemy/Alembic (ORM/migrations), `httpx` (HTTP client) |
| PWA-friendly | Serves both REST/JSON API and can serve static frontend if needed |
| Team familiarity | Python is common in Egyptian dev teams; easy hiring |

**Alternatives evaluated:**

| Stack | Pros | Cons for this project |
|---|---|---|
| Node.js + NestJS | Large npm ecosystem; TypeScript first-class | Heavier footprint; no natural advantage over Python here |
| Go + Gin | Static binary; minimal runtime | Steeper learning curve; no built-in ORM; less common in Egypt |
| PHP + Laravel | Cheap hosting options | Not aligned with zero-cost open-source-first philosophy; harder to deploy as PWA backend |
| Rust + Actix | Fastest; memory-safe | Over-engineered for MVP; very long dev time |

**Recommendation:** FastAPI unless Eli has a strong preference for another language.

### 2.2 Frontend

**Approved stack (D37, superseded proposal retained below for history): existing vanilla JavaScript PWA (HTML/CSS/JS) + FastAPI backend. No framework migration is authorized (D46).**

| Criteria | Rationale |
|---|---|
| Zero-cost | All MIT/Apache-2.0 licensed |
| PWA built-in | `vite-plugin-pwa` generates service worker + manifest automatically |
| RTL support | MUI has built-in RTL direction switching; easy Arabic layout |
| Desktop + mobile | Responsive Grid + breakpoints; touches-friendly components |
| Ecosystem | React Query (data fetching), React Hook Form (forms), date-fns (dates), Recharts/Chart.js (charts) |
| Hiring pool | Largest frontend talent pool in Egypt |

**Alternatives evaluated:**

| Stack | Pros | Cons for this project |
|---|---|---|
| Vue 3 + Vite | Simpler syntax; smaller bundle | Smaller RTL component library than MUI |
| Svelte | Very fast; small bundle | Smaller enterprise ecosystem; fewer Arabic/RTL resources |
| Angular | Strong typing; batteries included | Overweight for MVP; steeper learning curve |
| Vanilla JS + HTMX | Minimal JS; fast dev | No PWA service worker without extra work; harder to scale to complex dashboards |

**Recommendation (superseded by D37/D46):** keep the existing vanilla JS PWA. Framework changes require explicit owner approval (D46).

### 2.3 ORM & Migrations

**Proposal: SQLAlchemy 2.0 (async) + Alembic**

| Criteria | Rationale |
|---|---|
| Battle-tested | Used in production at scale; excellent documentation |
| Alembic migrations | Git-tracked, reversible migrations; standard in Python ecosystem |
| SQLAlchemy 2.0 | Modern async API (`asyncio` native); type-hinted |
| PostgreSQL-native | Full support for JSONB, arrays, window functions, CTEs, RLS |

**Alternatives:**
- **Prisma** (TypeScript ORM): excellent DX but couples frontend/backend to one ORM; PostgreSQL-only features are great but lock-in risk.
- **SQLModel** (Pydantic + SQLAlchemy): simpler for small projects but less mature for complex schemas.

**Recommendation:** SQLAlchemy + Alembic. Use PostgreSQL native types (JSONB, UUID, `money`/`numeric`) where appropriate.

### 2.4 Authentication & Authorization

**Proposal: FastAPI + JWT sessions + Argon2id password hashing + role-based access control (RBAC)**

| Criteria | Rationale |
|---|---|
| Security | Argon2id is the current gold standard for password hashing |
| Zero-cost | No paid auth provider needed |
| Simple sessions | JWT or server-side sessions; server-side sessions preferred for revoke/audit capability |
| RBAC | Role matrix covers: CEO, Admin, Finance, Sales Manager, Sales Rep, Warehouse, Branch Manager, Read-Only/Auditor |
| Private accounts boundary | Separate schema + row-level security (RLS) or application-level enforcement with audit logs (per D10) |

**Alternatives:**
- **Auth0 / Clerk / Supabase Auth:** easier to set up but violate zero-cost constraint (free tiers have limits).
- **LDAP/Active Directory:** only relevant if company already uses AD; likely overkill.

**Recommendation:** Build custom auth with server-side sessions (JWT tokens stored server-side with session table) for full audit trail and revocation capability.

### 2.5 PWA Tooling

| Tool | Purpose |
|---|---|
| `vite-plugin-pwa` | Service worker generation, cache strategies, manifest |
| Workbox (bundled via plugin) | Caching strategies (Stale-While-Revalidate for API responses) |
| `@pwa/install` or native `"beforeinstallprompt"` | Prompt users to install as app |

**Offline behavior (to be confirmed with Eli):** Read-only cached dashboards preferred; write operations require online.

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Desktop Browser / Installed PWA / Mobile Browser   │
│        (vanilla JS PWA — HTML/CSS/JS, RTL Arabic)    │
└──────────────────────────┬──────────────────────────┘
                           │ HTTPS (remote) / HTTP (local)
                           ▼
┌─────────────────────────────────────────────────────┐
│              Reverse Proxy / TLS Termination         │
│        (Caddy or Nginx — see §6 for details)        │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                 FastAPI Backend API                  │
│   (REST/JSON + auto Swagger docs + WebSocket if needed)│
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                 PostgreSQL 16+                     │
│   (schema-per-module or single schema with prefixes)│
│   + Row-Level Security for private accounts boundary│
└─────────────────────────────────────────────────────┘
                   ▲
                   │
┌─────────────────────────────────────────────────────┐
│              Telegram Bot (aiogram 3.x)             │
│         (read-only queries first; write gated)       │
└─────────────────────────────────────────────────────┘
```

**Key architectural decisions:**
- Monolithic backend serving both API and static frontend files (simpler deployment; no separate frontend hosting).
- Separate Docker Compose for local dev; systemd services for production (see §5).
- No message queue in MVP (Celery/RQ deferred to later if async jobs become necessary).

---

## 4. PostgreSQL Strategy

### 4.1 Version & Hosting
- **Target version:** PostgreSQL 16 LTS (or latest stable at build time).
- **Installation:** Native package (`apt` on Ubuntu Server or `yum` on AlmaLinux) — not Docker for production to reduce overhead on the CEO-room PC.
- **Connection pooling:** `PgBouncer` in transaction-mode (lightweight, avoids per-connection overhead).

### 4.2 Schema Organization
Two options under consideration (pending Eli's input):

| Option | Description | Pros | Cons |
|---|---|---|---|
| **Single schema (`public`)** | All tables in one schema; use naming prefixes (`sales_`, `inv_`, `fin_`, `master_`) | Simpler; fewer concepts to manage | Less isolation for private accounts |
| **Multiple schemas** | `app_public`, `app_private`, `app_audit`, `app_settings` | Stronger logical boundary for private accounts (D10) | Slightly more complex migrations |

**Recommendation:** Multiple schemas (`app_public`, `app_private`, `app_audit`) to enforce the private accounts security boundary (D10) via PostgreSQL schema-level privileges plus application-level RLS.

### 4.3 Key Data Types
| Domain | Type | Rationale |
|---|---|---|
| Money | `NUMERIC(19,4)` | Exact decimal; never `FLOAT`/`DOUBLE` |
| Currency | `CHAR(3)` (ISO 4217) | e.g., `EGP` |
| UUIDs | `UUID` (default `gen_random_uuid()`) | Stable primary keys; no sequential guessability |
| Timestamps | `TIMESTAMPTZ` | Always timezone-aware; store UTC, display in `Africa/Cairo` |
| JSONB | `JSONB` | Flexible fields (e.g., product attributes, settings) |
| Arrays | `NUMERIC[]` / `TEXT[]` | Where appropriate (e.g., multi-select tags) |
| Dates | `DATE` | Separate from timestamps |

### 4.4 Indexing Strategy
- Primary keys: clustered (PostgreSQL default).
- Foreign keys: automatic index on child tables.
- Common query patterns (per module): composite indexes on `(warehouse_id, product_id, date)`, `(customer_id, date)`, `(territory_id, date)`.
- GIN index on JSONB columns for flexible search.
- Partial indexes for active-only rows (`WHERE voided = false`).

### 4.5 Row-Level Security (RLS)
- Enable RLS on `app_private.*` tables.
- Policy: `owner_only()` function checks `current_setting('app.current_user_role') = 'owner'`.
- Audit table (`app_audit.events`) accessible only to `admin` and `owner` roles.

---

## 5. Hosting & Server Details

### 5.1 Host Machine
- **Existing PC in CEO room** (as specified).
- **Specs to verify:** CPU cores, RAM (minimum 8 GB recommended), disk space (minimum 100 GB free), UPS availability.
- **OS options (see §5.2).**

### 5.2 Server OS Recommendation

**Proposal: Ubuntu Server 24.04 LTS (x64)**

| Criteria | Rationale |
|---|---|
| Long-term support | 5 years free; security updates through 2029 |
| Zero-cost | No license fees |
| Package availability | PostgreSQL, Python, Caddy, Docker, all needed packages in official repos |
| Community/support | Large Egyptian admin community; many tutorials in Arabic |
| systemd-native | No Docker required; services managed by systemd (simpler, lighter) |

**Alternatives:**

| OS | Pros | Cons |
|---|---|---|
| Debian 12 | Rock-solid; smaller footprint | Slightly older packages; slower release cycle |
| AlmaLinux 9 | RHEL-compatible; stable | Smaller Egyptian community; fewer tutorials |
| Windows Server | Familiar to some admins | Licensing cost (violates zero-cost); heavier resource usage |

**Recommendation:** Ubuntu Server 24.04 LTS. If the existing PC runs Windows and reinstalling is not acceptable, run Ubuntu in a dual-boot or on a spare machine. Docker Compose can also run on Windows but is not recommended for production.

### 5.3 Service Architecture (Production)

```
Systemd services:
  postgresql.service    → managed by apt package
  pgbouncer.service     → connection pooler
  medical-app.service   → FastAPI backend (gunicorn + uvicorn workers)
  caddy.service         → reverse proxy + TLS termination
  telegram-bot.service  → standalone Python process (aiogram)
```

- All services run under dedicated system users (`postgres`, `pgbouncer`, `medapp`, `caddy`, `tgbot`) — least privilege.
- No services run as root.
- Automatic start on boot (`systemctl enable`).
- Automatic restart on crash (`Restart=always` in systemd unit).

### 5.4 Local Development

```
docker-compose.yml:
  postgres:16        (with volume for data)
  pgbouncer          (optional in dev)
```

Frontend runs via `npm run dev` (Vite dev server). Backend via `uvicorn main:app --reload`.

---

## 6. Remote Access & HTTPS Comparison

> This section compares three candidates. **Decision pending Eli's input after network conditions are assessed.**

### 6.1 Candidate Comparison

| Criterion | Cloudflare Tunnel (`cloudflared`) | DuckDNS + Caddy | WireGuard VPN (PiVPN / Tailscale) |
|---|---|---|---|
| **Cost** | Free tier (1 tunnel, 100 GB/mo egress) | Free (DuckDNS) + Caddy free auto-HTTPS | Free (open source) |
| **Setup complexity** | Low (`cloudflared install` + DNS CNAME) | Medium (DDNS client + Caddy config + port forwarding) | Medium-High (VPN server + client config per device) |
| **ISP CGNAT compatible** | ✅ Yes (outbound only) | ❌ No (needs public IP or port forwarding) | ⚠️ Depends (Tailscale works; WireGuard native needs public IP) |
| **TLS/HTTPS** | Managed by Cloudflare (free cert) | Caddy auto-HTTPS (Let's Encrypt) | N/A (encrypted tunnel; app still needs HTTP) |
| **DDoS protection** | ✅ Built-in (Cloudflare network) | ❌ None | N/A |
| **Bandwidth limit** | 100 GB/mo free; overage charged | Unlimited (your ISP cap) | Unlimited (your ISP cap) |
| **Audit/log exposure** | Cloudflare dashboard logs | Self-hosted logs | Self-hosted logs |
| **Single point of failure** | Cloudflare (reliable but external) | Your home internet | Your home internet |
| **Suitable for production** | ✅ Yes (widely used) | ✅ Yes (if public IP available) | ✅ Yes (but UX is worse — users install VPN client) |

### 6.2 Recommendation

**Primary: Cloudflare Tunnel (`cloudflared`)**

- Works behind CGNAT (common in Egypt).
- Free tier sufficient for a small company (5–20 users).
- No port forwarding; no public IP required.
- Free managed TLS (no cert renewal headaches).
- Cloudflare dashboard provides basic access logs.

**Fallback: DuckDNS + Caddy** — only if the company has a public IP and port forwarding is acceptable.

**Not recommended for MVP:** WireGuard/Tailscale VPN — adds friction for field reps (must install VPN client on phone/laptop). Consider later if Telegram integration is insufficient.

### 6.3 DNS & Hostname

- Purchase a low-cost domain (e.g., `.com` or `.eg`) — ~$10–12/year. This is the only likely non-free cost.
- Subdomain: `app.medcompany.eg` or similar (TBD with Eli).
- Cloudflare DNS managed under the same account; tunnel pointed at `app.medcompany.eg`.

---

## 7. Backup & Recovery

### 7.1 Backup Strategy

| Type | Frequency | Method | Retention |
|---|---|---|---|
| **Full DB dump** | Daily (02:00 Cairo time) | `pg_dump --format=custom` → compressed `.gz` file | 30 days local; 90 days offsite |
| ** WAL archiving** | Continuous | `wal_level = replica` + archive to local disk | 7 days local |
| **File system backup** | Daily | `rsync` to external USB or network share | 14 days |
| **Offsite copy** | Weekly | Upload to free tier cloud storage (Backblaze B2 ~$0.005/GB/mo) or Google Drive | 90 days |

### 7.2 Recovery Procedures

1. **Point-in-time recovery:** Restore from `pg_dump` + replay WAL up to target timestamp.
2. **Full restore:** Stop service → restore `.gz` dump → start service → verify row counts.
3. **Test restores:** Quarterly (documented in `BACKUP_AND_RECOVERY.md`).

### 7.3 Disaster Recovery

- Minimal RTO: 4 hours (restore from offsite backup).
- Minimal RPO: 1 hour (WAL archiving enables near-zero data loss).
- Documented runbook in `BACKUP_AND_RECOVERY.md` (to be created).

---

## 8. Supported Devices & Browsers

### 8.1 Browsers (minimum supported)

| Browser | Minimum Version | Notes |
|---|---|---|
| Chrome | 110+ | Primary target; best PWA support |
| Edge | 110+ | Chromium-based; same as Chrome |
| Firefox | 115+ | Full PWA support since v111 |
| Safari | 16.4+ | iOS 16.4+; PWA install supported |
| Samsung Internet | 18+ | Common in Egypt; Chromium-based |

### 8.2 Devices

| Device Type | Minimum Resolution | Notes |
|---|---|---|
| Desktop / Laptop | 1366×768 | 1024×768 acceptable for read-only views |
| Tablet | 768×1024 (portrait) | Touch-optimized; sidebar collapses to drawer |
| Smartphone | 360×640 (portrait) | Critical paths (scan, view invoice) must work |

### 8.3 PWA Install

- Supported on Chrome/Edge/Safari.
- "Add to Home Screen" prompt via `beforeinstallprompt` event.
- Offline cache: dashboard KPIs, master data lookup (customers/products).

---

## 9. Dependency & License Policy

Per `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md` §2C:

1. **No GPL/copyleft code in custom application** unless Eli explicitly approves the licensing consequence.
2. **Prefer permissive licenses:** MIT, BSD-2/3, Apache-2.0, PostgreSQL License.
3. **Record every dependency's license** in `THIRD_PARTY_NOTICES.md` (created before build).
4. **Study, don't copy:** ERPNext and other OSS projects are reference material only; implement behavior independently.
5. **Dependency update cadence:** Quarterly review; security patches applied immediately.
6. **No SaaS lock-in:** All core logic runs self-hosted; third-party APIs (Telegram Bot API) are integrations, not dependencies.

### Approved Dependency License Summary (for proposed stack)

| Dependency | License | Permissive? |
|---|---|---|
| Python | PSF (custom permissive) | ✅ |
| FastAPI | MIT | ✅ |
| SQLAlchemy | MIT | ✅ |
| Alembic | MIT | ✅ |
| asyncpg | BSD | ✅ |
| PgBouncer | PostgreSQL License | ✅ |
| React | MIT | ✅ |
| TypeScript | Apache-2.0 | ✅ |
| Vite | MIT | ✅ |
| Material-UI | MIT | ✅ |
| Caddy | BSD-2 | ✅ |
| Ubuntu | GNU GPL (OS only; not part of app) | ✅ (not distributed) |
| PostgreSQL | PostgreSQL License | ✅ |
| aiogram (Telegram) | MIT | ✅ |

---

## 10. Telegram & WhatsApp Integration

### 10.1 Telegram (Phase: Before Core Modules Complete)

**Library:** `aiogram 3.x` (Python, MIT-licensed, async-native).

**Security model:**
- Whitelist authorized Telegram user IDs (stored in DB, loaded at startup).
- All commands are read-only by default.
- Write actions (e.g., create sale, approve return) require explicit manager approval in-app; Telegram only sends alerts/links.
- Sensitive data (full AR balance, customer details) redacted in bot responses; only summary or deep-link to app.
- Audit log every bot interaction.

**Initial command set (TBD with Eli):**
- `/daily` — sales + collections summary for yesterday
- `/balance <customer_name>` — outstanding AR balance (exact match or prefix)
- `/lowstock` — products below reorder threshold
- `/alert <product>` — stock + expiry status for a product
- `/help` — list available commands

### 10.2 WhatsApp (Later Phase)

**Status:** Deferred. Must not block core system.

**Evaluation criteria before implementation:**
- Official WhatsApp Business API cost analysis (per-message pricing).
- Whether semi-automation (manual reply forwarding) is sufficient.
- Risk assessment of unofficial libraries (`whatsapp-web.js`, etc.) — fragile, ToS-violating.
- Explicit business value: which messages/workflows create measurable value?

**Recommendation:** Do not implement WhatsApp in MVP. Re-evaluate after Telegram is stable and Eli confirms measurable value.

---

## 11. Performance & Reliability Targets

### 11.1 Response Time Targets

| Operation | Target | Notes |
|---|---|---|
| Page load (initial) | < 2 s | Cached on subsequent visits |
| Dashboard KPI query | < 500 ms | Aggregated with materialized views if needed |
| Invoice search (by number/customer) | < 300 ms | Indexed |
| AR balance lookup | < 200 ms | Indexed on customer_id + date |
| Report generation (monthly sales) | < 5 s | Streaming response for large exports |
| Telegram bot response | < 1 s | Simple queries; complex reports defer to app link |

### 11.2 Concurrency

- Estimated concurrent users: 10–20 (company size unknown; confirm with Eli).
- FastAPI + uvicorn (4 workers) + PgBouncer (max 50 connections) should handle this comfortably.
- Load test before go-live with realistic data volume (migrated Excel data).

### 11.3 Availability

- Target: 99.5% uptime during business hours (8 AM – 10 PM Cairo time, Monday–Saturday).
- Downtime windows: scheduled maintenance announced 24h in advance.
- No SLA penalty (internal system); reliability goal driven by business need.

### 11.4 Data Integrity

- All money/stock mutations wrapped in database transactions.
- Soft-delete / void pattern (never hard-delete posted financial records).
- Audit trail on every CREATE/UPDATE/DELETE on sensitive tables.
- Quarterly backup restore test.

---

## 12. Observability & Logging

### 12.1 Application Logging

**Library:** Python `logging` module (standard library) + `structlog` for structured JSON logs.

**Log levels:**
- `INFO`: normal operations (login, invoice created, report viewed).
- `WARNING`: slow queries (>500 ms), deprecated API usage.
- `ERROR`: failed transactions, unhandled exceptions.
- `CRITICAL`: database connection lost, disk full, auth breach attempt.

**Log format:** JSON with fields: `timestamp`, `level`, `module`, `user_id`, `action`, `entity_type`, `entity_id`, `detail`.

**Log retention:** 90 days local (compressed); rotate weekly.

### 12.2 Audit Trail

**Table:** `app_audit.events` (append-only, never deleted).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `event_type` | TEXT | `login`, `logout`, `create`, `update`, `void`, `approve`, `export` |
| `entity_type` | TEXT | `invoice`, `collection`, `return`, `product`, `customer`, `setting` |
| `entity_id` | UUID | FK to relevant table |
| `user_id` | UUID | FK to users table |
| `old_values` | JSONB | Previous state (nullable) |
| `new_values` | JSONB | New state (nullable) |
| `ip_address` | INET | Client IP |
| `user_agent` | TEXT | Browser/client string |
| `created_at` | TIMESTAMPTZ | UTC |

**Access:** `admin` and `owner` roles only.

### 12.3 Health Checks

- `/health` endpoint: returns `{"status": "ok", "db": "connected", "uptime_s": N}`.
- Used by: systemd (restart on failure), Cloudflare (availability monitoring), internal monitoring.
- Check interval: every 30 s (systemd `StartLimitIntervalSec`).

### 12.4 Metrics (Lightweight — No External Service)

- Export Prometheus metrics via `/metrics` endpoint (optional, only if Eli wants monitoring dashboards).
- Libraries: `prometheus-client` (Apache-2.0).
- Alternative: skip Prometheus; use structured logs + Logrotate + manual grep for MVP.

### 12.5 Error Alerting

- Failed login attempts > 5 in 10 min from same IP → temporary IP block (configurable).
- Service crash → systemd auto-restart + log entry.
- Disk usage > 85% → log warning; > 95% → alert via Telegram bot to admin.

---

## 13. Internationalization (i18n) & RTL

| Concern | Approach |
|---|---|
| **Languages** | Arabic (default, RTL) + English (toggle) |
| **Framework** | JSON translation files served by FastAPI (`web/i18n/ar.json`, `web/i18n/en.json`) — already implemented in the vanilla PWA; no Django/DRF dependency |
| **Number formatting** | Arabic-Indic numerals (٠١٢٣٤٥٦٧٨٩) in Arabic UI; Western numerals in English UI |
| **Date formatting** | Hijri/Gregorian toggle (TBD — confirm if Hijri is needed with Eli) |
| **Currency display** | `EGP` symbol; Arabic: `ج.م` |
| **Layout** | MUI `direction="rtl"` / `direction="ltr"` toggle; CSS logical properties (`margin-inline-start` not `margin-left`) |

**Note:** Hijri calendar support is a known open question. Confirm with Eli whether Hijri dates are required in the UI.

---

## 14. Open Items Requiring Eli's Input

| # | Item | Why It Matters |
|---|---|---|
| 1 | **Backend framework approval** (FastAPI vs alternative) | Blocks Phase 1 |
| 2 | **Frontend framework approval** (React vs Vue vs others) | Blocks Phase 1 |
| 3 | **Server OS** (Ubuntu Server vs other) | Blocks deployment planning |
| 4 | **ISP public IP status** (affects remote access choice) | Determines Cloudflare Tunnel vs DuckDNS |
| 5 | **Domain purchase** (do we have one? budget?) | Needed for HTTPS + tunnel |
| 6 | **Hijri calendar requirement** | Impacts date handling library choice |
| 7 | **Exact user count & roles** | Impacts licensing, concurrency, permissions design |
| 8 | **PostgreSQL host** (same PC as app or separate?) | Affects resource planning |
| 9 | **Backup destination** (USB drive? network share? cloud?) | Impacts disaster recovery plan |
| 10 | **Approximate data volume** (total rows, growth rate) | Impacts indexing + storage planning |

---

## 15. Next Action

1. **Eli reviews this document.**
2. **Eli provides input on §14 (Open Items).**
3. **Eli approves or rejects the proposed stack (or suggests alternatives).**
4. Upon approval, proceed to Phase 1: build `PRD.md`, `APP_FLOW.md`, `DESIGN_BRIEF.md`, `DATABASE_SCHEMA.md`, `IMPLEMENTATION_PLAN.md`.

---

*Document status: DRAFT — pending Eli's approval.*
*Last updated: 2026-10-16*
