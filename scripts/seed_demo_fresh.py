"""Seed the persistent synthetic demo database ``medical_demo_fresh``.

100% synthetic data: every customer, product, batch and visit below is invented.
Nothing is read from a workbook, and no real company, customer, doctor or
financial record is involved.

Idempotent: every row carries a deterministic ``uuid5`` id derived from a
natural key that does not contain "today", and every statement is an
``INSERT ... ON CONFLICT DO UPDATE``. Re-running rewrites the same rows and
refreshes expiry dates relative to ``date.today()``; it never duplicates them.
Only business columns are updated, so first-insert timestamps and password
hashes stay stable. ``inventory.stock_movement`` is an append-only ledger (a
database trigger rejects UPDATE and DELETE), so opening movements are inserted
once and never touched again: editing the quantities below therefore requires a
fresh database, and the integrity check flags any drift instead of hiding it.

Credentials come from the environment only — never from this file:

    DATABASE_URL        required; must point at a local ``medical_demo_fresh``
    SEED_USER_PASSWORD  optional; without it the demo users get an unusable
                        random password, so the database has no known login

Usage:
    DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5432/medical_demo_fresh \\
        uv run --with-requirements requirements.txt python scripts/seed_demo_fresh.py
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sys
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine.url import make_url  # noqa: E402

from app.auth.security import hash_password  # noqa: E402

REQUIRED_DATABASE = "medical_demo_fresh"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
NAMESPACE = "medical-demo-fresh"
REFERENCE_DATE = date.today()

# ---------------------------------------------------------------------------
# Synthetic reference data
# ---------------------------------------------------------------------------

BRANCHES = [  # (code, name_ar, name_en)
    ("BR-CAI", "فرع القاهرة", "Cairo Branch"),
    ("BR-GIZ", "فرع الجيزة", "Giza Branch"),
    ("BR-ALX", "فرع الإسكندرية", "Alexandria Branch"),
]

TERRITORIES = [  # (code, name_ar, name_en)
    ("TR-CAI-DT", "وسط القاهرة", "Downtown Cairo"),
    ("TR-CAI-NS", "مدينة نصر", "Nasr City"),
    ("TR-GIZ-DQ", "الدقي والمهندسين", "Dokki and Mohandessin"),
    ("TR-ALX-SM", "سموحة", "Smouha"),
]

WAREHOUSES = [  # (code, branch_code, name_ar, name_en)
    ("WH-CAI-01", "BR-CAI", "مخزن القاهرة الرئيسي", "Cairo Main Warehouse"),
    ("WH-GIZ-01", "BR-GIZ", "مخزن الجيزة", "Giza Warehouse"),
    ("WH-ALX-01", "BR-ALX", "مخزن الإسكندرية", "Alexandria Warehouse"),
]

PRODUCTS = [  # (sku, name_ar, name_en, base_price, vat_rate)
    ("AMX-500", "أموكسيسيلين 500 مجم كبسولات", "Amoxicillin 500 mg capsules", "45.00", "14.00"),
    ("PCM-500", "باراسيتامول 500 مجم أقراص", "Paracetamol 500 mg tablets", "12.50", "14.00"),
    ("OMP-20", "أوميبرازول 20 مجم كبسولات", "Omeprazole 20 mg capsules", "78.00", "14.00"),
    ("MTF-850", "ميتفورمين 850 مجم أقراص", "Metformin 850 mg tablets", "36.00", "14.00"),
    ("AML-5", "أملوديبين 5 مجم أقراص", "Amlodipine 5 mg tablets", "54.00", "14.00"),
    ("CTR-10", "سيتريزين 10 مجم أقراص", "Cetirizine 10 mg tablets", "22.00", "14.00"),
    ("DCF-50", "ديكلوفيناك 50 مجم أقراص", "Diclofenac 50 mg tablets", "18.75", "14.00"),
    ("SAL-100", "سالبيوتامول بخاخ 100 ميكروجرام", "Salbutamol inhaler 100 mcg", "96.00", "14.00"),
    ("INS-MIX", "أنسولين مخلوط 100 وحدة/مل", "Mixed insulin 100 IU/mL", "285.00", "0.00"),
    ("VD3-50K", "فيتامين د3 50000 وحدة أمبولات", "Vitamin D3 50,000 IU ampoules", "63.00", "14.00"),
    ("FE-200", "حديد 200 مجم أقراص", "Ferrous 200 mg tablets", "41.00", "14.00"),
    ("CIP-500", "سيبروفلوكساسين 500 مجم أقراص", "Ciprofloxacin 500 mg tablets", "88.00", "14.00"),
]

CUSTOMERS = [  # (code, name_ar, name_en, branch_code, territory_code)
    ("CUS-001", "صيدلية النور", "Al Nour Pharmacy", "BR-CAI", "TR-CAI-DT"),
    ("CUS-002", "صيدلية الشفاء", "Al Shifa Pharmacy", "BR-CAI", "TR-CAI-NS"),
    ("CUS-003", "مستشفى الأمل التخصصي", "Al Amal Specialist Hospital", "BR-CAI", "TR-CAI-DT"),
    ("CUS-004", "عيادة د. حسن عبد الرحمن", "Dr Hassan Abdelrahman Clinic", "BR-GIZ", "TR-GIZ-DQ"),
    ("CUS-005", "صيدلية الرحمة", "Al Rahma Pharmacy", "BR-GIZ", "TR-GIZ-DQ"),
    ("CUS-006", "مركز السلام الطبي", "Al Salam Medical Centre", "BR-ALX", "TR-ALX-SM"),
    ("CUS-007", "صيدلية الهدى", "Al Huda Pharmacy", "BR-CAI", "TR-CAI-NS"),
    ("CUS-008", "مستشفى الحياة", "Al Hayat Hospital", "BR-GIZ", "TR-GIZ-DQ"),
    ("CUS-009", "صيدلية ابن سينا", "Ibn Sina Pharmacy", "BR-ALX", "TR-ALX-SM"),
    ("CUS-010", "مركز النيل للأشعة", "Nile Radiology Centre", "BR-CAI", "TR-CAI-DT"),
]

USERS = [  # (username, role, is_owner, first_name, last_name, branch_codes, territory_codes)
    (
        "fresh_owner", "owner", True, "هالة", "منصور",
        ("BR-CAI", "BR-GIZ", "BR-ALX"),
        ("TR-CAI-DT", "TR-CAI-NS", "TR-GIZ-DQ", "TR-ALX-SM"),
    ),
    ("fresh_rep_mona", "medical_rep", False, "منى", "عبد الله",
     ("BR-CAI",), ("TR-CAI-DT", "TR-CAI-NS")),
    ("fresh_rep_ahmed", "medical_rep", False, "أحمد", "سعيد",
     ("BR-GIZ", "BR-ALX"), ("TR-GIZ-DQ", "TR-ALX-SM")),
]

# (sku, warehouse_code, days_to_expiry, shelf_life_days, quantity)
# The short-dated entries are the intentional near-expiry stock: AMX-500 in Cairo
# (38 days), SAL-100 in Cairo (21 days) and OMP-20 in Giza (64 days).
BATCHES = [
    ("AMX-500", "WH-CAI-01", 38, 730, 420),
    ("AMX-500", "WH-CAI-01", 430, 730, 180),
    ("PCM-500", "WH-CAI-01", 610, 730, 900),
    ("PCM-500", "WH-CAI-01", 540, 730, 250),
    ("OMP-20", "WH-CAI-01", 365, 730, 260),
    ("OMP-20", "WH-CAI-01", 300, 730, 90),
    ("MTF-850", "WH-CAI-01", 275, 730, 380),
    ("AML-5", "WH-CAI-01", 335, 730, 300),
    ("CTR-10", "WH-CAI-01", 215, 730, 540),
    ("DCF-50", "WH-CAI-01", 490, 730, 610),
    ("SAL-100", "WH-CAI-01", 21, 365, 150),
    ("INS-MIX", "WH-CAI-01", 150, 540, 90),
    ("VD3-50K", "WH-CAI-01", 305, 730, 200),
    ("FE-200", "WH-CAI-01", 455, 730, 320),
    ("CIP-500", "WH-CAI-01", 245, 730, 180),
    ("AMX-500", "WH-GIZ-01", 185, 730, 260),
    ("PCM-500", "WH-GIZ-01", 395, 730, 480),
    ("OMP-20", "WH-GIZ-01", 64, 730, 140),
    ("MTF-850", "WH-GIZ-01", 305, 730, 210),
    ("AML-5", "WH-GIZ-01", 365, 730, 160),
    ("CTR-10", "WH-GIZ-01", 275, 730, 300),
    ("DCF-50", "WH-GIZ-01", 425, 730, 340),
    ("SAL-100", "WH-GIZ-01", 90, 365, 80),
    ("AMX-500", "WH-ALX-01", 215, 730, 190),
    ("PCM-500", "WH-ALX-01", 335, 730, 350),
    ("OMP-20", "WH-ALX-01", 155, 730, 110),
    ("CIP-500", "WH-ALX-01", 275, 730, 120),
    ("VD3-50K", "WH-ALX-01", 365, 730, 130),
    ("FE-200", "WH-ALX-01", 490, 730, 170),
]

# One field visit per entry unless the same customer repeats (history).
# line: (sku, quantity_prev, quantity_delivered, quantity_returned, quantity_current)
# Successive lines for one customer carry the previous count forward, so the
# sell-through chain is internally consistent.
VISITS = [
    {
        "customer": "CUS-001",
        "rep": "fresh_rep_mona",
        "days_ago": 14,
        "notes": "زيارة دورية — جرد افتتاحي لرف الصيدلية",
        "lines": [("AMX-500", 0, 80, 0, 60), ("PCM-500", 0, 100, 0, 70)],
    },
    {
        "customer": "CUS-001",
        "rep": "fresh_rep_mona",
        "days_ago": 7,
        "notes": "متابعة المخزون والقطع القريب من الانتهاء",
        "lines": [("AMX-500", 60, 120, 0, 95), ("PCM-500", 70, 200, 0, 180)],
    },
    {
        "customer": "CUS-002",
        "rep": "fresh_rep_ahmed",
        "days_ago": 6,
        "notes": "تحصيل طلبية الشهر ومراجعة البدائل",
        "lines": [("OMP-20", 40, 60, 0, 55), ("CTR-10", 80, 100, 10, 120)],
    },
    {
        "customer": "CUS-003",
        "rep": "fresh_rep_mona",
        "days_ago": 5,
        "notes": "مستشفى — صرف قسم الباطنة والطوارئ",
        "lines": [("INS-MIX", 20, 40, 0, 25), ("DCF-50", 100, 150, 0, 90)],
    },
    {
        "customer": "CUS-004",
        "rep": "fresh_rep_ahmed",
        "days_ago": 4,
        "notes": "عيادة — متابعة أصناف السكر والضغط",
        "lines": [("AML-5", 30, 60, 0, 42), ("MTF-850", 50, 80, 0, 60)],
    },
    {
        "customer": "CUS-005",
        "rep": "fresh_rep_ahmed",
        "days_ago": 3,
        "notes": "مرتجع بخاخات تالفة من الشحنة السابقة",
        "lines": [("SAL-100", 12, 24, 2, 10)],
    },
    {
        "customer": "CUS-007",
        "rep": "fresh_rep_mona",
        "days_ago": 2,
        "notes": "صيدلية — تنشيط أصناف الفيتامينات",
        "lines": [("VD3-50K", 25, 40, 0, 30), ("FE-200", 45, 60, 0, 50)],
    },
    {
        "customer": "CUS-006",
        "rep": "fresh_rep_mona",
        "days_ago": 1,
        "notes": "مركز طبي — مرتجع صلاحية ومطالبة تحصيل",
        "lines": [("CIP-500", 35, 50, 5, 30), ("AMX-500", 20, 40, 0, 18)],
    },
    {
        "customer": "CUS-009",
        "rep": "fresh_rep_ahmed",
        "days_ago": 0,
        "notes": "زيارة اليوم — جرد سريع قبل نهاية الشهر",
        "lines": [("PCM-500", 90, 120, 0, 110)],
    },
]

CREDIT_CUSTOMERS = {"CUS-003", "CUS-004", "CUS-006", "CUS-008", "CUS-010"}
CUSTOMER_BRANCH = {customer[0]: customer[3] for customer in CUSTOMERS}
BRANCH_WAREHOUSE = {warehouse[1]: warehouse[0] for warehouse in WAREHOUSES}
WAREHOUSE_TOKEN = {"WH-CAI-01": "CAI", "WH-GIZ-01": "GIZ", "WH-ALX-01": "ALX"}
PRICE_BY_SKU = {product[0]: Decimal(product[3]) for product in PRODUCTS}

ROW_COUNT_QUERIES = [
    ("branches", "SELECT count(*) FROM master_data.master_branch"),
    ("territories", "SELECT count(*) FROM master_data.master_territory"),
    ("warehouses", "SELECT count(*) FROM master_data.master_warehouse"),
    ("products", "SELECT count(*) FROM master_data.master_product"),
    ("customers", "SELECT count(*) FROM master_data.master_customer"),
    ("users", "SELECT count(*) FROM platform.platform_user"),
    ("batches", "SELECT count(*) FROM inventory.batch_record"),
    ("stock_balance", "SELECT count(*) FROM inventory.stock_balance"),
    ("stock_movement", "SELECT count(*) FROM inventory.stock_movement"),
    ("visits", "SELECT count(*) FROM sales.customer_stock_visit"),
    ("visit_lines", "SELECT count(*) FROM sales.customer_stock_visit_line"),
    ("held_stock", "SELECT count(*) FROM sales.customer_held_stock"),
]

DIGEST_QUERIES = [
    "SELECT id::text, code, name_ar FROM master_data.master_branch ORDER BY id",
    "SELECT id::text, code, name_ar FROM master_data.master_territory ORDER BY id",
    "SELECT id::text, code, branch_id::text FROM master_data.master_warehouse ORDER BY id",
    "SELECT id::text, sku, base_price, vat_rate, is_active FROM master_data.master_product ORDER BY id",
    "SELECT id::text, code, branch_id::text, territory_id::text FROM master_data.master_customer ORDER BY id",
    "SELECT id::text, username, role, is_owner FROM platform.platform_user ORDER BY id",
    "SELECT id::text, product_id::text, warehouse_id::text, batch_no, expiry_date "
    "FROM inventory.batch_record ORDER BY id",
    "SELECT id::text, warehouse_id::text, product_id::text, batch_id::text, quantity "
    "FROM inventory.stock_balance ORDER BY id",
    "SELECT id::text, movement_type, quantity, unit_cost FROM inventory.stock_movement ORDER BY id",
    "SELECT id::text, customer_id::text, rep_id::text, visit_date "
    "FROM sales.customer_stock_visit ORDER BY id",
    "SELECT id::text, visit_id::text, product_id::text, quantity_prev, quantity_delivered, "
    "quantity_returned, quantity_current, sell_through, amount "
    "FROM sales.customer_stock_visit_line ORDER BY id",
    "SELECT id::text, customer_id::text, product_id::text, batch_id::text, quantity_on_hand, "
    "last_visit_id::text FROM sales.customer_held_stock ORDER BY id",
]

INTEGRITY_CHECKS = [
    (
        "balance = sum(movements)",
        """
        SELECT count(*) FROM inventory.stock_balance b
        WHERE b.quantity <> (
            SELECT COALESCE(sum(m.quantity), 0) FROM inventory.stock_movement m
            WHERE m.warehouse_id = b.warehouse_id AND m.product_id = b.product_id
              AND m.batch_id IS NOT DISTINCT FROM b.batch_id
        )
        """,
    ),
    (
        "held = latest visit count",
        """
        WITH latest AS (
            SELECT DISTINCT ON (v.customer_id, l.product_id)
                   v.customer_id, l.product_id, l.batch_id, l.quantity_current
            FROM sales.customer_stock_visit_line l
            JOIN sales.customer_stock_visit v ON v.id = l.visit_id
            ORDER BY v.customer_id, l.product_id, v.visit_date DESC, l.id DESC
        )
        SELECT count(*) FROM latest
        JOIN sales.customer_held_stock h
          ON h.customer_id = latest.customer_id AND h.product_id = latest.product_id
        WHERE h.batch_id IS NOT DISTINCT FROM latest.batch_id
          AND h.quantity_on_hand <> latest.quantity_current
        """,
    ),
    (
        "sell-through formula holds",
        """
        SELECT count(*) FROM sales.customer_stock_visit_line
        WHERE sell_through <> quantity_prev + quantity_delivered
                           - quantity_returned - quantity_current
        """,
    ),
]


def _fail(message: str) -> None:
    sys.exit("seed_demo_fresh: " + message)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _id(*parts: object) -> str:
    """Deterministic uuid5 for one seeded row."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join([NAMESPACE, *map(str, parts)])))


def _connect():
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        _fail("DATABASE_URL is required; credentials must come from the environment")
    url = make_url(raw)
    if url.host not in LOCAL_HOSTS:
        _fail(f"refusing non-local host {url.host!r}; this seed is local-only")
    if url.database == "medical_dms":
        _fail("refusing the protected database medical_dms")
    if url.database != REQUIRED_DATABASE:
        _fail(f"DATABASE_URL names {url.database!r}; expected {REQUIRED_DATABASE!r}")
    engine = create_engine(raw, future=True)
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
    if revision is None:
        _fail("alembic_version is empty — run `alembic upgrade head` first")
    print(f"target: {url.host}:{url.port}/{url.database} · schema revision {revision}")
    return engine


def _upsert(db, table: str, row: dict, conflict: str, update: list[str]) -> None:
    """Insert one hard-coded row, updating the listed business columns on conflict.

    ``table``, the column names and the conflict clause are module constants; no
    value from the environment or the database is interpolated into SQL. An empty
    ``update`` list means "insert once, never touch again", which the append-only
    ledger triggers require.
    """
    statement = (
        f"INSERT INTO {table} ({', '.join(row)}) "
        f"VALUES ({', '.join(':' + column for column in row)}) "
        f"ON CONFLICT {conflict} "
    )
    if update:
        assignments = ", ".join(f"{column} = EXCLUDED.{column}" for column in update)
        statement += f"DO UPDATE SET {assignments}"
    else:
        statement += "DO NOTHING"
    db.execute(text(statement), row)


def _row_id(db, table: str, **natural_key: str) -> str:
    clause = " AND ".join(f"{column} = :{column}" for column in natural_key)
    return db.execute(
        text(f"SELECT id FROM {table} WHERE {clause}"), natural_key
    ).scalar_one()


def seed(engine) -> None:
    now = datetime.now(timezone.utc)
    password = os.environ.get("SEED_USER_PASSWORD") or secrets.token_urlsafe(32)

    branch_ids: dict[str, str] = {}
    territory_ids: dict[str, str] = {}
    warehouse_ids: dict[str, str] = {}
    product_ids: dict[str, str] = {}
    customer_ids: dict[str, str] = {}
    user_ids: dict[str, str] = {}
    batch_rows: list[dict] = []
    batches_by_warehouse_sku: dict[tuple[str, str], list[dict]] = defaultdict(list)

    with engine.begin() as db:
        for code, name_ar, name_en in BRANCHES:
            _upsert(
                db, "master_data.master_branch",
                {"id": _id("branch", code), "code": code, "name_ar": name_ar,
                 "name_en": name_en},
                "(code)", ["name_ar", "name_en"],
            )
            branch_ids[code] = _row_id(db, "master_data.master_branch", code=code)

        for code, name_ar, name_en in TERRITORIES:
            _upsert(
                db, "master_data.master_territory",
                {"id": _id("territory", code), "code": code, "name_ar": name_ar,
                 "name_en": name_en},
                "(code)", ["name_ar", "name_en"],
            )
            territory_ids[code] = _row_id(db, "master_data.master_territory", code=code)

        for code, branch_code, name_ar, name_en in WAREHOUSES:
            _upsert(
                db, "master_data.master_warehouse",
                {"id": _id("warehouse", code), "branch_id": branch_ids[branch_code],
                 "code": code, "name_ar": name_ar, "name_en": name_en,
                 "is_active": True},
                "(branch_id, code)", ["name_ar", "name_en", "is_active"],
            )
            warehouse_ids[code] = _row_id(
                db, "master_data.master_warehouse", code=code
            )

        for sku, name_ar, name_en, price, vat in PRODUCTS:
            _upsert(
                db, "master_data.master_product",
                {"id": _id("product", sku), "sku": sku, "name_ar": name_ar,
                 "name_en": name_en, "base_price": Decimal(price),
                 "vat_rate": Decimal(vat), "is_active": True},
                "(sku)", ["name_ar", "name_en", "base_price", "vat_rate", "is_active"],
            )
            product_ids[sku] = _row_id(db, "master_data.master_product", sku=sku)

        for code, name_ar, name_en, branch_code, territory_code in CUSTOMERS:
            _upsert(
                db, "master_data.master_customer",
                {"id": _id("customer", code), "code": code, "name_ar": name_ar,
                 "name_en": name_en, "branch_id": branch_ids[branch_code],
                 "territory_id": territory_ids[territory_code], "is_active": True},
                "(code)",
                ["name_ar", "name_en", "branch_id", "territory_id", "is_active"],
            )
            customer_ids[code] = _row_id(db, "master_data.master_customer", code=code)

        for username, role, is_owner, first, last, branches, territories in USERS:
            # password_hash is deliberately not in the update list: a re-run must
            # not rotate the credential, and no credential is stored in this file.
            _upsert(
                db, "platform.platform_user",
                {"id": _id("user", username), "username": username,
                 "password_hash": hash_password(password), "first_name": first,
                 "last_name": last, "role": role, "is_owner": is_owner,
                 "is_active": True},
                "(username)",
                ["first_name", "last_name", "role", "is_owner", "is_active"],
            )
            user_ids[username] = _row_id(db, "platform.platform_user", username=username)
            for branch_code in branches:
                db.execute(
                    text("INSERT INTO platform.user_branch(user_id, branch_id) "
                         "VALUES (:user_id, :branch_id) ON CONFLICT DO NOTHING"),
                    {"user_id": user_ids[username], "branch_id": branch_ids[branch_code]},
                )
            for territory_code in territories:
                db.execute(
                    text("INSERT INTO platform.user_territory(user_id, territory_id) "
                         "VALUES (:user_id, :territory_id) ON CONFLICT DO NOTHING"),
                    {"user_id": user_ids[username],
                     "territory_id": territory_ids[territory_code]},
                )

        # Batch numbers are positional, not date-derived, so a re-run on another
        # day updates the same row instead of creating a second batch.
        sequence: dict[tuple[str, str], int] = defaultdict(int)
        for sku, warehouse_code, days_to_expiry, shelf_life, quantity in BATCHES:
            sequence[(warehouse_code, sku)] += 1
            batch_no = (
                f"{sku}-{WAREHOUSE_TOKEN[warehouse_code]}-"
                f"{sequence[(warehouse_code, sku)]:02d}"
            )
            expiry = REFERENCE_DATE + timedelta(days=days_to_expiry)
            _upsert(
                db, "inventory.batch_record",
                {"id": _id("batch", warehouse_code, batch_no),
                 "product_id": product_ids[sku],
                 "warehouse_id": warehouse_ids[warehouse_code],
                 "batch_no": batch_no,
                 "manufacture_date": expiry - timedelta(days=shelf_life),
                 "expiry_date": expiry},
                "(product_id, warehouse_id, batch_no)",
                ["manufacture_date", "expiry_date"],
            )
            batch = {
                "sku": sku,
                "warehouse_code": warehouse_code,
                "batch_no": batch_no,
                "quantity": Decimal(quantity),
                "expiry": expiry,
                "id": _row_id(
                    db, "inventory.batch_record",
                    product_id=product_ids[sku],
                    warehouse_id=warehouse_ids[warehouse_code],
                    batch_no=batch_no,
                ),
            }
            batch_rows.append(batch)
            batches_by_warehouse_sku[(warehouse_code, sku)].append(batch)

        for batch in batch_rows:
            _upsert(
                db, "inventory.stock_balance",
                {"id": _id("balance", batch["warehouse_code"], batch["batch_no"]),
                 "warehouse_id": warehouse_ids[batch["warehouse_code"]],
                 "product_id": product_ids[batch["sku"]],
                 "batch_id": batch["id"],
                 "quantity": batch["quantity"]},
                "(warehouse_id, product_id, batch_id) WHERE batch_id IS NOT NULL",
                ["quantity"],
            )
            _upsert(
                db, "inventory.stock_movement",
                {"id": _id("movement", batch["warehouse_code"], batch["batch_no"]),
                 "warehouse_id": warehouse_ids[batch["warehouse_code"]],
                 "product_id": product_ids[batch["sku"]],
                 "batch_id": batch["id"],
                 "movement_type": "opening",
                 "quantity": batch["quantity"],
                 "unit_cost": _money(PRICE_BY_SKU[batch["sku"]] * Decimal("0.62")),
                 "note": "رصيد افتتاحي تجريبي",
                 "created_by": user_ids["fresh_owner"],
                 "created_at": now - timedelta(days=60)},
                "(id)",
                [],
            )

        # FEFO: a rep hands over the earliest-expiring batch first.
        for batch_list in batches_by_warehouse_sku.values():
            batch_list.sort(key=lambda item: (item["expiry"], item["batch_no"]))

        def pick_batch(warehouse_code: str, sku: str) -> dict:
            candidates = batches_by_warehouse_sku[(warehouse_code, sku)]
            return next((item for item in candidates if item["quantity"] > 0), candidates[0])

        latest_line: dict[tuple[str, str], dict] = {}

        for spec in VISITS:
            customer_code = spec["customer"]
            rep = spec["rep"]
            visit_date = REFERENCE_DATE - timedelta(days=spec["days_ago"])
            warehouse_code = BRANCH_WAREHOUSE[CUSTOMER_BRANCH[customer_code]]

            _upsert(
                db, "sales.customer_stock_visit",
                {"id": _id("visit", customer_code, rep, spec["days_ago"]),
                 "customer_id": customer_ids[customer_code],
                 "rep_id": user_ids[rep],
                 "visit_date": visit_date,
                 "notes": spec["notes"],
                 "created_by": user_ids[rep]},
                "(id)",
                ["customer_id", "rep_id", "visit_date", "notes", "created_by"],
            )
            visit_id = _row_id(
                db, "sales.customer_stock_visit",
                customer_id=customer_ids[customer_code], rep_id=user_ids[rep],
                visit_date=visit_date,
            )

            for sku, previous, delivered, returned, current in spec["lines"]:
                sell_through = previous + delivered - returned - current
                if sell_through < 0:
                    _fail(
                        f"{customer_code}/{sku}: sell-through would be negative "
                        f"({previous} + {delivered} - {returned} - {current})"
                    )
                batch = pick_batch(warehouse_code, sku)
                amount = _money(Decimal(delivered) * PRICE_BY_SKU[sku])
                _upsert(
                    db, "sales.customer_stock_visit_line",
                    {"id": _id("visit_line", customer_code, rep, spec["days_ago"], sku),
                     "visit_id": visit_id,
                     "product_id": product_ids[sku],
                     "batch_id": batch["id"],
                     "quantity_prev": Decimal(previous),
                     "quantity_delivered": Decimal(delivered),
                     "quantity_returned": Decimal(returned),
                     "quantity_current": Decimal(current),
                     "sell_through": Decimal(sell_through),
                     "amount": amount,
                     "payment_method": (
                         "credit" if customer_code in CREDIT_CUSTOMERS else "cash"
                     )},
                    "(visit_id, product_id)",
                    ["batch_id", "quantity_prev", "quantity_delivered",
                     "quantity_returned", "quantity_current", "sell_through",
                     "amount", "payment_method"],
                )
                key = (customer_code, sku)
                if key not in latest_line or spec["days_ago"] < latest_line[key]["days_ago"]:
                    latest_line[key] = {
                        "days_ago": spec["days_ago"],
                        "visit_id": visit_id,
                        "batch": batch,
                        "current": Decimal(current),
                    }

        # Held stock mirrors the newest visit line for every customer/product.
        for (customer_code, sku), line in latest_line.items():
            _upsert(
                db, "sales.customer_held_stock",
                {"id": _id("held", customer_code, sku, line["batch"]["batch_no"]),
                 "customer_id": customer_ids[customer_code],
                 "product_id": product_ids[sku],
                 "batch_id": line["batch"]["id"],
                 "quantity_on_hand": line["current"],
                 "last_visit_id": line["visit_id"]},
                "ON CONSTRAINT uq_customer_held_stock_tuple",
                ["quantity_on_hand", "last_visit_id"],
            )


def digest(engine) -> str:
    parts: list[str] = []
    with engine.connect() as connection:
        for statement in DIGEST_QUERIES:
            for row in connection.execute(text(statement)):
                parts.append("|".join("" if value is None else str(value) for value in row))
    return hashlib.md5("\n".join(parts).encode("utf-8")).hexdigest()


def report(engine) -> None:
    with engine.connect() as connection:
        counts = {
            label: connection.execute(text(statement)).scalar_one()
            for label, statement in ROW_COUNT_QUERIES
        }
        print("\nrows: " + " · ".join(f"{label} {count}" for label, count in counts.items()))

        print("\nstock by warehouse")
        for row in connection.execute(text("""
            SELECT w.code, w.name_en, count(DISTINCT b.product_id) AS products,
                   count(DISTINCT b.id) AS batches, COALESCE(sum(sb.quantity), 0) AS units
            FROM master_data.master_warehouse w
            JOIN inventory.batch_record b ON b.warehouse_id = w.id
            LEFT JOIN inventory.stock_balance sb ON sb.batch_id = b.id
            GROUP BY w.code, w.name_en ORDER BY w.code
        """)):
            print(f"  {row[0]:<11} {row[1]:<24} products {row[2]:>2} · batches {row[3]:>2} · units {row[4]:>7}")

        print("\nnear expiry (<= 90 days)")
        near = connection.execute(text("""
            SELECT p.sku, p.name_ar, b.batch_no, b.expiry_date,
                   b.expiry_date - CURRENT_DATE AS days_left,
                   w.code, COALESCE(sb.quantity, 0)
            FROM inventory.batch_record b
            JOIN master_data.master_product p ON p.id = b.product_id
            JOIN master_data.master_warehouse w ON w.id = b.warehouse_id
            LEFT JOIN inventory.stock_balance sb ON sb.batch_id = b.id
            WHERE b.expiry_date <= CURRENT_DATE + 90
            ORDER BY b.expiry_date
        """)).fetchall()
        for row in near:
            print(f"  {row[0]:<8} {row[2]:<14} {row[3]}  {row[4]:>3}d  {row[5]:<11} on hand {row[6]:>6}  {row[1]}")

        print("\ncustomers · visits · held stock")
        # Subqueries, not joins: joining visits and held rows multiplies both and
        # makes sum(DISTINCT ...) silently undercount equal quantities.
        for row in connection.execute(text("""
            SELECT c.code, c.name_ar,
                   (SELECT count(*) FROM sales.customer_stock_visit v
                     WHERE v.customer_id = c.id) AS visits,
                   (SELECT count(*) FROM sales.customer_held_stock h
                     WHERE h.customer_id = c.id) AS held_rows,
                   (SELECT COALESCE(sum(h.quantity_on_hand), 0)
                      FROM sales.customer_held_stock h
                     WHERE h.customer_id = c.id) AS held_units
            FROM master_data.master_customer c
            ORDER BY c.code
        """)):
            print(f"  {row[0]:<8} {row[1]:<30} visits {row[2]:>2} · held rows {row[3]:>2} · units {row[4]:>6}")

        print("\nheld stock detail")
        for row in connection.execute(text("""
            SELECT c.code, p.sku, b.batch_no, h.quantity_on_hand,
                   b.expiry_date - CURRENT_DATE AS days_left, v.visit_date
            FROM sales.customer_held_stock h
            JOIN master_data.master_customer c ON c.id = h.customer_id
            JOIN master_data.master_product p ON p.id = h.product_id
            LEFT JOIN inventory.batch_record b ON b.id = h.batch_id
            LEFT JOIN sales.customer_stock_visit v ON v.id = h.last_visit_id
            ORDER BY b.expiry_date, c.code
        """)):
            print(f"  {row[0]:<8} {row[1]:<8} {row[2] or '-':<14} on hand {row[3]:>5} · "
                  f"expires in {row[4]:>3}d · last visit {row[5]}")

        print("\nlatest sell-through lines")
        for row in connection.execute(text("""
            SELECT c.code, p.sku, l.quantity_prev, l.quantity_delivered,
                   l.quantity_returned, l.quantity_current, l.sell_through, l.amount,
                   l.payment_method, v.visit_date
            FROM sales.customer_stock_visit_line l
            JOIN sales.customer_stock_visit v ON v.id = l.visit_id
            JOIN master_data.master_customer c ON c.id = v.customer_id
            JOIN master_data.master_product p ON p.id = l.product_id
            ORDER BY v.visit_date DESC, c.code, p.sku LIMIT 12
        """)):
            print(f"  {row[9]} {row[0]:<8} {row[1]:<8} prev {row[2]:>4} + del {row[3]:>4} "
                  f"- ret {row[4]:>3} - cur {row[5]:>4} = sold {row[6]:>4} · "
                  f"EGP {row[7]:>9} · {row[8]}")

        print("\nintegrity")
        for label, statement in INTEGRITY_CHECKS:
            mismatches = connection.execute(text(statement)).scalar_one()
            print(f"  {label:<28} {'OK' if mismatches == 0 else f'{mismatches} MISMATCH'}")

    print(f"\nstate digest: {digest(engine)}")


def main() -> None:
    engine = _connect()
    seed(engine)
    report(engine)
    engine.dispose()


if __name__ == "__main__":
    main()
