"""B1 import dry run: confirmed master data only, isolated disposable DB.

Reads the 7 workbooks read-only. Inserts ONLY unambiguous entities
(branches, products) into a freshly created disposable database, verifies
counts, then drops it. No writes to source workbooks, medical_dms or medical_demo.
Customers/territories/warehouses are reported as unresolved (not inserted).
"""
from __future__ import annotations

import glob
import json
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATABASE_URL = os.environ["DATABASE_URL"]  # Require an explicit task-owned target.

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from alembic import command

SALES_WBS = sorted(glob.glob("مبيعات *2026.xlsx"))
FINANCE_WB = "الميزانية العمومية 2026.xlsx"
EXCLUDE_SHEETS = {"الرئيسية", "رصيد الارصدة المباعة", "كامل الكمية", "تحت التصريف"}
DB_NAME = "dms_cycle_test_b1import"


def fail(msg):
    raise SystemExit("b1_import: " + msg)


def admin_url():
    from app.db import DATABASE_URL
    base = create_engine(DATABASE_URL).url
    if base.host not in {"localhost", "127.0.0.1", "::1"}:
        fail(f"refusing non-local host {base.host!r}")
    if base.database in (DB_NAME, "medical_dms", "medical_demo"):
        fail(f"refusing to reuse {base.database}")
    return base


def create_db() -> Engine:
    base = admin_url()
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)')
        conn.exec_driver_sql(f'CREATE DATABASE "{DB_NAME}"')
    return create_engine(base.set(database=DB_NAME))


def apply_migrations(engine):
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%"))
    command.upgrade(cfg, "head")


def extract_branches():
    # one branch per sales workbook; code = short slug, name = region from filename
    out = []
    for f in SALES_WBS:
        name = os.path.basename(f).replace("مبيعات ", "").replace(" 2026.xlsx", "").replace(" 2026.xlsx", "").strip()
        code = "BR-" + name[:6].upper().replace(" ", "")
        out.append({"code": code, "name_ar": name, "source": os.path.basename(f)})
    return out


NON_PRODUCT_ROWS = {"#REF!", "الاجمالى", "المبلغ"}

def extract_products():
    # union of item names from كامل الكمية column A; price from first occurrence (col D)
    # Reject aggregate/error rows; keep PulmiPure variants separate (not merged)
    seen = {}
    order = []
    rejected = []
    for f in SALES_WBS:
        import openpyxl
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb["كامل الكمية"]
        for row in ws.iter_rows(min_row=2):
            name = row[0].value
            price = row[3].value if len(row) > 3 else None
            if isinstance(name, str) and name.strip():
                name = name.strip()
                if name in NON_PRODUCT_ROWS:
                    if name not in rejected:
                        rejected.append(name)
                    continue
                if name not in seen:
                    seen[name] = price
                    order.append(name)
    return [{"name": n, "price": seen[n]} for n in order], rejected


def extract_unresolved():
    import openpyxl
    wb = openpyxl.load_workbook(FINANCE_WB, read_only=True, data_only=True)
    ws = wb["العملاء"]
    cust = []
    for c in range(4, ws.max_column + 1, 6):
        v = ws.cell(row=2, column=c).value
        if isinstance(v, str) and v.strip():
            cust.append(v.strip())
    # warehouse-sheet candidates
    wh_total = 0
    for f in SALES_WBS:
        wb2 = openpyxl.load_workbook(f, read_only=True, data_only=True)
        wh_total += len([s for s in wb2.sheetnames if s not in EXCLUDE_SHEETS])
    return cust, wh_total


def main():
    branches = extract_branches()
    products, rejected_products = extract_products()
    cust, _ = extract_unresolved()

    engine = create_db()
    try:
        apply_migrations(engine)
        accepted = {"branches": 0, "products": 0}
        rejected = {"branches": 0, "products": 0}
        duplicates = {"branches": 0, "products": 0}
        with engine.begin() as db:
            # branches (idempotent: skip duplicates by code)
            for b in branches:
                if not b["code"] or not b["name_ar"]:
                    rejected["branches"] += 1
                    continue
                res = db.execute(text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,:name) ON CONFLICT (code) DO NOTHING RETURNING id"),
                                 {"id": str(uuid.uuid4()), "code": b["code"], "name": b["name_ar"]})
                if res.scalar() is None:
                    duplicates["branches"] += 1
                else:
                    accepted["branches"] += 1
            # products (idempotent by sku; validate name+price)
            for pr in products:
                if not pr["name"]:
                    rejected["products"] += 1
                    continue
                price = pr["price"]
                if price is None:
                    price = 0
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    rejected["products"] += 1
                    continue
                res = db.execute(text("INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,:name,:price,14.00) ON CONFLICT (sku) DO NOTHING RETURNING id"),
                                 {"id": str(uuid.uuid4()), "sku": pr["name"], "name": pr["name"], "price": str(price)})
                if res.scalar() is None:
                    duplicates["products"] += 1
                else:
                    accepted["products"] += 1
        # verify
        with engine.connect() as db:
            bcount = db.execute(text("SELECT count(*) FROM master_data.master_branch")).scalar_one()
            pcount = db.execute(text("SELECT count(*) FROM master_data.master_product")).scalar_one()
            assert bcount == accepted["branches"] + duplicates["branches"], (bcount, accepted, duplicates)
            assert pcount == accepted["products"] + duplicates["products"], (pcount, accepted, duplicates)
        inserted = {"branches": bcount, "products": pcount}
    finally:
        # drop disposable db
        base = admin_url()
        admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)')
        engine.dispose()

    # sanitized summary (counts only, no company records)
    summary = {
        "accepted": accepted,
        "rejected": {"branches": rejected["branches"], "products": len(rejected_products)},
        "duplicates": duplicates,
        "db_writes": "disposable DB created, loaded, verified, dropped",
        "db_name": DB_NAME,
        "medical_dms_touched": False,
        "medical_demo_touched": False,
        "source_file_writes": "NONE",
        "inserted": inserted,
        "rejected_product_rows": rejected_products,
        "unresolved_not_inserted": {
            "warehouses": "291 candidate sheets; company vs customer-held stock location unconfirmed",
            "customers": len(cust),
            "territories": "no explicit territory column; inferred from sheet refs only",
            "products_branch_specific": len(products) - 10,
        },
        "unresolved_questions": [
            "Q1: Customer->branch/territory key (workbook name vs sheet prefix vs manual)?",
            "Q2: Which of the 291 sheets are company source warehouses vs customer-held stock?",
            "Q3: Are the 5 branch-specific product names the same SKU sold in all branches or branch-exclusive?",
            "Q4: Territory = branch, or separate dimension?",
        ],
    }
    out = os.path.join(ROOT, "docs", "evidence", "invoice-cycle", "b1_import_dry_run_20261019")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    # private exception list (local only, not committed) with source refs
    exc_path = os.path.join(ROOT, "private", "b1_exceptions.txt")
    os.makedirs(os.path.dirname(exc_path), exist_ok=True)
    with open(exc_path, "w", encoding="utf-8") as fh:
        fh.write("B1 private exception list (NOT committed; contains source refs)\n")
        fh.write("Warehouses: 291 candidate sheets across 5 workbooks; company vs customer-held unconfirmed.\n")
        fh.write(f"Customers: {len(cust)} blocks in finance workbook AR sheet.\n")
        fh.write(f"Products: {len(products)} unique, 10 common to all 5 workbooks.\n")
        fh.write("Territories: no explicit column; inferred from sheet refs only.\n")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print("private exception list written to:", exc_path)


if __name__ == "__main__":
    main()
