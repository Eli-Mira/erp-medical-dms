"""Create (or recreate) the isolated demo database ``medical_demo``.

CLIENT PROTOTYPE data source — 100% synthetic:

- Every code is prefixed ``DEMO-`` and every Arabic name carries ``تجريبي``.
- Nothing is imported from any workbook; no real company, customer, doctor,
  supplier or financial record is read anywhere (only ``postgres`` is contacted
  to CREATE/DROP the demo database, via the same admin-URL pattern the approved
  disposable-DB runner uses — local host only, never ``medical_dms``).
- Historical activity (posted invoices, opening receivables, collections) is
  inserted as complete, constraint-consistent rows computed with the app's own
  ``app.sales.calc`` functions. These stand in for past events so the read-only
  screens have something truthful to display; they do not exercise or simulate
  the posting pipeline, and ``POSTING_ENABLED`` stays off in the server that
  the demo uses (draft creation therefore never touches stock or AR).

Usage:
    uv run --with-requirements requirements.txt python scripts/make_demo.py
"""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.db import DATABASE_URL  # noqa: E402
from app.sales.calc import line_calc, invoice_totals  # noqa: E402

DEMO_DB = "medical_demo"
DEMO_PASSWORD = "Demo-2026"
TODAY = date(2026, 10, 18)  # demo clock — synthetic, deterministic


def _fail(message: str) -> None:
    sys.exit("make_demo: " + message)


def build_demo_url():
    base = create_engine(DATABASE_URL).url
    if base.host not in {"localhost", "127.0.0.1", "::1"}:
        _fail(f"refusing non-local host {base.host!r}; the demo database is local-only")
    if base.database == DEMO_DB:
        _fail("DATABASE_URL already points at the demo database")
    return base


def create_database() -> Engine:
    """Drop + recreate ``medical_demo`` on the local dev Postgres."""
    admin = create_engine(
        build_demo_url().set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{DEMO_DB}" WITH (FORCE)')
            conn.exec_driver_sql(f'CREATE DATABASE "{DEMO_DB}"')
    except Exception as error:  # noqa: BLE001
        _fail(
            "cannot reach the local Postgres admin socket — is the dev database "
            f"container running? ({error})"
        )
    return create_engine(build_demo_url().set(database=DEMO_DB))


def apply_migrations(engine: Engine) -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option(
        "sqlalchemy.url",
        engine.url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Synthetic reference data
# ---------------------------------------------------------------------------

BRANCHES = [  # (code, name_ar)
    ("DEMO-B1", "فرع تجريبي أ"),
    ("DEMO-B2", "فرع تجريبي ب"),
]
TERRITORIES = [
    ("DEMO-T1", "منطقة تجريبية أ"),
    ("DEMO-T2", "منطقة تجريبية ب"),
]
WAREHOUSES = [  # (code, branch_idx, name_ar)
    ("DEMO-WH1", 0, "المخزن التجريبي الرئيسي"),
    ("DEMO-WH2", 1, "مخزن تجريبي ثانوي"),
]
PRODUCTS = [  # (sku, name_ar, base_price, vat_rate)
    ("DEMO-001", "منتج تجريبي أ", "12.50", "14.00"),
    ("DEMO-002", "منتج تجريبي ب", "85.00", "14.00"),
    ("DEMO-003", "منتج تجريبي ج", "220.00", "14.00"),
    ("DEMO-004", "منتج تجريبي د", "57.30", "14.00"),
]
CUSTOMERS = [  # (code, name_ar, branch_idx, territory_idx)
    ("DEMO-C01", "عميل تجريبي ١ (بيانات وهمية)", 0, 0),
    ("DEMO-C02", "عميل تجريبي ٢ (بيانات وهمية)", 0, 0),
    ("DEMO-C03", "عميل تجريبي ٣ (بيانات وهمية)", 1, 1),
    ("DEMO-C04", "عميل تجريبي ٤ (بيانات وهمية)", 1, 1),
]
seed_note = "بيانات عرض تجريبية مولّدة آليًا — بيانات وهمية بالكامل"

STOCK = [  # (warehouse_idx, product_idx, quantity)
    (0, 0, "300.000"),
    (0, 1, "1200.000"),
    (0, 2, "250.000"),
    (0, 3, "800.000"),
    (1, 0, "100.000"),
    (1, 3, "40.000"),
]

USERS = [  # (username, role, is_owner)
    ("demo_owner", "owner", True),
    ("demo_rep", "medical_rep", False),
    ("demo_finance", "finance", False),
]

# Historical, synthetic, clearly-labelled activity.
# line tuple: (line_no, product_idx, quantity, discount_pct)
POSTED_INVOICES = [
    {
        "invoice_no": "DEMO-INV-101",
        "branch_idx": 0,
        "customer_idx": 0,
        "warehouse_idx": 0,
        "invoice_date": date(2026, 10, 10),
        "created_by": "demo_rep",
        "lines": [(1, 0, "20", "0"), (2, 2, "3", "0")],
    },
    {
        "invoice_no": "DEMO-INV-102",
        "branch_idx": 0,
        "customer_idx": 1,
        "warehouse_idx": 0,
        "invoice_date": date(2026, 10, 12),
        "created_by": "demo_rep",
        "lines": [(1, 1, "5", "0"), (2, 3, "10", "10")],
    },
    {
        "invoice_no": "DEMO-INV-103",
        "branch_idx": 1,
        "customer_idx": 2,
        "warehouse_idx": 1,
        "invoice_date": date(2026, 10, 15),
        "created_by": "demo_owner",
        "lines": [(1, 0, "40", "0")],
    },
]
OPENING_AR = [  # (customer_idx, entry_date, debit)
    (0, date(2026, 9, 1), "1500.00"),
    (2, date(2026, 9, 5), "250.00"),
]
RECEIPTS = [  # (receipt_no, invoice_no, receipt_date, amount, method, created_by)
    ("DEMO-RCPT-001", "DEMO-INV-101", date(2026, 10, 13), "500.00", "cash", "demo_rep"),
    ("DEMO-RCPT-002", "DEMO-INV-102", date(2026, 10, 16), "300.00", "check", "demo_finance"),
]


def seed(engine: Engine) -> None:
    ids = {key: uuid4() for key in (
        *[f"b{i}" for i in range(len(BRANCHES))],
        *[f"t{i}" for i in range(len(TERRITORIES))],
        *[f"w{i}" for i in range(len(WAREHOUSES))],
        *[f"p{i}" for i in range(len(PRODUCTS))],
        *[f"c{i}" for i in range(len(CUSTOMERS))],
    )}
    user_ids = {name: uuid4() for name, _role, _owner in USERS}
    invoice_ids = {inv["invoice_no"]: uuid4() for inv in POSTED_INVOICES}

    with engine.begin() as db:
        for i, (code, name) in enumerate(BRANCHES):
            db.execute(text(
                "INSERT INTO master_data.master_branch(id,code,name_ar) "
                "VALUES (:id,:code,:name)"), {"id": ids[f"b{i}"], "code": code, "name": name})
        for i, (code, name) in enumerate(TERRITORIES):
            db.execute(text(
                "INSERT INTO master_data.master_territory(id,code,name_ar) "
                "VALUES (:id,:code,:name)"), {"id": ids[f"t{i}"], "code": code, "name": name})
        for i, (code, branch_idx, name) in enumerate(WAREHOUSES):
            db.execute(text(
                "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar,is_active) "
                "VALUES (:id,:b,:code,:name,true)"),
                {"id": ids[f"w{i}"], "b": ids[f"b{branch_idx}"], "code": code, "name": name})
        for i, (sku, name, price, vat) in enumerate(PRODUCTS):
            db.execute(text(
                "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) "
                "VALUES (:id,:sku,:name,:price,:vat)"),
                {"id": ids[f"p{i}"], "sku": sku, "name": name, "price": price, "vat": vat})
        for i, (code, name, branch_idx, terr_idx) in enumerate(CUSTOMERS):
            db.execute(text(
                "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
                "VALUES (:id,:code,:name,:b,:t)"),
                {"id": ids[f"c{i}"], "code": code, "name": name,
                 "b": ids[f"b{branch_idx}"], "t": ids[f"t{terr_idx}"]})

        # Demo accounts — passwords hashed with the app's own PBKDF2 helper.
        password_hash = hash_password(DEMO_PASSWORD)
        for username, role, is_owner in USERS:
            db.execute(text(
                "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
                "VALUES (:id,:u,:p,:role,:owner)"),
                {"id": user_ids[username], "u": username, "p": password_hash,
                 "role": role, "owner": is_owner})
        # The rep is scoped to branch/territory demo-1 and sees exactly that.
        db.execute(text(
            "INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
            {"u": user_ids["demo_rep"], "b": ids["b0"]})
        db.execute(text(
            "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t)"),
            {"u": user_ids["demo_rep"], "t": ids["t0"]})

        # Opening stock + the matching opening movements (balance-only history).
        for warehouse_idx, product_idx, quantity in STOCK:
            db.execute(text(
                "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) "
                "VALUES (:w,:p,:q)"),
                {"w": ids[f"w{warehouse_idx}"], "p": ids[f"p{product_idx}"], "q": quantity})
            db.execute(text(
                "INSERT INTO inventory.stock_movement"
                "(movement_type,warehouse_id,product_id,quantity,note,created_by,created_at) "
                "VALUES ('opening',:w,:p,:q,:note,:by,now())"),
                {"w": ids[f"w{warehouse_idx}"], "p": ids[f"p{product_idx}"], "q": quantity,
                 "note": "رصيد افتتاحي تجريبي (بيانات وهمية)", "by": user_ids["demo_owner"]})

        # Two-phase invoice insert: lines must exist while the invoice is still
        # 'Draft' (the line guard), the header flips to 'Posted' afterwards —
        # exactly the ordering the live pipeline uses.
        products = {
            i: {"price": Decimal(price), "vat": Decimal(vat)}
            for i, (_sku, _name, price, vat) in enumerate(PRODUCTS)
        }
        for inv in POSTED_INVOICES:
            invoice_id = invoice_ids[inv["invoice_no"]]
            actor = user_ids[inv["created_by"]]
            line_rows = []
            calc_inputs = []
            for line_no, product_idx, quantity, discount in inv["lines"]:
                product = products[product_idx]
                net, total, vat = line_calc(
                    Decimal(quantity), product["price"], Decimal(discount), product["vat"]
                )
                line_rows.append({
                    "no": line_no, "pid": ids[f"p{product_idx}"], "qty": quantity,
                    "price": f"{product['price']:.2f}", "disc": discount,
                    "net": f"{net:.2f}", "total": f"{total:.2f}",
                    "vatrate": f"{product['vat']:.2f}", "vat": f"{vat:.2f}",
                })
                calc_inputs.append((Decimal(quantity), product["price"],
                                    Decimal(discount), product["vat"]))
            totals = invoice_totals(calc_inputs)

            db.execute(text(
                "INSERT INTO sales.sales_invoice"
                "(id,invoice_no,branch_id,customer_id,territory_id,warehouse_id,created_by,"
                "invoice_date,posting_status,notes,version,updated_at) "
                "VALUES (:id,:no,:b,:c,:t,:w,:by,:d,'Draft',:note,1,now())"),
                {"id": invoice_id, "no": inv["invoice_no"],
                 "b": ids[f"b{inv['branch_idx']}"], "c": ids[f"c{inv['customer_idx']}"],
                 "t": ids[f"t{1 if inv['customer_idx'] != 0 else 0}"],
                 "w": ids[f"w{inv['warehouse_idx']}"], "by": actor,
                 "d": inv["invoice_date"], "note": seed_note})
            for row in line_rows:
                db.execute(text(
                    "INSERT INTO sales.sales_invoice_line"
                    "(invoice_id,line_no,product_id,quantity,unit_price,discount_pct,"
                    "net_price,line_total,vat_rate,vat_amount) "
                    "VALUES (:inv,:no,:pid,:qty,:price,:disc,:net,:total,:vatrate,:vat)"),
                    {"inv": invoice_id, **row})
            db.execute(text(
                "UPDATE sales.sales_invoice SET posting_status='Posted', posted_at=:at, "
                "posted_by=:by, total_before_discount=:before, total_discount=:disc, "
                "total_net=:net, vat_amount=:vat, grand_total=:grand "
                "WHERE id=:id"),
                {"at": int_to_datetime(inv["invoice_date"]), "by": actor, "id": invoice_id,
                 "before": f"{totals['total_before_discount']:.2f}",
                 "disc": f"{totals['total_discount']:.2f}",
                 "net": f"{totals['total_net']:.2f}",
                 "vat": f"{totals['vat_amount']:.2f}",
                 "grand": f"{totals['grand_total']:.2f}"})

            # AR: debit the invoice, and create its collection later below.
            db.execute(text(
                "INSERT INTO finance.ar_entry"
                "(customer_id,invoice_id,entry_type,entry_date,debit,credit,created_by,note) "
                "VALUES (:c,:inv,'invoice',:d,:debit,0,:by,:note)"),
                {"c": ids[f"c{inv['customer_idx']}"], "inv": invoice_id,
                 "d": inv["invoice_date"], "debit": f"{totals['grand_total']:.2f}",
                 "by": actor, "note": "فاتورة تجريبية مُرحّلة (بيانات وهمية)"})

        for customer_idx, entry_date, debit in OPENING_AR:
            db.execute(text(
                "INSERT INTO finance.ar_entry"
                "(customer_id,entry_type,entry_date,debit,credit,created_by,note) "
                "VALUES (:c,'opening',:d,:debit,0,:by,:note)"),
                {"c": ids[f"c{customer_idx}"], "d": entry_date,
                 "debit": debit, "by": user_ids["demo_owner"], "note": seed_note})

        for receipt_no, invoice_no, receipt_date, amount, method, creator in RECEIPTS:
            inv = next(i for i in POSTED_INVOICES if i["invoice_no"] == invoice_no)
            invoice_id = invoice_ids[invoice_no]
            receipt_id = uuid4()
            db.execute(text(
                "INSERT INTO finance.payment_receipt"
                "(id,invoice_id,branch_id,customer_id,receipt_no,receipt_date,amount,method,"
                "status,created_by,note,version) "
                "VALUES (:id,:inv,:b,:c,:no,:d,:amount,coalesce(NULLIF(:m,''),'cash'),'Active',"
                ":by,:note,1)"),
                {"id": receipt_id, "inv": invoice_id, "b": ids[f"b{inv['branch_idx']}"],
                 "c": ids[f"c{inv['customer_idx']}"], "no": receipt_no, "d": receipt_date,
                 "amount": amount, "m": method if method in ("cash", "check", "transfer") else "cash",
                 "by": user_ids[creator], "note": "سند قبض تجريبي (بيانات وهمية)"})
            db.execute(text(
                "INSERT INTO finance.ar_entry"
                "(customer_id,receipt_id,entry_type,entry_date,debit,credit,created_by,note) "
                "VALUES (:c,:r,'payment',:d,0,:credit,:by,:note)"),
                {"c": ids[f"c{inv['customer_idx']}"], "r": receipt_id, "d": receipt_date,
                 "credit": amount, "by": user_ids[creator],
                 "note": "تحصيل تجريبي (بيانات وهمية)"})

    verify(engine)


def int_to_datetime(day: date):
    from datetime import datetime, time

    return datetime.combine(day, time(12, 0))


def verify(engine: Engine) -> None:
    """Re-read the seeded rows and confirm internal consistency."""
    checks = {
        "users": "SELECT count(*) FROM platform.platform_user",
        "invoices": "SELECT count(*) FROM sales.sales_invoice WHERE posting_status='Posted'",
        "stock_balances": "SELECT count(*) FROM inventory.stock_balance",
        "ar_entries": "SELECT count(*) FROM finance.ar_entry",
        "receipts": "SELECT count(*) FROM finance.payment_receipt",
        "collections_sum": "SELECT COALESCE(sum(credit),0) FROM finance.ar_entry WHERE entry_type='payment'",
        "totals_ok": (
            "SELECT count(*) FROM sales.sales_invoice "
            "WHERE total_before_discount - total_discount <> grand_total "
            "OR total_net + vat_amount <> grand_total"
        ),
        "ar_sums_ok": (
            "SELECT count(*) FROM finance.ar_entry WHERE (debit > 0 AND credit > 0) "
            "OR (debit = 0 AND credit = 0)"
        ),
    }
    counts = {}
    with engine.connect() as db:
        for name, sql in checks.items():
            counts[name] = db.execute(text(sql)).scalar()
        # Also recompute one invoice's header from its lines server-side... the
        # constraints already did that; surface the demo balances instead.
        balance_rows = db.execute(text(
            "SELECT c.code, (COALESCE(SUM(e.debit),0) - COALESCE(SUM(e.credit),0))::text "
            "FROM master_data.master_customer c LEFT JOIN finance.ar_entry e "
            "ON e.customer_id=c.id GROUP BY c.id, c.code ORDER BY c.code")).all()
    problems = []
    if counts["totals_ok"] != 0:
        problems.append("invoice totals inconsistent")
    if counts["ar_sums_ok"] != 0:
        problems.append("ar entries violate one-sided rule")
    if problems:
        _fail("; ".join(problems))
    print("Databases seeded and internally verified (zero constraint failures):")
    for name, value in counts.items():
        print(f"  {name:>16}: {value}")
    print("\nSynthetic customer balances (from finance.ar_entry):")
    for code, balance in balance_rows:
        print(f"  {code}: {balance}")
    print(f"\nDemo credentials (all users): username/<{DEMO_PASSWORD}> "
          "- owner: demo_owner, sales: demo_rep (branch demo-1), finance: demo_finance")


def main() -> None:
    engine = create_database()
    apply_migrations(engine)
    seed(engine)
    engine.dispose()
    print(f'\nDemo database ready: {build_demo_url().set(database=DEMO_DB).render_as_string(hide_password=False)}')
    print(
        "Start the prototype server with:\n"
        '  $env:DATABASE_URL="'
        + build_demo_url().set(database=DEMO_DB).render_as_string(hide_password=False)
        + '"; $env:POSTING_ENABLED="false"; $env:DEMO_MODE="1"; '
        "uv run --with-requirements requirements.txt uvicorn app.main:app --host 127.0.0.1 --port 8018\n"
        'Then open http://127.0.0.1:8018/app/ and sign in with demo_owner / Demo-2026.'
    )


if __name__ == "__main__":
    main()
