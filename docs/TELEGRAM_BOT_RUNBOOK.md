# Telegram Bot Operations & Security Runbook — ElsebaeyPharma ERP (`aiogram 3.33.0`)

- **Architecture Reference:** Built from `PHASE2_REFERENCES.md` (`aiogram` MIT) and `REFERENCE_CHECK.md §5` (Router + Filter + fail-closed `BaseMiddleware` allowlists prior to any handler or DB query).
- **Dependency Isolation (`Eli T3`):** Pinned `aiogram==3.33.0` lives ONLY in `requirements-telegram.txt` (core ERP `requirements.txt` remains untouched; license recorded in `THIRD_PARTY_NOTICES.md`).
- **Token Custody Rule (NON-NEGOTIABLE):** Production and throwaway BotFather tokens live ONLY in the operator's local `.env.telegram` file (never committed to git, never pasted in chat, never given to agents).

---

## 1. Least-Privilege PostgreSQL Role Setup (`telegram_reader`)

Create a strictly read-only role with ZERO access to `platform.*`, `audit.*`, or `private.*`:

```sql
CREATE ROLE telegram_reader NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN PASSWORD '<strong-random-password>';
ALTER ROLE telegram_reader SET default_transaction_read_only = on;
ALTER ROLE telegram_reader SET statement_timeout = '5s';
GRANT USAGE ON SCHEMA master_data, inventory, sales, finance TO telegram_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA master_data, inventory, sales, finance TO telegram_reader;
REVOKE ALL ON SCHEMA platform, audit, private FROM telegram_reader;
```

## 2. Environment Variables (`.env.telegram` — Local Operator File Only)

| Variable | Example / Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `<from BotFather, local only>` | Bot API credential (NEVER logged or committed) |
| `TELEGRAM_READONLY_DB_URL` | `postgresql+psycopg://telegram_reader:<pwd>@127.0.0.1:5432/<db>` | Read-only PostgreSQL URL |
| `TELEGRAM_ALLOWED_USER_IDS` | `111111,222222` | Comma-separated allowlisted Telegram numeric user IDs |
| `TELEGRAM_ALLOWED_CHAT_IDS` | `111111,222222` | Private chat IDs (and later allowlisted group chat IDs) |
| `TELEGRAM_USER_ROLES` | `111111:owner,222222:medical_rep:<territory_uuid>,333333:warehouse_staff:<branch_uuid>` | ERP role & scope mapping (`Eli T2`) |
| `TELEGRAM_ALERTS_ENABLED` | `false` | Enables `/alerts` & daily digest (near-expiry, low stock, AR) |
| `TELEGRAM_GROUP_MODE_ENABLED` | `false` | **MUST remain `false`** until private-chat live smoke passes (`Eli A6`) |
| `TELEGRAM_BOT_USERNAME` | `elsebaey_erp_bot` | Required `@mention` trigger when group mode is enabled |

## 3. Commands & Role Access Matrix

| Command / Keywords | Owner / Finance | Sales Mgr / Rep (Territory-Scoped) | Warehouse Staff (Branch-Scoped) | Group Chat (`GROUP_MODE=true` + `@mention`) |
|---|---|---|---|---|
| `/start`, `/help`, `/lang ar\|en` | Allowed | Allowed | Allowed | Allowed |
| `/balance <code\|uuid>` (`رصيد`) | All customers | Assigned territory only | **DENIED** | **DENIED (Private only)** |
| `/stock <sku\|uuid>` (`مخزون`) | All warehouses | All warehouses | Assigned branch only | **DENIED (Private only)** |
| `/sales` (`مبيعات اليوم`) | Company total | Assigned territory only | **DENIED** | Allowed |
| `/expiry [days]` (`صلاحية`) | All warehouses | All warehouses | Assigned branch only | Allowed |
| `/targets <uuid>` (`هدف`) | All targets | Assigned territory only | **DENIED** | Allowed |
| `/cover <sku\|uuid>` (`تغطية`) | Allowed | Allowed | **DENIED** | Allowed |
| `/alerts` (requires `TELEGRAM_ALERTS_ENABLED=true`) | Allowed | Sales Manager only | **DENIED** | **DENIED (Private only)** |

## 4. Operator 1-Command Throwaway-Bot Live Smoke (`Eli T1` / `A6`)

1. Install optional Telegram deps in a dedicated venv: `pip install -r requirements-telegram.txt`
2. Run automated local mock-server verification (zero internet, zero token):
   ```powershell
   python scripts/telegram_live_smoke.py --dry-run-local-mock
   ```
3. When ready on the operator PC with a **throwaway BotFather test token** in `.env.telegram`:
   ```powershell
   python scripts/telegram_live_smoke.py --live-throwaway
   ```
   Verify `live_ping_ok: true` and `token_redacted: true` in the generated receipt before switching to the production bot or enabling `TELEGRAM_GROUP_MODE_ENABLED=true`.

## 5. Starting the Bot Service

```powershell
python -m app.telegram.aiogram_bot
```
Unauthorized groups are automatically left (`leave_chat`), unknown users receive zero response (fail-closed), and per-user requests are rate-limited (`10` req / `60s`).
