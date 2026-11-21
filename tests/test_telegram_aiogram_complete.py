import asyncio
import os
import time
import uuid
import pytest
import sqlalchemy
from sqlalchemy import text, create_engine
from sqlalchemy.engine.url import make_url

aiogram = pytest.importorskip("aiogram")
from aiohttp import web
from aiogram import types

from app.telegram.aiogram_bot import BotSettings, build_bot, build_dispatcher


@pytest.fixture(scope="module")
def pg_role_engine():
    db_url = os.environ["DATABASE_URL"]
    admin_engine = create_engine(db_url)

    role_name = f"tg_ro_test_{uuid.uuid4().hex[:8]}"
    pwd = "tg_ro_pwd"

    with admin_engine.begin() as conn:
        # create read‑only role
        conn.execute(
            text(
                f"CREATE ROLE {role_name} NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN PASSWORD '{pwd}'"
            )
        )
        conn.execute(
            text(
                f"ALTER ROLE {role_name} SET default_transaction_read_only = on"
            )
        )
        conn.execute(
            text(
                f"GRANT USAGE ON SCHEMA master_data, inventory, sales, finance TO {role_name}"
            )
        )
        conn.execute(
            text(
                f"GRANT SELECT ON ALL TABLES IN SCHEMA master_data, inventory, sales, finance TO {role_name}"
            )
        )

        # deterministic UUIDs
        B1 = "11111111-1111-1111-1111-111111111111"
        B2 = "22222222-2222-2222-2222-222222222222"
        T1 = "33333333-3333-3333-3333-333333333333"
        T2 = "44444444-4444-4444-4444-444444444444"
        W1 = "55555555-5555-5555-5555-555555555555"
        W2 = "66666666-6666-6666-6666-666666666666"
        C1 = "77777777-7777-7777-7777-777777777777"
        C2 = "88888888-8888-8888-8888-888888888888"
        P1 = "99999999-9999-9999-9999-999999999999"
        BATCH1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        BATCH2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        OWNER_U = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        INV1 = "dddddddd-dddd-dddd-dddd-dddddddddddd"
        TARGET1 = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"

        # platform_user
        conn.execute(
            text(
                "INSERT INTO platform.platform_user (id, username, password_hash, role, is_owner, is_active) "
                "VALUES (:id, :username, :pwd_hash, :role, :is_owner, :is_active)"
            ),
            {
                "id": OWNER_U,
                "username": f"tg_owner_{uuid.uuid4().hex[:6]}",
                "pwd_hash": "x",
                "role": "owner",
                "is_owner": True,
                "is_active": True,
            },
        )

        # master_branch
        conn.execute(
            text(
                "INSERT INTO master_data.master_branch (id, code, name_ar) VALUES "
                "(:b1, 'TGB1', 'فرع1'), (:b2, 'TGB2', 'فرع2')"
            ),
            {"b1": B1, "b2": B2},
        )

        # master_territory
        conn.execute(
            text(
                "INSERT INTO master_data.master_territory (id, code, name_ar) VALUES "
                "(:t1, 'TGT1', 'منطقة1'), (:t2, 'TGT2', 'منطقة2')"
            ),
            {"t1": T1, "t2": T2},
        )

        # master_warehouse
        conn.execute(
            text(
                "INSERT INTO master_data.master_warehouse (id, branch_id, code, name_ar) VALUES "
                "(:w1, :b1, 'W1-TG', 'مخزن1'), (:w2, :b2, 'W2-TG', 'مخزن2')"
            ),
            {"w1": W1, "w2": W2, "b1": B1, "b2": B2},
        )

        # master_customer
        conn.execute(
            text(
                "INSERT INTO master_data.master_customer (id, code, name_ar, branch_id, territory_id) VALUES "
                "(:c1, 'CUST-TG-1', 'عميل1', :b1, :t1), "
                "(:c2, 'CUST-TG-2', 'عميل2', :b2, :t2)"
            ),
            {"c1": C1, "c2": C2, "b1": B1, "b2": B2, "t1": T1, "t2": T2},
        )

        # master_product
        conn.execute(
            text(
                "INSERT INTO master_data.master_product (id, sku, name_ar, base_price, vat_rate) VALUES "
                "(:p1, 'SKU-TG-1', 'صنف1', 114.00, 14.00)"
            ),
            {"p1": P1},
        )

        # batch_record
        conn.execute(
            text(
                "INSERT INTO inventory.batch_record (id, product_id, warehouse_id, batch_no, expiry_date) VALUES "
                "(:batch1, :p1, :w1, 'LOT-W1', CURRENT_DATE + INTERVAL '20 days'), "
                "(:batch2, :p1, :w2, 'LOT-W2', CURRENT_DATE + INTERVAL '20 days')"
            ),
            {"batch1": BATCH1, "batch2": BATCH2, "p1": P1, "w1": W1, "w2": W2},
        )

        # stock_balance
        conn.execute(
            text(
                "INSERT INTO inventory.stock_balance (warehouse_id, product_id, batch_id, quantity) VALUES "
                "(:w1, :p1, :batch1, 4.000), (:w2, :p1, :batch2, 9.000)"
            ),
            {"w1": W1, "w2": W2, "p1": P1, "batch1": BATCH1, "batch2": BATCH2},
        )

        # ar_entry
        conn.execute(
            text(
                "INSERT INTO finance.ar_entry (customer_id, entry_type, entry_date, debit, credit, note, created_by) VALUES "
                "(:c1, 'opening', CURRENT_DATE, 300.00, 0, 'tg', :owner), "
                "(:c2, 'opening', CURRENT_DATE, 500.00, 0, 'tg', :owner)"
            ),
            {"c1": C1, "c2": C2, "owner": OWNER_U},
        )

        # sales_invoice (draft -> line -> Posted per guard_terminal_line)
        conn.execute(
            text(
                "INSERT INTO sales.sales_invoice "
                "(id, invoice_no, branch_id, warehouse_id, customer_id, territory_id, "
                " invoice_date, posting_status, total_before_discount, total_discount, "
                " total_net, vat_amount, grand_total, created_by) "
                "VALUES (:inv1, :inv_no, :b1, :w1, :c1, :t1, "
                " CURRENT_DATE, 'Draft', 228.00, 0, 200.00, 28.00, 228.00, :owner)"
            ),
            {
                "inv1": INV1,
                "inv_no": f"TG-INV-{uuid.uuid4().hex[:6]}",
                "b1": B1,
                "w1": W1,
                "c1": C1,
                "t1": T1,
                "owner": OWNER_U,
            },
        )
        conn.execute(
            text(
                "INSERT INTO sales.sales_invoice_line "
                "(invoice_id, line_no, product_id, batch_id, quantity, unit_price, discount_pct, "
                " net_price, line_total, vat_rate, vat_amount) "
                "VALUES (:inv1, 1, :p1, :batch1, 2, 114.00, 0, 114.00, 228.00, 14.00, 28.00)"
            ),
            {"inv1": INV1, "p1": P1, "batch1": BATCH1},
        )
        conn.execute(
            text(
                "UPDATE sales.sales_invoice SET posting_status='Posted', posted_at=now(), posted_by=:owner WHERE id=:inv1"
            ),
            {"owner": OWNER_U, "inv1": INV1},
        )

        # sales_target
        conn.execute(
            text(
                "INSERT INTO sales.sales_target (id, territory_id, period_month, target_quantity, created_by) VALUES "
                "(:target1, :t1, date_trunc('month', CURRENT_DATE)::date, 100, :owner)"
            ),
            {"target1": TARGET1, "t1": T1, "owner": OWNER_U},
        )

    ro_engine = create_engine(
        make_url(db_url).set(username=role_name, password=pwd)
    )
    try:
        yield ro_engine
    finally:
        ro_engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA master_data, inventory, sales, finance FROM {role_name}"))
            conn.execute(text(f"REVOKE ALL PRIVILEGES ON SCHEMA master_data, inventory, sales, finance FROM {role_name}"))
            conn.execute(text(f"DROP ROLE IF EXISTS {role_name}"))
        admin_engine.dispose()


async def _run_with_mock_api(coro_fn):
    calls = []

    async def handler(request):
        method = request.match_info["method"]
        data = await request.post()
        calls.append((method, dict(data)))
        if method == "sendMessage":
            resp = {
                "ok": True,
                "result": {
                    "message_id": 1,
                    "date": int(time.time()),
                    "chat": {
                        "id": int(data.get("chat_id", 1)),
                        "type": "private",
                    },
                    "text": str(data.get("text", "")),
                },
            }
        elif method == "leaveChat":
            resp = {"ok": True, "result": True}
        else:
            resp = {"ok": True, "result": {}}
        return web.json_response(resp)

    app = web.Application()
    app.router.add_post("/bot{token}/{method}", handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    try:
        await coro_fn(base_url, calls)
    finally:
        await runner.cleanup()
    return calls


def _make_update(user_id: int, chat_id: int, text_str: str) -> types.Update:
    chat_type = "private" if chat_id > 0 else "group"
    msg = types.Message(
        message_id=1,
        date=int(time.time()),
        chat=types.Chat(id=chat_id, type=chat_type),
        from_user=types.User(id=user_id, is_bot=False, first_name="Test"),
        text=text_str,
    )
    upd = types.Update(update_id=uuid.uuid4().int & 0x7FFFFFFF, message=msg)
    return upd


async def _feed(dp, bot, user_id: int, chat_id: int, text_str: str):
    await dp.feed_update(bot, _make_update(user_id, chat_id, text_str))


def _last_text(calls) -> str:
    for method, data in reversed(calls):
        if method == "sendMessage":
            return data.get("text", "")
    return ""



def test_aiogram_private_allowlist_and_role_scoping_on_real_pg(pg_role_engine):
    async def scenario(base_url, calls):
        settings = BotSettings(
            bot_token="123456:TEST_SECRET_TOKEN_XYZ",
            readonly_db_url=str(pg_role_engine.url),
            allowed_user_ids=frozenset({1001, 1003, 1004}),
            allowed_chat_ids=frozenset({1}),
            user_roles={
                1001: ("owner", None),
                1003: ("medical_rep", "33333333-3333-3333-3333-333333333333"),
                1004: ("warehouse_staff", "11111111-1111-1111-1111-111111111111"),
            },
            api_base=base_url,
            rate_limit_max=20,
        )
        bot = build_bot(settings)
        dp = build_dispatcher(settings, engine=pg_role_engine)
        try:
            # Unauthorized user -> fail-closed, 0 outbound calls
            await _feed(dp, bot, 9999, 1, "/start")
            assert len(calls) == 0

            # Owner runs all commands against real PostgreSQL
            for cmd in (
                "/start",
                "/help",
                "/balance CUST-TG-1",
                "/balance CUST-TG-2",
                "/sales",
                "/stock SKU-TG-1",
                "/expiry 60",
                "/targets eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                "/cover SKU-TG-1",
            ):
                await _feed(dp, bot, 1001, 1, cmd)

            texts = [d.get("text", "") for m, d in calls if m == "sendMessage"]
            assert any("300.00" in t for t in texts)
            assert any("500.00" in t for t in texts)
            assert any("228.00" in t for t in texts)
            assert any("13.000" in t for t in texts)
            assert any("LOT-W1" in t and "LOT-W2" in t for t in texts)
            assert any("100" in t for t in texts)
            assert any("Cover days" in t and "13.000" in t for t in texts)

            # Medical rep (T1) sees T1 customer, CANNOT see T2 even with spoofed arg
            await _feed(dp, bot, 1003, 1, "/balance CUST-TG-1")
            assert "300.00" in _last_text(calls)

            await _feed(dp, bot, 1003, 1, "/balance CUST-TG-2 44444444-4444-4444-4444-444444444444")
            assert "500.00" not in _last_text(calls)

            # Warehouse staff (B1) sees ONLY B1 stock & expiry, denied balance & sales
            await _feed(dp, bot, 1004, 1, "/stock SKU-TG-1")
            t_stock = _last_text(calls)
            assert "4.000" in t_stock and "13.000" not in t_stock

            await _feed(dp, bot, 1004, 1, "/expiry 60")
            t_exp = _last_text(calls)
            assert "LOT-W1" in t_exp and "LOT-W2" not in t_exp

            await _feed(dp, bot, 1004, 1, "/balance CUST-TG-1")
            assert "permission" in _last_text(calls).lower()

            await _feed(dp, bot, 1004, 1, "/sales")
            assert "permission" in _last_text(calls).lower()
        finally:
            await bot.session.close()

    asyncio.run(_run_with_mock_api(scenario))


def test_aiogram_bilingual_ar_en_and_rate_limit_and_alerts(pg_role_engine):
    async def scenario(base_url, calls):
        settings = BotSettings(
            bot_token="123456:TEST_SECRET_TOKEN_XYZ",
            readonly_db_url=str(pg_role_engine.url),
            allowed_user_ids=frozenset({1001}),
            allowed_chat_ids=frozenset({1}),
            user_roles={1001: ("owner", None)},
            alerts_enabled=True,
            api_base=base_url,
            rate_limit_max=4,
            rate_limit_window_sec=60,
        )
        bot = build_bot(settings)
        dp = build_dispatcher(settings, engine=pg_role_engine)
        try:
            await _feed(dp, bot, 1001, 1, "/lang en")
            assert "English" in _last_text(calls)

            await _feed(dp, bot, 1001, 1, "/lang ar")
            assert "العربية" in _last_text(calls)

            await _feed(dp, bot, 1001, 1, "/alerts")
            digest = _last_text(calls)
            assert "LOT-W1" in digest and "300.00" in digest

            await _feed(dp, bot, 1001, 1, "/balance CUST-TG-1")
            assert "300.00" in _last_text(calls)

            # 5th request exceeds rate_limit_max=4
            await _feed(dp, bot, 1001, 1, "/balance CUST-TG-2")
            assert "rate limit" in _last_text(calls).lower()
        finally:
            await bot.session.close()

    asyncio.run(_run_with_mock_api(scenario))


def test_aiogram_group_mode_off_and_mention_mode_and_auto_leave(pg_role_engine):
    async def scenario(base_url, calls):
        # 1. Unauthorized group -> auto-leaveChat, zero sendMessage
        s1 = BotSettings(
            bot_token="123456:TEST_SECRET_TOKEN_XYZ",
            readonly_db_url=str(pg_role_engine.url),
            allowed_user_ids=frozenset(),
            allowed_chat_ids=frozenset(),
            user_roles={},
            group_mode_enabled=True,
            api_base=base_url,
        )
        bot = build_bot(s1)
        dp = build_dispatcher(s1, engine=pg_role_engine)
        try:
            await _feed(dp, bot, 1001, -99999, "/start")
            assert any(m == "leaveChat" for m, _ in calls)
            assert not any(m == "sendMessage" for m, _ in calls)
        finally:
            await bot.session.close()
        calls.clear()

        # 2. Authorized group with group_mode_enabled=False -> silent ignore
        s2 = BotSettings(
            bot_token="123456:TEST_SECRET_TOKEN_XYZ",
            readonly_db_url=str(pg_role_engine.url),
            allowed_user_ids=frozenset({1001}),
            allowed_chat_ids=frozenset({-5001}),
            user_roles={1001: ("owner", None)},
            group_mode_enabled=False,
            api_base=base_url,
        )
        bot = build_bot(s2)
        dp = build_dispatcher(s2, engine=pg_role_engine)
        try:
            await _feed(dp, bot, 1001, -5001, "@elsebaey_erp_bot expiry 60")
            assert len(calls) == 0
        finally:
            await bot.session.close()
        calls.clear()

        # 3. Authorized group with group_mode_enabled=True -> mention required + private-only blocked
        s3 = BotSettings(
            bot_token="123456:TEST_SECRET_TOKEN_XYZ",
            readonly_db_url=str(pg_role_engine.url),
            allowed_user_ids=frozenset({1001}),
            allowed_chat_ids=frozenset({-5001}),
            user_roles={1001: ("owner", None)},
            group_mode_enabled=True,
            api_base=base_url,
        )
        bot = build_bot(s3)
        dp = build_dispatcher(s3, engine=pg_role_engine)
        try:
            await _feed(dp, bot, 1001, -5001, "expiry 60")
            assert len(calls) == 0

            await _feed(dp, bot, 1001, -5001, "@elsebaey_erp_bot expiry 60")
            assert "LOT-W1" in _last_text(calls)

            await _feed(dp, bot, 1001, -5001, "@elsebaey_erp_bot /balance CUST-TG-1")
            assert "private chat" in _last_text(calls).lower()
        finally:
            await bot.session.close()

    asyncio.run(_run_with_mock_api(scenario))


def test_aiogram_readonly_db_role_cannot_mutate_or_read_private_auth(pg_role_engine):
    with pytest.raises(sqlalchemy.exc.DBAPIError):
        with pg_role_engine.begin() as conn:
            conn.execute(text("DELETE FROM finance.ar_entry WHERE 1=1"))

    with pytest.raises(sqlalchemy.exc.DBAPIError):
        with pg_role_engine.begin() as conn:
            conn.execute(text("SELECT * FROM platform.platform_user"))

    with pytest.raises(sqlalchemy.exc.DBAPIError):
        with pg_role_engine.begin() as conn:
            conn.execute(text("SELECT * FROM private.private_account_entry"))


def test_aiogram_sqli_and_safe_error_never_leaks_token_or_sql(pg_role_engine):
    async def scenario(base_url, calls):
        settings = BotSettings(
            bot_token="123456:TEST_SECRET_TOKEN_XYZ",
            readonly_db_url=str(pg_role_engine.url),
            allowed_user_ids=frozenset({1001}),
            allowed_chat_ids=frozenset({1}),
            user_roles={1001: ("owner", None)},
            api_base=base_url,
        )
        bot = build_bot(settings)
        dp = build_dispatcher(settings, engine=pg_role_engine)
        try:
            malicious = "/balance ' OR '1'='1; DROP TABLE finance.ar_entry;--"
            await _feed(dp, bot, 1001, 1, malicious)
            txt = _last_text(calls)
            assert "123456:TEST_SECRET_TOKEN_XYZ" not in txt
            assert "drop table" not in txt.lower()
            with pg_role_engine.begin() as conn:
                cnt = conn.execute(text("SELECT COUNT(*) FROM finance.ar_entry")).scalar()
                assert cnt >= 2
        finally:
            await bot.session.close()

    asyncio.run(_run_with_mock_api(scenario))


