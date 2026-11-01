"""Returns intake: validate before SQL and preserve scoped, exact quarantine reads."""

import os
import re
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app

pytest_plugins = ["test_invoice_api"]


@pytest.fixture(autouse=True)
def owned_database():
    assert os.environ.get("APP_ENV") == "test"
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", engine.url.database)
    with engine.connect() as db:
        assert (
            db.execute(text("SELECT current_database()")).scalar_one()
            == engine.url.database
        )


def body(ids, **changes):
    result = {
        "customer_id": str(ids["customer"]),
        "product_id": str(ids["product"]),
        "warehouse_id": str(ids["warehouse"]),
        "batch_id": None,
        "quantity": "1.125",
        "return_date": "2026-10-15",
        "reason": None,
    }
    return {**result, **changes}


def set_role(db, ids, role):
    db.execute(
        text("UPDATE platform.platform_user SET role=:role WHERE id=:id"),
        {"role": role, "id": ids["other"]},
    )
    db.commit()


def other_warehouse(db):
    branch, warehouse = uuid4(), uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:i,:c,'Synthetic B')"
        ),
        {"i": branch, "c": branch.hex[:20]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:i,:b,:c,'Synthetic B')"
        ),
        {"i": warehouse, "b": branch, "c": warehouse.hex[:20]},
    )
    db.commit()
    return warehouse


@pytest.mark.parametrize(
    "field", ["customer_id", "product_id", "warehouse_id", "batch_id", "invoice_id"]
)
@pytest.mark.parametrize("invalid", ["not-a-uuid", "invalid\x00reference"])
def test_malformed_reference_is_422_without_writes(invoice_env, field, invalid):
    _client, db, ids, _payload, headers = invoice_env
    auth = headers("owner")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/returns", headers=auth, json=body(ids, **{field: invalid})
        )
    assert response.status_code == 422, response.text
    assert db.execute(text("SELECT count(*) FROM sales.sales_return")).scalar_one() == 0
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM audit.audit_log WHERE entity_type='sales_return'"
            )
        ).scalar_one()
        == 0
    )


@pytest.mark.parametrize(
    "invalid", ["0", "-1", "0.0001", "9999999999", "NaN", "Infinity", True]
)
def test_unrepresentable_quantity_is_422_without_rounding_or_writes(
    invoice_env, invalid
):
    _client, db, ids, _payload, headers = invoice_env
    auth = headers("owner")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/returns", headers=auth, json=body(ids, quantity=invalid)
        )
    assert response.status_code == 422, response.text
    assert db.execute(text("SELECT count(*) FROM sales.sales_return")).scalar_one() == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"return_date": "not-a-date"},
        {"return_date": "2026-13-01"},
        {"reason": "synthetic\x00reason"},
        {"reason": {"unexpected": "object"}},
    ],
)
def test_invalid_date_or_reason_is_422_before_sql(invoice_env, changes):
    _client, db, ids, _payload, headers = invoice_env
    auth = headers("owner")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/returns", headers=auth, json=body(ids, **changes))
    assert response.status_code == 422, response.text
    assert db.execute(text("SELECT count(*) FROM sales.sales_return")).scalar_one() == 0


def test_return_list_preserves_persisted_decimal_as_json_text(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    auth = headers("owner")
    created = client.post(
        "/returns", headers=auth, json=body(ids, quantity="+1.23000e0")
    )
    assert created.status_code == 201, created.text
    rows = client.get("/returns", headers=auth).json()
    row = next(row for row in rows if row["id"] == created.json()["id"])
    persisted = db.execute(
        text("SELECT quantity FROM sales.sales_return WHERE id=:id"), {"id": row["id"]}
    ).scalar_one()
    assert isinstance(row["quantity"], str)
    assert row["quantity"] == str(persisted)
    assert Decimal(row["quantity"]) == Decimal("1.23")
    assert row["status"] == "quarantined"


def test_sales_manager_cannot_intake_foreign_territory_customer(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    set_role(db, ids, "sales_manager")
    auth = headers("other")
    denied = client.post(
        "/returns", headers=auth, json=body(ids, customer_id=str(ids["other_customer"]))
    )
    assert denied.status_code == 404, denied.text
    assert db.execute(text("SELECT count(*) FROM sales.sales_return")).scalar_one() == 0
    own = client.post("/returns", headers=auth, json=body(ids))
    assert own.status_code == 201, own.text
    assert client.get("/returns", headers=auth).json()[0]["id"] == own.json()["id"]


def test_sales_manager_cannot_intake_unowned_warehouse(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    warehouse = other_warehouse(db)
    set_role(db, ids, "sales_manager")
    auth = headers("other")
    denied = client.post(
        "/returns", headers=auth, json=body(ids, warehouse_id=str(warehouse))
    )
    assert denied.status_code == 404, denied.text
    assert db.execute(text("SELECT count(*) FROM sales.sales_return")).scalar_one() == 0
    own = client.post("/returns", headers=auth, json=body(ids))
    assert own.status_code == 201, own.text


@pytest.mark.parametrize("role", ["sales_manager", "district_manager"])
def test_scoped_return_history_requires_both_customer_territory_and_owned_warehouse(
    invoice_env, role
):
    client, db, ids, _payload, headers = invoice_env
    warehouse = other_warehouse(db)
    owner = headers("owner")
    visible = client.post("/returns", headers=owner, json=body(ids))
    hidden_customer = client.post(
        "/returns",
        headers=owner,
        json=body(ids, customer_id=str(ids["other_customer"])),
    )
    hidden_warehouse = client.post(
        "/returns", headers=owner, json=body(ids, warehouse_id=str(warehouse))
    )
    assert [
        visible.status_code,
        hidden_customer.status_code,
        hidden_warehouse.status_code,
    ] == [201, 201, 201]
    set_role(db, ids, role)
    scoped = headers("other")
    listed = client.get("/returns", headers=scoped)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()} == {visible.json()["id"]}
    filtered = client.get(
        "/returns", headers=scoped, params={"customer_id": str(ids["other_customer"])}
    )
    assert filtered.status_code == 200 and filtered.json() == []


@pytest.mark.parametrize("role", ["finance", "warehouse_staff", "read_only_auditor"])
def test_existing_global_return_read_roles_do_not_lose_access(invoice_env, role):
    client, db, ids, _payload, headers = invoice_env
    warehouse = other_warehouse(db)
    owner = headers("owner")
    recorded = client.post(
        "/returns", headers=owner, json=body(ids, warehouse_id=str(warehouse))
    )
    assert recorded.status_code == 201, recorded.text
    set_role(db, ids, role)
    db.execute(
        text("DELETE FROM platform.user_branch WHERE user_id=:u"), {"u": ids["other"]}
    )
    db.execute(
        text("DELETE FROM platform.user_territory WHERE user_id=:u"),
        {"u": ids["other"]},
    )
    db.commit()
    auth = headers("other")
    response = client.get("/returns", headers=auth)
    assert response.status_code == 200, response.text
    assert {row["id"] for row in response.json()} == {recorded.json()["id"]}
    intake = client.post("/returns", headers=auth, json=body(ids))
    assert intake.status_code == (403 if role == "read_only_auditor" else 201), (
        intake.text
    )


def test_optional_invoice_reference_must_match_return_customer(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers("owner")
    original = client.post("/invoices", headers=auth, json=payload)
    assert original.status_code == 201, original.text
    invoice = original.json()
    denied = client.post(
        "/returns",
        headers=auth,
        json=body(
            ids, customer_id=str(ids["other_customer"]), invoice_id=invoice["id"]
        ),
    )
    assert denied.status_code == 422, denied.text
    assert db.execute(text("SELECT count(*) FROM sales.sales_return")).scalar_one() == 0
    accepted = client.post(
        "/returns", headers=auth, json=body(ids, invoice_id=invoice["id"])
    )
    assert accepted.status_code == 201, accepted.text
    reopened = client.get("/invoices/" + invoice["id"], headers=auth)
    assert reopened.status_code == 200 and reopened.json() == invoice
