from datetime import date
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from test_invoice_api import invoice_env  # noqa: F401
from app.telegram.queries import TEMPLATES

def test_all_6_telegram_templates_execute_as_readonly_telegram_reader_on_real_postgres(invoice_env):
    client, db, ids, payload, headers = invoice_env

    # seed data via API
    assert client.post(
        "/inventory/movements",
        headers=headers("owner"),
        json={
            "warehouse_id": str(ids["warehouse"]),
            "product_id": str(ids["product"]),
            "batch_id": str(ids["batch"]),
            "movement_type": "opening",
            "quantity": "20",
        },
    ).status_code == 201

    assert client.post(
        "/ar/entries",
        headers=headers("owner"),
        json={
            "customer_id": str(ids["customer"]),
            "entry_type": "opening",
            "entry_date": date.today().isoformat(),
            "debit": "150.00",
            "credit": "0",
        },
    ).status_code == 201

    inv_r = client.post("/invoices", headers=headers("owner"), json=payload)
    assert inv_r.status_code == 201
    inv_id = inv_r.json()["id"]
    db.execute(
        text(
            "UPDATE sales.sales_invoice SET posting_status='Posted', posted_at=now(), posted_by=:u WHERE id=:id"
        ),
        {"u": ids["owner"], "id": inv_id},
    )
    db.commit()

    tgt_r = client.post(
        "/targets",
        headers=headers("owner"),
        json={
            "territory_id": str(ids["territory"]),
            "period_month": date.today().replace(day=1).isoformat(),
            "target_quantity": "20",
        },
    )
    assert tgt_r.status_code == 201
    target_id = tgt_r.json()["id"]

    # create/reset least‑privilege role
    db.execute(
        text(
            """
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telegram_reader') THEN
                    CREATE ROLE telegram_reader NOLOGIN;
                END IF;
            END $$;
            """
        )
    )
    db.execute(
        text(
            "REVOKE ALL ON ALL TABLES IN SCHEMA public, platform, audit, master_data, inventory, sales, finance FROM telegram_reader"
        )
    )
    db.execute(text("REVOKE ALL ON SCHEMA platform, audit FROM telegram_reader"))
    db.execute(
        text(
            "GRANT USAGE ON SCHEMA master_data, inventory, sales, finance TO telegram_reader"
        )
    )
    db.execute(
        text(
            """
            GRANT SELECT ON
                master_data.master_customer,
                master_data.master_product,
                inventory.stock_balance,
                inventory.batch_record,
                sales.sales_invoice,
                sales.sales_invoice_line,
                sales.sales_target,
                finance.ar_entry
            TO telegram_reader
            """
        )
    )
    db.commit()

    # switch role and run templates
    db.execute(text("SET LOCAL ROLE telegram_reader"))

    # balance
    rows = db.execute(
        text(TEMPLATES["balance"]["sql"]), {"customer_id": ids["customer"]}
    ).fetchall()
    out = TEMPLATES["balance"]["format"](rows)
    assert "150.00 EGP" in out

    # stock
    rows = db.execute(
        text(TEMPLATES["stock"]["sql"]), {"product_id": ids["product"]}
    ).fetchall()
    out = TEMPLATES["stock"]["format"](rows)
    assert "20.000 units" in out

    # sales_today
    rows = db.execute(text(TEMPLATES["sales_today"]["sql"])).fetchall()
    out = TEMPLATES["sales_today"]["format"](rows)
    assert "228.00 EGP" in out
    assert "Invoices: 1" in out

    # expiry
    rows = db.execute(
        text(TEMPLATES["expiry"]["sql"]), {"days": 400}
    ).fetchall()
    out = TEMPLATES["expiry"]["format"](rows)
    assert "TEST" in out
    assert "20.000 units" in out

    # targets
    rows = db.execute(
        text(TEMPLATES["targets"]["sql"]), {"target_id": target_id}
    ).fetchall()
    out = TEMPLATES["targets"]["format"](rows)
    assert "20.000 units" in out
    assert "2.000 units" in out

    # stock_cover
    rows = db.execute(
        text(TEMPLATES["stock_cover"]["sql"]), {"product_id": ids["product"]}
    ).fetchall()
    out = TEMPLATES["stock_cover"]["format"](rows)
    assert "20.000 units" in out
    assert "Cover:" in out

    # negative privilege checks
    with pytest.raises(ProgrammingError):
        with db.begin_nested():
            db.execute(text("SELECT id FROM platform.platform_user LIMIT 1"))

    with pytest.raises(ProgrammingError):
        with db.begin_nested():
            db.execute(text("SELECT id FROM finance.private_account LIMIT 1"))

    with pytest.raises(ProgrammingError):
        with db.begin_nested():
            db.execute(text("DELETE FROM finance.ar_entry WHERE id IS NOT NULL"))

    db.rollback()
