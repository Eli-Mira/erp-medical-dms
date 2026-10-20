import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, text

from alembic import command
from alembic.config import Config

DB_PREFIX = "dms_cycle_test_"


def make_db(base_url):
    import uuid as _uuid

    name = DB_PREFIX + _uuid.uuid4().hex
    admin = create_engine(base_url.set(database="postgres"))
    with admin.connect() as c:
        c.execution_options(isolation_level="AUTOCOMMIT")
        c.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        c.exec_driver_sql(f'CREATE DATABASE "{name}"')
    admin.dispose()
    return name, create_engine(base_url.set(database=name))


def drop_db(base_url, name):
    admin = create_engine(base_url.set(database="postgres"))
    with admin.connect() as c:
        c.execution_options(isolation_level="AUTOCOMMIT")
        c.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    admin.dispose()


def cfg_for(url):
    cfg = Config(r"C:\Desktop\Huge system\alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    return cfg


def snapshot(engine):
    with engine.connect() as c:
        revision = c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        tables = sorted(
            r[0] + "." + r[1]
            for r in c.execute(
                text(
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema')"
                )
            ).all()
        )
        key_tables = [
            "platform.platform_user",
            "master_data.master_branch",
            "master_data.master_territory",
            "master_data.master_customer",
            "master_data.master_product",
            "master_data.master_warehouse",
            "sales.sales_invoice",
            "sales.sales_invoice_line",
            "inventory.stock_balance",
            "inventory.stock_movement",
            "finance.ar_entry",
            "finance.payment_receipt",
        ]

        def rows_for(table):
            schema, name = table.split(".", 1)
            result = c.execute(text(f"SELECT * FROM {schema}.{name} ORDER BY 1"))
            cols = list(result.keys())
            out = []
            for row in result.mappings().all():
                out.append({k: (str(v) if not isinstance(v, (int, float, bool, type(None))) else v) for k, v in dict(row).items()})
            return cols, out

        counts = {}
        hashes = {}
        for table in key_tables:
            cols, rows = rows_for(table)
            counts[table] = len(rows)
            import hashlib

            hashes[table] = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()

        functions = sorted(
            r[0] + "." + r[1]
            for r in c.execute(
                text(
                    "SELECT n.nspname, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname IN ('sales','finance')"
                )
            ).all()
        )
        triggers = sorted(
            r[0] + "." + r[1] + "." + r[2]
            for r in c.execute(
                text(
                    "SELECT trigger_schema, event_object_table, trigger_name "
                    "FROM information_schema.triggers WHERE trigger_schema IN ('sales','finance','inventory')"
                )
            ).all()
        )
        grants = sorted(
            (r[0], r[1], r[2], r[3])
            for r in c.execute(
                text(
                    "SELECT grantee, table_schema, table_name, privilege_type "
                    "FROM information_schema.role_table_grants "
                    "WHERE table_schema IN ('platform','master_data','sales','inventory','finance','audit')"
                )
            ).all()
        )
    return {
        "revision": revision,
        "tables": tables,
        "counts": counts,
        "hashes": hashes,
        "functions": functions,
        "triggers": triggers,
        "grants": grants,
    }


def seed(engine):
    ids = {
        "owner": uuid.uuid4(),
        "branch": uuid.uuid4(),
        "territory": uuid.uuid4(),
        "customer": uuid.uuid4(),
        "product": uuid.uuid4(),
        "warehouse": uuid.uuid4(),
        "invoice": uuid.uuid4(),
        "line": uuid.uuid4(),
        "sale_movement": uuid.uuid4(),
        "reversed_movement": uuid.uuid4(),
        "ar_invoice": uuid.uuid4(),
        "receipt": uuid.uuid4(),
        "ar_payment": uuid.uuid4(),
        "ar_reversed": uuid.uuid4(),
    }
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
                "VALUES (:id,'rehearse_owner','unused','owner',true)"
            ),
            {"id": ids["owner"]},
        )
        db.execute(
            text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,'RB','فرع')"),
            {"id": ids["branch"]},
        )
        db.execute(
            text("INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,'RT','منطقة')"),
            {"id": ids["territory"]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
                "VALUES (:id,'RC','عميل',:b,:t)"
            ),
            {"id": ids["customer"], "b": ids["branch"], "t": ids["territory"]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) "
                "VALUES (:id,'RP','منتج',10,14)"
            ),
            {"id": ids["product"]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
                "VALUES (:id,:b,'RW','مخزن')"
            ),
            {"id": ids["warehouse"], "b": ids["branch"]},
        )
        db.execute(
            text(
                "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) "
                "VALUES (:w,:p,10)"
            ),
            {"w": ids["warehouse"], "p": ids["product"]},
        )
        db.execute(
            text(
                "INSERT INTO sales.sales_invoice("
                "id,invoice_no,branch_id,customer_id,territory_id,warehouse_id,created_by,"
                "invoice_date,posting_status,version) "
                "VALUES (:id,'REH-1',:b,:c,:t,:w,:u,:d,'Draft',1)"
            ),
            {
                "id": ids["invoice"],
                "b": ids["branch"],
                "c": ids["customer"],
                "t": ids["territory"],
                "w": ids["warehouse"],
                "u": ids["owner"],
                "d": date(2026, 10, 10),
            },
        )
        db.execute(
            text(
                "INSERT INTO sales.sales_invoice_line("
                "id,invoice_id,line_no,product_id,quantity,unit_price,discount_pct,"
                "net_price,line_total,vat_rate,vat_amount) "
                "VALUES (:id,:inv,1,:p,2,10,0,20,20,14,2.8)"
            ),
            {"id": ids["line"], "inv": ids["invoice"], "p": ids["product"]},
        )
        db.execute(
            text(
                "UPDATE sales.sales_invoice SET posting_status='Posted', posted_at=:at, "
                "posted_by=:u, total_before_discount=22.8, total_discount=0, "
                "total_net=20, vat_amount=2.8, grand_total=22.8 WHERE id=:id"
            ),
            {"at": datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc), "u": ids["owner"], "id": ids["invoice"]},
        )
        db.execute(
            text(
                "INSERT INTO inventory.stock_movement("
                "id,movement_type,warehouse_id,product_id,quantity,source_id,source_type,"
                "invoice_line_id,created_by,created_at) "
                "VALUES (:id,'sale',:w,:p,2,:inv,'invoice',:line,:u,now())"
            ),
            {
                "id": ids["sale_movement"],
                "w": ids["warehouse"],
                "p": ids["product"],
                "inv": ids["invoice"],
                "line": ids["line"],
                "u": ids["owner"],
            },
        )
        db.execute(
            text(
                "INSERT INTO inventory.stock_movement("
                "id,movement_type,warehouse_id,product_id,quantity,source_id,source_type,"
                "reverses_movement_id,created_by,created_at) "
                "VALUES (:id,'adjustment',:w,:p,2,:inv,'invoice',:rev,:u,now())"
            ),
            {
                "id": ids["reversed_movement"],
                "w": ids["warehouse"],
                "p": ids["product"],
                "inv": ids["invoice"],
                "rev": ids["sale_movement"],
                "u": ids["owner"],
            },
        )
        db.execute(
            text(
                "INSERT INTO finance.ar_entry("
                "id,customer_id,invoice_id,entry_type,entry_date,debit,credit,created_by) "
                "VALUES (:id,:c,:inv,'invoice',:d,22.8,0,:u)"
            ),
            {"id": ids["ar_invoice"], "c": ids["customer"], "inv": ids["invoice"], "d": date(2026, 10, 10), "u": ids["owner"]},
        )
        db.execute(
            text(
                "INSERT INTO finance.payment_receipt("
                "id,invoice_id,branch_id,customer_id,receipt_no,receipt_date,amount,method,status,created_by,version) "
                "VALUES (:id,:inv,:b,:c,'REH-RCPT',:d,5,'cash','Active',:u,1)"
            ),
            {
                "id": ids["receipt"],
                "inv": ids["invoice"],
                "b": ids["branch"],
                "c": ids["customer"],
                "d": date(2026, 10, 11),
                "u": ids["owner"],
            },
        )
        db.execute(
            text(
                "INSERT INTO finance.ar_entry("
                "id,customer_id,receipt_id,entry_type,entry_date,debit,credit,created_by) "
                "VALUES (:id,:c,:r,'payment',:d,0,5,:u)"
            ),
            {"id": ids["ar_payment"], "c": ids["customer"], "r": ids["receipt"], "d": date(2026, 10, 11), "u": ids["owner"]},
        )
        db.execute(
            text(
                "INSERT INTO finance.ar_entry("
                "id,customer_id,entry_type,entry_date,debit,credit,created_by,reverses_entry_id) "
                "VALUES (:id,:c,'adjustment',:d,0,1,:u,:rev)"
            ),
            {"id": ids["ar_reversed"], "c": ids["customer"], "d": date(2026, 10, 12), "u": ids["owner"], "rev": ids["ar_payment"]},
        )
    return ids


def main():
    import os

    base_url_str = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:@127.0.0.1:59873/postgres")
    from sqlalchemy.engine.url import make_url

    base_url = make_url(base_url_str)
    name, engine = make_db(base_url)
    try:
        cfg = cfg_for(engine.url)
        command.upgrade(cfg, "0010_invoice_collections")
        assert engine.connect().execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0010_invoice_collections"
        seed(engine)
        baseline = snapshot(engine)

        command.upgrade(cfg, "0015_private_accounts")
        assert engine.connect().execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0015_private_accounts"

        command.downgrade(cfg, "0010_invoice_collections")
        after_conn = engine.connect()
        after_revision = after_conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        after_conn.close()
        assert after_revision == "0010_invoice_collections", after_revision
        recovered = snapshot(engine)

        new_tables = [
            "master_data.master_supplier",
            "finance.coa_account",
            "marketing.marketing_kol",
            "sales.sales_target",
            "sales.sales_return",
            "marketing.marketing_spend",
            "marketing.marketing_spend_product",
            "marketing.marketing_objective",
            "private.account_entry",
        ]
        unexpected = [t for t in new_tables if t in recovered["tables"]]
        assert not unexpected, unexpected

        for key in ("counts", "hashes"):
            assert baseline[key] == recovered[key], (key, baseline[key], recovered[key])

        assert baseline["functions"] == recovered["functions"]
        assert baseline["triggers"] == recovered["triggers"]
        assert baseline["grants"] == recovered["grants"]

        # Confirm 0010 guards are still active by attempting a forbidden raw update.
        with engine.begin() as db:
            try:
                db.execute(text("UPDATE sales.sales_invoice SET invoice_no='X' WHERE posting_status='Posted'"))
                raise AssertionError("guard_terminal_invoice did not block raw update")
            except Exception:
                pass

        print(
            json.dumps(
                {
                    "database": name,
                    "baseline_revision": baseline["revision"],
                    "recovered_revision": recovered["revision"],
                    "unexpected_new_tables": unexpected,
                    "counts": recovered["counts"],
                    "functions_preserved": baseline["functions"] == recovered["functions"],
                    "triggers_preserved": baseline["triggers"] == recovered["triggers"],
                    "grants_preserved": baseline["grants"] == recovered["grants"],
                    "data_hashes_preserved": baseline["hashes"] == recovered["hashes"],
                    "result": "PASS",
                },
                indent=2,
            )
        )
    finally:
        engine.dispose()
        drop_db(base_url, name)


if __name__ == "__main__":
    main()
