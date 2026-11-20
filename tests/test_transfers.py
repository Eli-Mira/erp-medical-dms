"""Warehouse transfers: two linked movements, no sales side-effects."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_beta_returns_api import other_warehouse, set_role

from app.main import app

pytest_plugins = ["test_invoice_api"]


def test_transfer_moves_stock_between_warehouses(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    ids["dest_warehouse"] = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:id,:b,:c,'Dest wh')"
        ),
        {
            "id": ids["dest_warehouse"],
            "b": ids["branch"],
            "c": ids["dest_warehouse"].hex[:20],
        },
    )
    db.commit()
    assert (
        client.post(
            "/inventory/movements",
            headers=headers("owner"),
            json={
                "warehouse_id": str(ids["warehouse"]),
                "product_id": str(ids["product"]),
                "batch_id": str(ids["batch"]),
                "movement_type": "opening",
                "quantity": "10",
            },
        ).status_code
        == 201
    )
    body = client.post(
        "/transfers",
        headers=headers("owner"),
        json={
            "source_warehouse_id": str(ids["warehouse"]),
            "destination_warehouse_id": str(ids["dest_warehouse"]),
            "product_id": str(ids["product"]),
            "batch_id": str(ids["batch"]),
            "quantity": "4",
            "note": "rebalance",
        },
    )
    assert body.status_code == 201, body.text
    src = client.get(
        f"/inventory/stock?warehouse_id={ids['warehouse']}", headers=headers("owner")
    ).json()
    dst = client.get(
        f"/inventory/stock?warehouse_id={ids['dest_warehouse']}",
        headers=headers("owner"),
    ).json()
    assert src[0]["quantity"] == "6.000"
    assert dst[0]["quantity"] == "4.000"
    assert (
        db.execute(text("SELECT count(*) FROM sales.sales_invoice")).scalar_one() == 0
    )


def test_transfer_insufficient_stock(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    ids["dest_warehouse"] = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:id,:b,:c,'Dest wh')"
        ),
        {
            "id": ids["dest_warehouse"],
            "b": ids["branch"],
            "c": ids["dest_warehouse"].hex[:20],
        },
    )
    db.commit()
    body = client.post(
        "/transfers",
        headers=headers("owner"),
        json={
            "source_warehouse_id": str(ids["warehouse"]),
            "destination_warehouse_id": str(ids["dest_warehouse"]),
            "product_id": str(ids["product"]),
            "quantity": "1",
        },
    )
    assert body.status_code == 409


def test_transfer_same_warehouse_rejected(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    body = client.post(
        "/transfers",
        headers=headers("owner"),
        json={
            "source_warehouse_id": str(ids["warehouse"]),
            "destination_warehouse_id": str(ids["warehouse"]),
            "product_id": str(ids["product"]),
            "quantity": "1",
        },
    )
    assert body.status_code == 422


def test_transfer_unauthenticated(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    assert client.post("/transfers", json={}).status_code == 401


@pytest.mark.parametrize("quantity", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_transfer_rejects_nonfinite_quantity_without_writes(invoice_env, quantity):
    _client, db, ids, _payload, headers = invoice_env
    destination = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:id,:b,:c,'Finite guard destination')"
        ),
        {"id": destination, "b": ids["branch"], "c": destination.hex[:20]},
    )
    db.commit()
    auth = headers("owner")
    before_audit = db.execute(
        text("SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_transfer'")
    ).scalar_one()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/transfers",
            headers=auth,
            json={
                "source_warehouse_id": str(ids["warehouse"]),
                "destination_warehouse_id": str(destination),
                "product_id": str(ids["product"]),
                "quantity": quantity,
            },
        )
    assert response.status_code == 422, response.text
    for table in ("inventory.stock_movement", "inventory.stock_balance"):
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_transfer'"
            )
        ).scalar_one()
        == before_audit
    )


def test_transfer_rejects_destination_batch_with_conflicting_dates(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    ids["dest_warehouse"] = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:id,:b,:c,'Dest wh')"
        ),
        {
            "id": ids["dest_warehouse"],
            "b": ids["branch"],
            "c": ids["dest_warehouse"].hex[:20],
        },
    )
    db.commit()
    # Destination batch: same product and batch_no as source, but different
    # manufacture_date and expiry_date.
    ids["dest_batch"] = uuid4()
    db.execute(
        text(
            "INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,"
            "manufacture_date,expiry_date) VALUES (:id,:p,:w,:bn,:md,:ed)"
        ),
        {
            "id": ids["dest_batch"],
            "p": ids["product"],
            "w": ids["dest_warehouse"],
            "bn": "TEST",
            "md": datetime.now(UTC).date() - timedelta(days=30),
            "ed": datetime.now(UTC).date() + timedelta(days=100),
        },
    )
    db.commit()
    auth = headers("owner")
    before_audit = db.execute(
        text("SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_transfer'")
    ).scalar_one()
    response = client.post(
        "/transfers",
        headers=auth,
        json={
            "source_warehouse_id": str(ids["warehouse"]),
            "destination_warehouse_id": str(ids["dest_warehouse"]),
            "product_id": str(ids["product"]),
            "batch_id": str(ids["batch"]),
            "quantity": "4",
            "note": "metadata conflict",
        },
    )
    assert response.status_code == 422, response.text
    # No writes: no movement, balance, audit entry, and destination batch
    # unchanged (never overwritten).
    assert (
        db.execute(text("SELECT count(*) FROM inventory.stock_movement")).scalar_one()
        == 0
    )
    assert (
        db.execute(text("SELECT count(*) FROM inventory.stock_balance")).scalar_one()
        == 0
    )
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_transfer'"
            )
        ).scalar_one()
        == before_audit
    )
    persisted = (
        db.execute(
            text(
                "SELECT manufacture_date, expiry_date FROM inventory.batch_record "
                "WHERE id=:id"
            ),
            {"id": ids["dest_batch"]},
        )
        .mappings()
        .one()
    )
    assert persisted["manufacture_date"] == datetime.now(UTC).date() - timedelta(
        days=30
    )
    assert persisted["expiry_date"] == datetime.now(UTC).date() + timedelta(days=100)


@pytest.mark.parametrize("manufacture_date", [None, date(2026, 1, 1)])
def test_transfer_reuses_matching_destination_batch(invoice_env, manufacture_date):
    client, db, ids, _payload, headers = invoice_env
    destination, destination_batch = uuid4(), uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:id,:b,:c,'Matching batch destination')"
        ),
        {"id": destination, "b": ids["branch"], "c": destination.hex[:20]},
    )
    db.execute(
        text("UPDATE inventory.batch_record SET manufacture_date=:md WHERE id=:id"),
        {"md": manufacture_date, "id": ids["batch"]},
    )
    db.execute(
        text(
            "INSERT INTO inventory.batch_record "
            "(id,product_id,warehouse_id,batch_no,manufacture_date,expiry_date) "
            "SELECT :id,product_id,:w,batch_no,manufacture_date,expiry_date "
            "FROM inventory.batch_record WHERE id=:source"
        ),
        {"id": destination_batch, "w": destination, "source": ids["batch"]},
    )
    db.commit()
    auth = headers("owner")
    opening = client.post(
        "/inventory/movements",
        headers=auth,
        json={
            "warehouse_id": str(ids["warehouse"]),
            "product_id": str(ids["product"]),
            "batch_id": str(ids["batch"]),
            "movement_type": "opening",
            "quantity": "10",
        },
    )
    assert opening.status_code == 201, opening.text
    response = client.post(
        "/transfers",
        headers=auth,
        json={
            "source_warehouse_id": str(ids["warehouse"]),
            "destination_warehouse_id": str(destination),
            "product_id": str(ids["product"]),
            "batch_id": str(ids["batch"]),
            "quantity": "4",
        },
    )
    assert response.status_code == 201, response.text
    batches = db.execute(
        text(
            "SELECT id, manufacture_date FROM inventory.batch_record "
            "WHERE warehouse_id=:w AND product_id=:p"
        ),
        {"w": destination, "p": ids["product"]},
    ).all()
    assert batches == [(destination_batch, manufacture_date)]
    movements = db.execute(
        text(
            "SELECT movement_type, batch_id, quantity FROM inventory.stock_movement "
            "WHERE source_type='transfer' AND source_id=:id"
        ),
        {"id": response.json()["id"]},
    ).all()
    assert set(movements) == {
        ("transfer_out", ids["batch"], -4),
        ("transfer_in", destination_batch, 4),
    }
    balances = db.execute(
        text(
            "SELECT warehouse_id, batch_id, quantity FROM inventory.stock_balance "
            "WHERE product_id=:p"
        ),
        {"p": ids["product"]},
    ).all()
    assert set(balances) == {
        (ids["warehouse"], ids["batch"], 6),
        (destination, destination_batch, 4),
    }
    for table in ("sales.sales_invoice", "finance.ar_entry"):
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0


@pytest.mark.parametrize("unassigned_end", ["source", "destination"])
def test_staff_transfer_requires_both_ends_assigned(invoice_env, unassigned_end):
    client, db, ids, _payload, headers = invoice_env
    foreign = other_warehouse(db)
    owner = headers("owner")
    for warehouse in (ids["warehouse"], foreign):
        opened = client.post(
            "/inventory/movements",
            headers=owner,
            json={
                "warehouse_id": str(warehouse),
                "product_id": str(ids["product"]),
                "movement_type": "opening",
                "quantity": "10",
            },
        )
        assert opened.status_code == 201, opened.text
    set_role(db, ids, "warehouse_staff")
    auth = headers("other")
    before = db.execute(
        text(
            "SELECT warehouse_id,product_id,batch_id,quantity "
            "FROM inventory.stock_balance ORDER BY warehouse_id,product_id,batch_id"
        )
    ).all()
    movements = db.scalar(text("SELECT count(*) FROM inventory.stock_movement"))
    audits = db.scalar(text("SELECT count(*) FROM audit.audit_log"))
    response = client.post(
        "/transfers",
        headers=auth,
        json={
            "source_warehouse_id": str(
                foreign if unassigned_end == "source" else ids["warehouse"]
            ),
            "destination_warehouse_id": str(
                foreign if unassigned_end == "destination" else ids["warehouse"]
            ),
            "product_id": str(ids["product"]),
            "quantity": "1",
        },
    )
    assert response.status_code == 403, response.text
    assert (
        db.execute(
            text(
                "SELECT warehouse_id,product_id,batch_id,quantity "
                "FROM inventory.stock_balance ORDER BY warehouse_id,product_id,batch_id"
            )
        ).all()
        == before
    )
    assert db.scalar(text("SELECT count(*) FROM inventory.stock_movement")) == movements
    assert db.scalar(text("SELECT count(*) FROM audit.audit_log")) == audits


def test_staff_transfer_between_assigned_warehouses_succeeds(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    destination = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:id,:branch,:code,'Assigned synthetic destination')"
        ),
        {"id": destination, "branch": ids["branch"], "code": destination.hex[:20]},
    )
    db.commit()
    opened = client.post(
        "/inventory/movements",
        headers=headers("owner"),
        json={
            "warehouse_id": str(ids["warehouse"]),
            "product_id": str(ids["product"]),
            "movement_type": "opening",
            "quantity": "10",
        },
    )
    assert opened.status_code == 201, opened.text
    set_role(db, ids, "warehouse_staff")
    response = client.post(
        "/transfers",
        headers=headers("other"),
        json={
            "source_warehouse_id": str(ids["warehouse"]),
            "destination_warehouse_id": str(destination),
            "product_id": str(ids["product"]),
            "quantity": "1",
        },
    )
    assert response.status_code == 201, response.text
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM inventory.stock_movement WHERE source_type='transfer' "
                "AND source_id=:id"
            ),
            {"id": response.json()["id"]},
        )
        == 2
    )
    assert db.scalar(text("SELECT count(*) FROM finance.ar_entry")) == 0


def test_staff_transfer_history_requires_both_ends_assigned(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    destination = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:id,:branch,:code,'Assigned history destination')"
        ),
        {"id": destination, "branch": ids["branch"], "code": destination.hex[:20]},
    )
    db.commit()
    foreign = other_warehouse(db)
    owner = headers("owner")
    for warehouse in (ids["warehouse"], foreign):
        opened = client.post(
            "/inventory/movements",
            headers=owner,
            json={
                "warehouse_id": str(warehouse),
                "product_id": str(ids["product"]),
                "movement_type": "opening",
                "quantity": "10",
            },
        )
        assert opened.status_code == 201, opened.text
    for source, target, note in (
        (ids["warehouse"], destination, "visible-assigned"),
        (ids["warehouse"], foreign, "hidden-destination"),
        (foreign, ids["warehouse"], "hidden-source"),
    ):
        created = client.post(
            "/transfers",
            headers=owner,
            json={
                "source_warehouse_id": str(source),
                "destination_warehouse_id": str(target),
                "product_id": str(ids["product"]),
                "quantity": "1",
                "note": note,
            },
        )
        assert created.status_code == 201, created.text
    set_role(db, ids, "warehouse_staff")
    listed = client.get("/transfers", headers=headers("other"))
    assert listed.status_code == 200, listed.text
    assert {row["note"] for row in listed.json()} == {"visible-assigned"}
