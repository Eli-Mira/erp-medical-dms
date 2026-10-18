"""GET /inventory/cover: stock-cover/overstock computed from real ledgers only."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

pytest_plugins = ["test_inventory_api"]


def _seed_posted_sale(db, today, ids, *, product_id, warehouse_id, qty, days_ago, seq=1):
    """Direct Posted-invoice insert (API posting stays disabled); cover reads it."""
    invoice_id = uuid4()
    # Lines may only attach to a Draft; posting is the Draft->Posted update,
    # exactly what post_invoice_atomic does.
    db.execute(
        text("""INSERT INTO sales.sales_invoice
            (id, invoice_no, branch_id, warehouse_id, customer_id, rep_id,
             invoice_date, posting_status, created_by, territory_id,
             total_net, vat_amount, grand_total)
            VALUES (:id, :no, :branch, :wh, :cust, :rep, :date, 'Draft',
                    :owner, :terr, 0, 0, 0)"""),
        {"id": invoice_id, "no": f"CV-{seq}", "branch": ids["branch"],
         "wh": warehouse_id, "cust": ids["cover_customer"],
         "rep": ids["owner"], "date": today - timedelta(days=days_ago),
         "owner": ids["owner"], "terr": ids["territory"]},
    )
    db.execute(
        text("""INSERT INTO sales.sales_invoice_line
            (id, invoice_id, product_id, line_no, quantity, unit_price,
             discount_pct, net_price, line_total, vat_rate, vat_amount)
            VALUES (gen_random_uuid(), :invoice, :product, 1, :qty, 10.00,
                    0, 10.00, :lt, 14.00, 0)"""),
        {"invoice": invoice_id, "product": product_id, "qty": Decimal(qty),
         "lt": Decimal(qty) * Decimal("10.00")},
    )
    db.execute(
        text("""UPDATE sales.sales_invoice SET posting_status='Posted',
            posted_at=now(), posted_by=:owner WHERE id=:id"""),
        {"owner": ids["owner"], "id": invoice_id},
    )


@pytest.fixture
def cover_env(stock_env):
    client, db, ids, headers, movement = stock_env
    ids["territory"] = uuid4()
    ids["cover_customer"] = uuid4()
    db.execute(text(
        "INSERT INTO master_data.master_territory(id,code,name_ar) "
        "VALUES (:id,:code,'Terr')"),
        {"id": ids["territory"], "code": ids["territory"].hex[:20]})
    db.execute(text(
        "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
        "VALUES (:id,:code,'Cust',:branch,:terr)"),
        {"id": ids["cover_customer"], "code": ids["cover_customer"].hex[:20],
         "branch": ids["branch"], "terr": ids["territory"]})
    db.commit()
    return client, db, ids, headers, movement


def test_cover_without_sales_history_is_honest(stock_env):
    client, _db, ids, headers, movement = stock_env
    assert client.post("/inventory/movements", json=movement(),
                       headers=headers("owner")).status_code == 201
    body = client.get(
        f"/inventory/cover?product_id={ids['product']}", headers=headers("owner"))
    assert body.status_code == 200, body.text
    rows = body.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "no_sales_history"
    assert row["sold_in_window"] is None and row["cover_days"] is None
    assert row["window_days"] == 30 and row["threshold_days"] == 180


def test_cover_uses_configured_policy(stock_env):
    client, _db, _ids, headers, movement = stock_env
    client.put("/settings/inventory-policy", headers=headers("owner"),
               json={"stock_cover_window_days": 45, "overstock_threshold_days": 200})
    assert client.post("/inventory/movements", json=movement(),
                       headers=headers("owner")).status_code == 201
    row = client.get("/inventory/cover", headers=headers("owner")).json()[0]
    assert row["window_days"] == 45 and row["threshold_days"] == 200


def test_cover_computes_days_and_status_ok(cover_env):
    client, db, ids, headers, movement = cover_env
    today = datetime.now(UTC).astimezone().date()
    _seed_posted_sale(db, today, ids, product_id=ids["product"],
                      warehouse_id=ids["warehouse"], qty="30", days_ago=10)
    db.commit()
    assert client.post("/inventory/movements", json=movement(),
                       headers=headers("owner")).status_code == 201
    row = client.get("/inventory/cover", headers=headers("owner")).json()[0]
    assert row["status"] == "ok"
    # 10 on hand at 1 unit/day = 10 days of cover.
    assert Decimal(row["cover_days"]) == 10
    assert Decimal(row["sold_in_window"]) == 30


def test_cover_flags_overstock(cover_env):
    client, db, ids, headers, movement = cover_env
    today = datetime.now(UTC).astimezone().date()
    _seed_posted_sale(db, today, ids, product_id=ids["product"],
                      warehouse_id=ids["warehouse"], qty="1", days_ago=5, seq=2)
    db.commit()
    client.post("/inventory/movements", json=movement(quantity="100"),
                headers=headers("owner"))
    row = client.get("/inventory/cover", headers=headers("owner")).json()[0]
    assert row["status"] == "overstock"


def test_cover_unauthenticated_denied(stock_env):
    client, _db, _ids, _headers, _m = stock_env
    assert client.get("/inventory/cover").status_code == 401
