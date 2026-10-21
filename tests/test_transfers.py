"""Warehouse transfers: two linked movements, no sales side-effects."""

from datetime import date, timedelta

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app

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


@pytest.mark.parametrize("quantity", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_transfer_rejects_nonfinite_quantity_without_writes(invoice_env, quantity):
    _client, db, ids, _payload, headers = invoice_env
    destination = uuid4()
    db.execute(text(
        "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
        "VALUES (:id,:b,:c,'Finite guard destination')"
    ), {"id": destination, "b": ids["branch"], "c": destination.hex[:20]})
    db.commit()
    auth = headers("owner")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/transfers", headers=auth, json={
            "source_warehouse_id": str(ids["warehouse"]),
            "destination_warehouse_id": str(destination),
            "product_id": str(ids["product"]),
            "quantity": quantity,
        })
    assert response.status_code == 422, response.text
    for table in ("inventory.stock_movement", "inventory.stock_balance"):
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    assert db.execute(text(
        "SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_transfer'"
    )).scalar_one() == 0


def test_transfer_rejects_destination_batch_with_conflicting_dates(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    ids["dest_warehouse"] = uuid4()
    db.execute(text(
        "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
        "VALUES (:id,:b,:c,'Dest wh')"
    ), {"id": ids["dest_warehouse"], "b": ids["branch"],
        "c": ids["dest_warehouse"].hex[:20]})
    db.commit()
    # Destination batch: same product and batch_no as source, but different
    # manufacture_date and expiry_date.
    ids["dest_batch"] = uuid4()
    db.execute(text(
        "INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,"
        "manufacture_date,expiry_date) VALUES (:id,:p,:w,:bn,:md,:ed)"
    ), {"id": ids["dest_batch"], "p": ids["product"],
        "w": ids["dest_warehouse"], "bn": "TEST",
        "md": date.today() - timedelta(days=30),
        "ed": date.today() + timedelta(days=100)})
    db.commit()
    auth = headers("owner")
    response = client.post("/transfers", headers=auth, json={
        "source_warehouse_id": str(ids["warehouse"]),
        "destination_warehouse_id": str(ids["dest_warehouse"]),
        "product_id": str(ids["product"]),
        "batch_id": str(ids["batch"]),
        "quantity": "4", "note": "metadata conflict",
    })
    assert response.status_code == 422, response.text
    # No writes: no movement, balance, audit entry, and destination batch
    # unchanged (never overwritten).
    assert db.execute(text("SELECT count(*) FROM inventory.stock_movement")).scalar_one() == 0
    assert db.execute(text("SELECT count(*) FROM inventory.stock_balance")).scalar_one() == 0
    assert db.execute(text(
        "SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_transfer'"
    )).scalar_one() == 0
    persisted = db.execute(text(
        "SELECT manufacture_date, expiry_date FROM inventory.batch_record "
        "WHERE id=:id"
    ), {"id": ids["dest_batch"]}).mappings().one()
    assert persisted["manufacture_date"] == date.today() - timedelta(days=30)
    assert persisted["expiry_date"] == date.today() + timedelta(days=100)
