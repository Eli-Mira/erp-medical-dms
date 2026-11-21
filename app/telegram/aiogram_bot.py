import os
import time
import asyncio
from dataclasses import dataclass, field
from typing import (
    FrozenSet,
    Dict,
    Tuple,
    Optional,
    Any,
    List,
    Set,
)
from decimal import Decimal
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from asyncio import to_thread

# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class BotSettings:
    bot_token: str
    readonly_db_url: str
    allowed_user_ids: FrozenSet[int]
    allowed_chat_ids: FrozenSet[int]
    user_roles: Dict[int, Tuple[str, Optional[str]]]
    group_mode_enabled: bool = False
    alerts_enabled: bool = False
    bot_username: str = "elsebaey_erp_bot"
    api_base: Optional[str] = None
    rate_limit_max: int = 10
    rate_limit_window_sec: int = 60

    @classmethod
    def from_env(cls) -> "BotSettings":
        def _parse_int_set(val: str) -> FrozenSet[int]:
            return frozenset(int(x) for x in val.split(",") if x.strip())

        def _parse_roles(val: str) -> Dict[int, Tuple[str, Optional[str]]]:
            out: Dict[int, Tuple[str, Optional[str]]] = {}
            for part in filter(None, (p.strip() for p in val.split(","))):
                seg = part.split(":")
                if len(seg) not in (2, 3):
                    continue
                uid = int(seg[0])
                role = seg[1]
                scope = seg[2] if len(seg) == 3 else None
                out[uid] = (role, scope)
            return out

        return cls(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            readonly_db_url=os.getenv("TELEGRAM_READONLY_DB_URL", ""),
            allowed_user_ids=_parse_int_set(os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")),
            allowed_chat_ids=_parse_int_set(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")),
            user_roles=_parse_roles(os.getenv("TELEGRAM_USER_ROLES", "")),
            group_mode_enabled=os.getenv("TELEGRAM_GROUP_MODE_ENABLED", "false").lower()
            == "true",
            alerts_enabled=os.getenv("TELEGRAM_ALERTS_ENABLED", "false").lower() == "true",
            bot_username=os.getenv("TELEGRAM_BOT_USERNAME", "elsebaey_erp_bot"),
            api_base=os.getenv("TELEGRAM_API_BASE") or None,
            rate_limit_max=int(os.getenv("TELEGRAM_RATE_LIMIT_MAX", "10")),
            rate_limit_window_sec=int(os.getenv("TELEGRAM_RATE_LIMIT_WINDOW_SEC", "60")),
        )


# --------------------------------------------------------------------------- #
# Middleware
# --------------------------------------------------------------------------- #
class AllowlistAndRateLimitMiddleware(BaseMiddleware):
    def __init__(self, settings: BotSettings, engine: Engine):
        super().__init__()
        self.settings = settings
        self.engine = engine
        self._user_timestamps: Dict[int, List[float]] = {}
        self._lang_store: Dict[int, str] = {}

    async def __call__(
        self,
        handler,
        event: Message,
        data: Dict[str, Any],
    ):
        chat = event.chat
        user = event.from_user
        chat_id = chat.id
        user_id = user.id if user else 0
        text_msg = (event.text or "").strip()

        # Group handling
        if chat.type in ("group", "supergroup"):
            if chat_id not in self.settings.allowed_chat_ids:
                try:
                    await event.bot.leave_chat(chat_id)
                except Exception:
                    pass
                return None
            if not self.settings.group_mode_enabled:
                return None
            if f"@{self.settings.bot_username}".lower() not in text_msg.lower():
                return None

        # Private allowlist
        if (
            chat_id not in self.settings.allowed_chat_ids
            or user_id not in self.settings.allowed_user_ids
            or user_id not in self.settings.user_roles
        ):
            return None

        # Rate limiting
        now = time.monotonic()
        ts = self._user_timestamps.setdefault(user_id, [])
        ts = [t for t in ts if t > now - self.settings.rate_limit_window_sec]
        if len(ts) >= self.settings.rate_limit_max:
            await event.answer(
                "تم تجاوز حد الطلبات مؤقتاً. حاول بعد دقيقة. / Rate limit exceeded; please retry shortly."
            )
            return None
        ts.append(now)
        self._user_timestamps[user_id] = ts

        # Inject DI data
        role, scope = self.settings.user_roles[user_id]
        data.update(
            {
                "erp_role": role,
                "erp_scope_id": str(scope) if scope is not None else None,
                "settings": self.settings,
                "db_engine": self.engine,
                "lang_store": self._lang_store,
            }
        )
        return await handler(event, data)


# --------------------------------------------------------------------------- #
# RBAC & Helpers
# --------------------------------------------------------------------------- #
ROLE_ALLOWED: Dict[str, Set[str]] = {
    "owner": {
        "balance",
        "stock",
        "sales_today",
        "expiry",
        "targets",
        "stock_cover",
        "alerts",
    },
    "finance": {
        "balance",
        "stock",
        "sales_today",
        "expiry",
        "targets",
        "stock_cover",
        "alerts",
    },
    "sales_manager": {
        "balance",
        "stock",
        "sales_today",
        "expiry",
        "targets",
        "stock_cover",
        "alerts",
    },
    "district_manager": {
        "balance",
        "stock",
        "sales_today",
        "expiry",
        "targets",
        "stock_cover",
    },
    "medical_rep": {
        "balance",
        "stock",
        "sales_today",
        "expiry",
        "targets",
        "stock_cover",
    },
    "read_only_auditor": {
        "balance",
        "stock",
        "sales_today",
        "expiry",
        "targets",
        "stock_cover",
    },
    "warehouse_staff": {"stock", "expiry"},
}

GROUP_SAFE = frozenset({"expiry", "stock_cover", "sales_today", "targets"})


def _is_uuid(val: str) -> bool:
    try:
        import uuid

        uuid.UUID(val)
        return True
    except Exception:
        return False


async def _check_permission(
    template: str, erp_role: str, message: Message, chat_type: str
) -> bool:
    allowed = ROLE_ALLOWED.get(erp_role, set())
    if template not in allowed:
        await message.answer("Permission denied for this operation.")
        return False
    if chat_type != "private" and template not in GROUP_SAFE:
        await message.answer("This command can only be used in private chat.")
        return False
    return True


# --------------------------------------------------------------------------- #
# Database query helpers
# --------------------------------------------------------------------------- #
async def _run_query(engine: Engine, stmt: str, params: dict) -> List[Dict[str, Any]]:
    def _exec():
        with engine.connect() as conn:
            return conn.execute(text(stmt), params).mappings().all()

    return await to_thread(_exec)


async def query_balance(
    engine: Engine, ref: str, territory_id: Optional[str], lang: str
) -> str:
    if _is_uuid(ref):
        cust_cond = "c.id = CAST(:ref AS uuid)"
    else:
        cust_cond = "LOWER(c.code) = LOWER(:ref)"
    where = f"{cust_cond}"
    if territory_id:
        where += " AND c.territory_id = CAST(:tid AS uuid)"
    stmt = f"""
        SELECT COALESCE(SUM(e.debit - e.credit), 0) AS balance
        FROM master_data.master_customer c
        LEFT JOIN finance.ar_entry e ON e.customer_id = c.id
        WHERE {where}
        GROUP BY c.id
    """
    rows = await _run_query(engine, stmt, {"ref": ref, "tid": territory_id})
    bal = rows[0]["balance"] if rows else 0
    return f"{Decimal(str(bal)):.2f} EGP"


async def query_stock(
    engine: Engine, ref: str, branch_id: Optional[str], lang: str
) -> str:
    if _is_uuid(ref):
        prod_cond = "p.id = CAST(:ref AS uuid)"
    else:
        prod_cond = "LOWER(p.sku) = LOWER(:ref)"
    join_branch = ""
    if branch_id:
        join_branch = "JOIN master_data.master_warehouse w ON w.id = s.warehouse_id AND w.branch_id = CAST(:bid AS uuid)"
    stmt = f"""
        SELECT COALESCE(SUM(s.quantity), 0) AS qty
        FROM master_data.master_product p
        JOIN inventory.stock_balance s ON s.product_id = p.id
        {join_branch}
        WHERE {prod_cond}
        GROUP BY p.id
    """
    rows = await _run_query(engine, stmt, {"ref": ref, "bid": branch_id})
    qty = rows[0]["qty"] if rows else 0
    return f"{Decimal(str(qty)):.3f}"


async def query_sales_today(
    engine: Engine, territory_id: Optional[str], lang: str
) -> str:
    where = ""
    if territory_id:
        where = "AND territory_id = CAST(:tid AS uuid)"
    stmt = f"""
        SELECT COALESCE(SUM(grand_total), 0) AS total
        FROM sales.sales_invoice
        WHERE invoice_date = CURRENT_DATE
          AND posting_status = 'Posted'
          {where}
    """
    rows = await _run_query(engine, stmt, {"tid": territory_id})
    total = rows[0]["total"] if rows else 0
    return f"{Decimal(str(total)):.2f}"


async def query_expiry(
    engine: Engine, days: int, branch_id: Optional[str], lang: str
) -> str:
    days = max(1, min(days, 365))
    branch_filter = ""
    if branch_id:
        branch_filter = "AND w.branch_id = CAST(:bid AS uuid)"
    stmt = f"""
        SELECT b.batch_no, p.sku, b.expiry_date, s.quantity, w.code AS wh_code
        FROM inventory.batch_record b
        JOIN master_data.master_product p ON p.id = b.product_id
        JOIN inventory.stock_balance s ON s.batch_id = b.id
            AND s.product_id = b.product_id
            AND s.warehouse_id = b.warehouse_id
        JOIN master_data.master_warehouse w ON w.id = s.warehouse_id
        WHERE b.expiry_date <= CURRENT_DATE + (:days * INTERVAL '1 day')
          AND s.quantity > 0
          {branch_filter}
        ORDER BY b.expiry_date ASC
        LIMIT 20
    """
    rows = await _run_query(engine, stmt, {"days": days, "bid": branch_id})
    lines = []
    for r in rows:
        qty = Decimal(str(r["quantity"])).quantize(Decimal("0.001"))
        lines.append(
            f"{r['batch_no']} | {r['sku']} | {r['expiry_date']} | {qty} | {r['wh_code']}"
        )
    return "\n".join(lines) or "No expiring batches found."


async def query_targets(
    engine: Engine, target_id: str, territory_id: Optional[str], lang: str
) -> str:
    if not _is_uuid(target_id):
        return "Invalid target identifier."
    stmt = f"""
        SELECT t.target_quantity,
               COALESCE(SUM(l.quantity), 0) AS achieved
        FROM sales.sales_target t
        LEFT JOIN sales.sales_invoice i
          ON i.posting_status = 'Posted'
         AND date_trunc('month', i.invoice_date)::date = t.period_month
         AND (
               (t.rep_id IS NOT NULL AND i.rep_id = t.rep_id)
               OR (t.territory_id IS NOT NULL AND i.territory_id = t.territory_id)
             )
        LEFT JOIN sales.sales_invoice_line l
          ON l.invoice_id = i.id
         AND (t.product_id IS NULL OR l.product_id = t.product_id)
        WHERE t.id = CAST(:tid AS uuid)
    """
    if territory_id:
        stmt += " AND t.territory_id = CAST(:territory AS uuid)"
    stmt += " GROUP BY t.id, t.target_quantity"
    rows = await _run_query(
        engine, stmt, {"tid": target_id, "territory": territory_id}
    )
    if not rows:
        return "Target not found."
    r = rows[0]
    return f"Target: {r['target_quantity']}, Achieved: {r['achieved']}"


async def query_stock_cover(
    engine: Engine, ref: str, lang: str
) -> str:
    if _is_uuid(ref):
        prod_cond = "p.id = CAST(:ref AS uuid)"
    else:
        prod_cond = "LOWER(p.sku) = LOWER(:ref)"
    stmt_qty = f"""
        SELECT COALESCE(SUM(s.quantity), 0) AS stock_qty
        FROM master_data.master_product p
        JOIN inventory.stock_balance s ON s.product_id = p.id
        WHERE {prod_cond}
    """
    stmt_avg = f"""
        SELECT COALESCE(SUM(l.quantity), 0) / 30.0 AS avg_daily
        FROM master_data.master_product p
        JOIN sales.sales_invoice_line l ON l.product_id = p.id
        JOIN sales.sales_invoice i ON i.id = l.invoice_id
          AND i.posting_status = 'Posted'
          AND i.invoice_date >= CURRENT_DATE - INTERVAL '30 days'
        WHERE {prod_cond}
    """
    stock_row = await _run_query(engine, stmt_qty, {"ref": ref})
    avg_row = await _run_query(engine, stmt_avg, {"ref": ref})
    stock_qty = Decimal(str(stock_row[0]["stock_qty"])) if stock_row else Decimal("0")
    avg_daily = Decimal(str(avg_row[0]["avg_daily"])) if avg_row else Decimal("0")
    cover = stock_qty / avg_daily if avg_daily != 0 else Decimal("0")
    return f"Stock: {stock_qty:.3f}, Cover days: {cover:.1f}"


async def build_daily_digest(engine: Engine, lang: str = "ar", warn_days: int = 90, crit_days: int = 30) -> str:
    today = date.today()
    # Near expiry
    expiry_stmt = f"""
        SELECT p.sku, b.batch_no, b.expiry_date, s.quantity
        FROM inventory.batch_record b
        JOIN master_data.master_product p ON p.id = b.product_id
        JOIN inventory.stock_balance s ON s.batch_id = b.id
        WHERE b.expiry_date <= :today + (:warn_days * INTERVAL '1 day')
          AND s.quantity > 0
        ORDER BY b.expiry_date ASC
        LIMIT 10
    """
    expiry_rows = await _run_query(
        engine,
        expiry_stmt,
        {"today": today, "warn_days": warn_days},
    )
    # Low stock
    low_stock_stmt = """
        SELECT p.sku, COALESCE(SUM(s.quantity),0) AS qty
        FROM master_data.master_product p
        JOIN inventory.stock_balance s ON s.product_id = p.id
        GROUP BY p.id
        HAVING COALESCE(SUM(s.quantity),0) <= 5
        ORDER BY qty ASC
        LIMIT 10
    """
    low_stock_rows = await _run_query(engine, low_stock_stmt, {})
    # Outstanding AR
    ar_stmt = """
        SELECT c.code, COALESCE(SUM(e.debit - e.credit),0) AS bal
        FROM master_data.master_customer c
        LEFT JOIN finance.ar_entry e ON e.customer_id = c.id
        GROUP BY c.id
        HAVING COALESCE(SUM(e.debit - e.credit),0) > 0
        ORDER BY bal DESC
        LIMIT 10
    """
    ar_rows = await _run_query(engine, ar_stmt, {})

    parts = ["📊 Daily Digest"]
    if expiry_rows:
        parts.append("\n⚠️ Near Expiry:")
        for r in expiry_rows:
            parts.append(f"{r['sku']} {r['batch_no']} {r['expiry_date']} qty:{r['quantity']}")
    if low_stock_rows:
        parts.append("\n📦 Low Stock:")
        for r in low_stock_rows:
            parts.append(f"{r['sku']} qty:{r['qty']}")
    if ar_rows:
        parts.append("\n💰 Outstanding AR:")
        for r in ar_rows:
            parts.append(f"{r['code']} bal:{Decimal(str(r['bal'])):.2f}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Bot construction
# --------------------------------------------------------------------------- #
def build_bot(settings: BotSettings) -> Bot:
    session = (
        AiohttpSession(api=TelegramAPIServer.from_base(settings.api_base))
        if settings.api_base
        else None
    )
    return Bot(token=settings.bot_token, session=session)


def build_dispatcher(settings: BotSettings, engine: Optional[Engine] = None) -> Dispatcher:
    dp = Dispatcher()
    router = Router()
    router.message.middleware(AllowlistAndRateLimitMiddleware(settings, engine or create_engine(settings.readonly_db_url, future=True, pool_pre_ping=True)))
    dp.include_router(router)

    # ------------------------------------------------------------------- #
    # Language command
    # ------------------------------------------------------------------- #
    @router.message(F.text.startswith("/lang"))
    async def set_lang(
        message: Message,
        lang_store: Dict[int, str],
        settings: BotSettings,
    ):
        parts = (message.text or "").split()
        if len(parts) < 2:
            await message.answer("Usage: /lang <en|ar>")
            return
        lang = parts[1].lower()
        if lang not in ("en", "ar"):
            await message.answer("Supported languages: en, ar")
            return
        user_id = message.from_user.id if message.from_user else 0
        lang_store[user_id] = lang
        if lang == "en":
            await message.answer("Language set to English.")
        else:
            await message.answer("تم ضبط اللغة إلى العربية.")

    # ------------------------------------------------------------------- #
    # Generic handler
    # ------------------------------------------------------------------- #
    @router.message()
    async def generic_handler(
        message: Message,
        erp_role: str,
        erp_scope_id: Optional[str],
        settings: BotSettings,
        db_engine: Engine,
        lang_store: Dict[int, str],
    ):
        raw = (message.text or "").strip()
        # Remove bot mention if present
        mention = f"@{settings.bot_username.lower()}"
        if mention in raw.lower():
            raw = raw.lower().replace(mention, "").strip()
        # Split and get command/template
        parts = raw.split()
        if not parts:
            return
        cmd = parts[0].lstrip("/").split("@", 1)[0].lower()
        lang = lang_store.get(message.from_user.id if message.from_user else 0, "ar")
        if cmd in ("start", "help"):
            if lang == "en":
                await message.answer("ElsebaeyPharma ERP Bot (read-only). Commands: /balance, /stock, /sales, /expiry, /targets, /cover, /alerts, /lang en|ar")
            else:
                await message.answer("بوت شركة السباعي فارما (للقراءة فقط). الأوامر: /balance /stock /sales /expiry /targets /cover /alerts /lang ar|en")
            return
        aliases = {"sales": "sales_today", "cover": "stock_cover"}
        template = aliases.get(cmd, cmd)
        try:
            from .queries import match_template  # type: ignore
        except Exception:
            match_template = lambda x: None
        matched = template if template in {"balance", "stock", "sales_today", "expiry", "targets", "stock_cover", "alerts"} else (match_template(raw) or template)

        if not await _check_permission(matched, erp_role, message, message.chat.type):
            return

        territory_scope = erp_scope_id if erp_role in ("medical_rep", "district_manager", "sales_manager") else None
        branch_scope = erp_scope_id if erp_role == "warehouse_staff" else None
        try:
            if matched == "balance":
                if len(parts) < 2:
                    await message.answer("Provide customer reference.")
                    return
                res = await query_balance(db_engine, parts[1], territory_scope, lang)
                await message.answer(f"Balance: {res}")
            elif matched == "stock":
                if len(parts) < 2:
                    await message.answer("Provide product reference.")
                    return
                res = await query_stock(db_engine, parts[1], branch_scope, lang)
                await message.answer(f"Stock: {res}")
            elif matched == "sales_today":
                res = await query_sales_today(db_engine, territory_scope, lang)
                await message.answer(f"Today's sales total: {res}")
            elif matched == "expiry":
                days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30
                res = await query_expiry(db_engine, days, branch_scope, lang)
                await message.answer(res)
            elif matched == "targets":
                if len(parts) < 2:
                    await message.answer("Provide target ID.")
                    return
                res = await query_targets(db_engine, parts[1], territory_scope, lang)
                await message.answer(res)
            elif matched == "stock_cover":
                if len(parts) < 2:
                    await message.answer("Provide product reference.")
                    return
                res = await query_stock_cover(db_engine, parts[1], lang)
                await message.answer(res)
            elif matched == "alerts":
                if not settings.alerts_enabled:
                    await message.answer("Daily alerts are disabled (TELEGRAM_ALERTS_ENABLED=false).")
                    return
                digest = await build_daily_digest(db_engine, lang)
                await message.answer(digest)
            else:
                await message.answer("Unknown command or not permitted.")
        except Exception as e:
            await message.answer(f"Error: {e}")
        except Exception as exc:
            await message.answer("An error occurred while processing your request.")
            # Log exception in real deployment

    return dp


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
async def run_polling(settings: BotSettings | None = None):
    settings = settings or BotSettings.from_env()
    bot = build_bot(settings)
    engine = create_engine(settings.readonly_db_url, future=True, pool_pre_ping=True)
    dp = build_dispatcher(settings, engine)
    await dp.start_polling(bot)
