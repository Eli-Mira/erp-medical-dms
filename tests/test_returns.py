"""Sales returns: explicit return transaction + stock increase."""

pytest_plugins = ["test_invoice_api"]


def test_return_increases_warehouse_stock(invoice_env):
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
    assert stock[0]["quantity"] == "13.000"
    rows = client.get("/returns", headers=headers("owner")).json()
    assert len(rows) == 1 and rows[0]["reason"] == "damaged"


def test_return_missing_fields(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    assert client.post("/returns", headers=headers("owner"), json={}).status_code == 422


def test_return_unauthenticated(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    assert client.post("/returns", json={}).status_code == 401
