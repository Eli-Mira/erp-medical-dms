"""Warehouse transfers: two linked movements, no sales side-effects."""

from uuid import uuid4

from sqlalchemy import text

pytest_plugins = ["test_invoice_api"]


def test_transfer_moves_stock_between_warehouses(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    ids["dest_warehouse"] = uuid4()
    db.execute(text("INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
                    "VALUES (:id,:b,:c,'Dest wh')"),
               {"id": ids["dest_warehouse"], "b": ids["branch"],
                "c": ids["dest_warehouse"].hex[:20]})
    db.commit()
    assert client.post("/inventory/movements", headers=headers("owner"),
                       json={"warehouse_id": str(ids["warehouse"]),
                             "product_id": str(ids["product"]),
                             "batch_id": str(ids["batch"]),
                             "movement_type": "opening", "quantity": "10"}).status_code == 201
    body = client.post("/transfers", headers=headers("owner"), json={
        "source_warehouse_id": str(ids["warehouse"]),
        "destination_warehouse_id": str(ids["dest_warehouse"]),
        "product_id": str(ids["product"]),
        "batch_id": str(ids["batch"]),
        "quantity": "4", "note": "rebalance",
    })
    assert body.status_code == 201, body.text
    src = client.get(f"/inventory/stock?warehouse_id={ids['warehouse']}",
                     headers=headers("owner")).json()
    dst = client.get(f"/inventory/stock?warehouse_id={ids['dest_warehouse']}",
                     headers=headers("owner")).json()
    assert src[0]["quantity"] == "6.000"
    assert dst[0]["quantity"] == "4.000"
    assert db.execute(text("SELECT count(*) FROM sales.sales_invoice")).scalar_one() == 0


def test_transfer_insufficient_stock(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    ids["dest_warehouse"] = uuid4()
    db.execute(text("INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
                    "VALUES (:id,:b,:c,'Dest wh')"),
               {"id": ids["dest_warehouse"], "b": ids["branch"],
                "c": ids["dest_warehouse"].hex[:20]})
    db.commit()
    body = client.post("/transfers", headers=headers("owner"), json={
        "source_warehouse_id": str(ids["warehouse"]),
        "destination_warehouse_id": str(ids["dest_warehouse"]),
        "product_id": str(ids["product"]),
        "quantity": "1",
    })
    assert body.status_code == 409


def test_transfer_same_warehouse_rejected(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    body = client.post("/transfers", headers=headers("owner"), json={
        "source_warehouse_id": str(ids["warehouse"]),
        "destination_warehouse_id": str(ids["warehouse"]),
        "product_id": str(ids["product"]),
        "quantity": "1",
    })
    assert body.status_code == 422


def test_transfer_unauthenticated(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    assert client.post("/transfers", json={}).status_code == 401
