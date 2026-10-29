"""Physical return intake stays quarantined, not saleable or financially posted."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app

pytest_plugins = ["test_invoice_api"]


def test_return_stays_quarantined_without_increasing_saleable_stock(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    assert client.post("/inventory/movements", headers=headers("owner"),
                       json={"warehouse_id": str(ids["warehouse"]),
                             "product_id": str(ids["product"]),
                             "batch_id": str(ids["batch"]),
                             "movement_type": "opening", "quantity": "10"}).status_code == 201
    body = client.post("/returns", headers=headers("owner"), json={
        "customer_id": str(ids["customer"]),
        "product_id": str(ids["product"]),
        "warehouse_id": str(ids["warehouse"]),
        "batch_id": str(ids["batch"]),
        "quantity": "3",
        "return_date": "2026-10-01",
        "reason": "damaged",
    })
    assert body.status_code == 201, body.text
    stock = client.get(f"/inventory/stock?warehouse_id={ids['warehouse']}",
                       headers=headers("owner")).json()
    assert stock[0]["quantity"] == "10.000"
    rows = client.get("/returns", headers=headers("owner")).json()
    assert len(rows) == 1 and rows[0]["reason"] == "damaged"
    assert rows[0]["status"] == "quarantined"


def test_return_missing_fields(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    assert client.post("/returns", headers=headers("owner"), json={}).status_code == 422


def test_return_unauthenticated(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    assert client.post("/returns", json={}).status_code == 401


@pytest.mark.parametrize("quantity", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_return_rejects_nonfinite_quantity_without_writes(invoice_env, quantity):
    _client, db, ids, _payload, headers = invoice_env
    auth = headers("owner")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/returns", headers=auth, json={
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "quantity": quantity,
            "return_date": "2026-10-01",
        })
    assert response.status_code == 422, response.text
    for table in ("sales.sales_return", "inventory.stock_movement", "inventory.stock_balance"):
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    assert db.execute(text(
        "SELECT count(*) FROM audit.audit_log WHERE entity_type='sales_return'"
    )).scalar_one() == 0
