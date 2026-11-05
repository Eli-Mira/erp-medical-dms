"""Quarantine-return authority must not grant inventory read/write authority."""

import pytest
from sqlalchemy import text
from test_beta_returns_api import body, other_warehouse, set_role
from test_beta_returns_api import owned_database as owned_database  # noqa: PLC0414

pytest_plugins = ["test_invoice_api"]


def test_returns_without_branch_grants_do_not_grant_stock_access(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    foreign = other_warehouse(db)
    recorded = client.post(
        "/returns", headers=headers(), json=body(ids, warehouse_id=str(foreign))
    )
    assert recorded.status_code == 201, recorded.text
    set_role(db, ids, "warehouse_staff")
    db.execute(
        text("DELETE FROM platform.user_branch WHERE user_id=:u"), {"u": ids["other"]}
    )
    db.execute(
        text("DELETE FROM platform.user_territory WHERE user_id=:u"),
        {"u": ids["other"]},
    )
    db.commit()
    auth = headers("other")
    before = db.execute(
        text("SELECT warehouse_id,product_id,quantity FROM inventory.stock_balance")
    ).all()
    movements = db.scalar(text("SELECT count(*) FROM inventory.stock_movement"))
    listed = client.get("/returns", headers=auth)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()} == {recorded.json()["id"]}
    intake = client.post("/returns", headers=auth, json=body(ids))
    assert intake.status_code == 201, intake.text
    assert intake.json()["status"] == "quarantined"
    for view in ("stock", "batches", "movements", "cover", "expiry-warnings"):
        assert client.get("/inventory/" + view, headers=auth).status_code == 403
    for kind in ("opening", "adjustment"):
        denied = client.post(
            "/inventory/movements",
            headers=auth,
            json={
                "warehouse_id": str(ids["warehouse"]),
                "product_id": str(ids["product"]),
                "movement_type": kind,
                "quantity": "1",
                "reason_id": str(ids["reason"]),
            },
        )
        assert denied.status_code == 403, denied.text
    assert db.scalar(text("SELECT count(*) FROM inventory.stock_movement")) == movements
    assert (
        db.execute(
            text("SELECT warehouse_id,product_id,quantity FROM inventory.stock_balance")
        ).all()
        == before
    )


def test_global_returns_preserve_assigned_stock_and_foreign_stock_denial(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    foreign = other_warehouse(db)
    owner = headers()
    opening = client.post(
        "/inventory/movements",
        headers=owner,
        json={
            "warehouse_id": str(ids["warehouse"]),
            "product_id": str(ids["product"]),
            "movement_type": "opening",
            "quantity": "4",
        },
    )
    assert opening.status_code == 201, opening.text
    recorded = client.post(
        "/returns", headers=owner, json=body(ids, warehouse_id=str(foreign))
    )
    assert recorded.status_code == 201, recorded.text
    set_role(db, ids, "warehouse_staff")
    auth = headers("other")
    own = client.get("/inventory/stock", headers=auth)
    assert own.status_code == 200, own.text
    assert [(r["warehouse_id"], r["quantity"]) for r in own.json()] == [
        (str(ids["warehouse"]), "4.000")
    ]
    denied = client.get(
        "/inventory/stock", headers=auth, params={"warehouse_id": str(foreign)}
    )
    assert denied.status_code == 404, denied.text
    listed = client.get("/returns", headers=auth)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()} == {recorded.json()["id"]}


@pytest.mark.parametrize("role", ["admin", "medical_rep"])
def test_unapproved_roles_cannot_read_or_intake_returns(invoice_env, role):
    client, db, ids, _payload, headers = invoice_env
    recorded = client.post("/returns", headers=headers(), json=body(ids))
    assert recorded.status_code == 201, recorded.text
    set_role(db, ids, role)
    auth = headers("other")
    before = db.scalar(text("SELECT count(*) FROM sales.sales_return"))
    assert client.get("/returns", headers=auth).status_code == 403
    denied = client.post("/returns", headers=auth, json=body(ids))
    assert denied.status_code == 403, denied.text
    assert db.scalar(text("SELECT count(*) FROM sales.sales_return")) == before
