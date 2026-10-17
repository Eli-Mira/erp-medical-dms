"""Inventory API integration tests: real PostgreSQL, no repository mocks."""
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


@pytest.fixture
def stock_env():
    """Every request uses real SQL; API commits are contained in an outer rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids = {name: uuid4() for name in (
        "owner", "other", "branch", "warehouse", "other_warehouse",
        "product", "other_product", "batch", "reason",
    )}
    for role, uid, owner in [("owner", ids["owner"], True), ("warehouse_staff", ids["other"], False)]:
        db.execute(text("INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) VALUES (:id,:u,'unused',:role,:owner)"),
                   {"id": uid, "u": f"stock_test_{uid.hex}", "role": role, "owner": owner})
    db.execute(text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'Test branch')"),
               {"id": ids["branch"], "code": ids["branch"].hex[:20]})
    for key in ("warehouse", "other_warehouse"):
        db.execute(text("INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:branch,:code,'Test warehouse')"),
                   {"id": ids[key], "branch": ids["branch"], "code": ids[key].hex[:20]})
    for key in ("product", "other_product"):
        db.execute(text("INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'Test product',100,'14.00')"),
                   {"id": ids[key], "sku": ids[key].hex})
    db.execute(text("INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date) VALUES (:id,:p,:w,'TEST',:expiry)"),
               {"id": ids["batch"], "p": ids["product"], "w": ids["warehouse"],
                "expiry": date.today() + timedelta(days=365)})
    db.execute(text("INSERT INTO audit.reason_code(id,code,category) VALUES (:id,:code,'adjustment')"),
               {"id": ids["reason"], "code": ids["reason"].hex[:30]})
    db.commit()

    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        def headers(user="owner"):
            sid = uuid4()
            db.execute(text("INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:sid,:uid,now() + interval '1 hour')"),
                       {"sid": sid, "uid": ids[user]})
            db.commit()
            return {"Authorization": f"Bearer {sid}"}

        def movement(**overrides):
            body = {"warehouse_id": str(ids["warehouse"]), "product_id": str(ids["product"]),
                    "movement_type": "opening", "quantity": "10"}
            body.update(overrides)
            return body

        yield client, db, ids, headers, movement
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()


def test_inventory_routes_require_authentication():
    with TestClient(app) as client:
        assert client.get("/inventory/stock").status_code == 401
        assert client.get("/inventory/movements").status_code == 401
        assert client.post("/inventory/movements", json={}).status_code == 401


def test_opening_stock_records_movement_and_balance(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    response = client.post("/inventory/movements", json=movement(), headers=auth)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["movement"]["movement_type"] == "opening"
    assert body["movement"]["quantity"] == "10.000"
    assert body["movement"]["source_type"] == "manual"
    assert body["balance_quantity"] == "10.000"
    stock = client.get("/inventory/stock", headers=auth).json()
    assert [(row["product_id"], row["quantity"]) for row in stock] == [(str(ids["product"]), "10.000")]
    ledger = client.get("/inventory/movements", headers=auth).json()
    assert len(ledger) == 1
    assert ledger[0]["created_by"] == str(ids["owner"])
    event = db.execute(text("SELECT action,entity_type FROM audit.audit_log WHERE entity_type='stock_movement'")).one()
    assert (event.action, event.entity_type) == ("created", "stock_movement")


def test_movements_accumulate_balance(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    client.post("/inventory/movements", json=movement(quantity="10"), headers=auth)
    client.post("/inventory/movements", json=movement(
        movement_type="adjustment", quantity="5", reason_id=str(ids["reason"])), headers=auth)
    response = client.post("/inventory/movements", json=movement(
        movement_type="adjustment", quantity="-3", reason_id=str(ids["reason"])), headers=auth)
    assert response.status_code == 201, response.text
    assert response.json()["balance_quantity"] == "12.000"
    assert len(client.get("/inventory/movements", headers=auth).json()) == 3
    assert client.get("/inventory/stock", headers=auth).json()[0]["quantity"] == "12.000"


def test_insufficient_stock_rejected_and_nothing_written(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    response = client.post("/inventory/movements", json=movement(
        movement_type="adjustment", quantity="-1", reason_id=str(ids["reason"])), headers=auth)
    assert response.status_code == 409, response.text
    assert client.get("/inventory/stock", headers=auth).json() == []
    assert client.get("/inventory/movements", headers=auth).json() == []
    assert db.execute(text("SELECT count(*) FROM inventory.stock_balance")).scalar_one() == 0


def test_overdraw_after_stock_exists_is_rejected(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    client.post("/inventory/movements", json=movement(quantity="5"), headers=auth)
    response = client.post("/inventory/movements", json=movement(
        movement_type="adjustment", quantity="-6", reason_id=str(ids["reason"])), headers=auth)
    assert response.status_code == 409, response.text
    assert client.get("/inventory/stock", headers=auth).json()[0]["quantity"] == "5.000"


def test_negative_balance_blocked_at_database(stock_env):
    from sqlalchemy.exc import IntegrityError
    client, db, ids, headers, movement = stock_env
    with pytest.raises(IntegrityError) as rejected:
        with db.begin_nested():
            db.execute(text("INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) VALUES (:w,:p,-1)"),
                       {"w": ids["warehouse"], "p": ids["product"]})
    assert rejected.value.orig.diag.constraint_name == "ck_stock_balance_nonneg"


def test_batched_and_unbatched_stock_are_separate(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    client.post("/inventory/movements", json=movement(quantity="10", batch_id=str(ids["batch"])), headers=auth)
    client.post("/inventory/movements", json=movement(quantity="4"), headers=auth)
    stock = client.get("/inventory/stock", headers=auth).json()
    assert sorted(row["quantity"] for row in stock) == ["10.000", "4.000"]
    filtered = client.get(f"/inventory/stock?batch_id={ids['batch']}", headers=auth).json()
    assert [row["quantity"] for row in filtered] == ["10.000"]


def test_stock_is_separated_by_warehouse(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    client.post("/inventory/movements", json=movement(quantity="10"), headers=auth)
    client.post("/inventory/movements", json=movement(
        warehouse_id=str(ids["other_warehouse"]), quantity="3"), headers=auth)
    assert len(client.get("/inventory/stock", headers=auth).json()) == 2
    filtered = client.get(f"/inventory/stock?warehouse_id={ids['other_warehouse']}", headers=auth).json()
    assert [row["quantity"] for row in filtered] == ["3.000"]


def test_adjustment_requires_active_reason_code(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    client.post("/inventory/movements", json=movement(), headers=auth)
    adjust = movement(movement_type="adjustment", quantity="1")
    assert client.post("/inventory/movements", json=adjust, headers=auth).status_code == 422
    db.execute(text("UPDATE audit.reason_code SET is_active=false WHERE id=:id"), {"id": ids["reason"]})
    db.commit()
    assert client.post("/inventory/movements", json={**adjust, "reason_id": str(ids["reason"])}, headers=auth).status_code == 422
    assert client.post("/inventory/movements", json={**adjust, "reason_id": str(uuid4())}, headers=auth).status_code == 422


def test_batch_must_match_product_and_warehouse(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    assert client.post("/inventory/movements", json=movement(batch_id=str(uuid4())), headers=auth).status_code == 422
    assert client.post("/inventory/movements", json=movement(
        product_id=str(ids["other_product"]), batch_id=str(ids["batch"])), headers=auth).status_code == 422
    assert client.post("/inventory/movements", json=movement(
        warehouse_id=str(ids["other_warehouse"]), batch_id=str(ids["batch"])), headers=auth).status_code == 422
    assert client.get("/inventory/stock", headers=auth).json() == []


def test_inactive_product_or_warehouse_rejected(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    db.execute(text("UPDATE master_data.master_product SET is_active=false WHERE id=:id"), {"id": ids["product"]})
    db.commit()
    assert client.post("/inventory/movements", json=movement(), headers=auth).status_code == 422


@pytest.mark.parametrize("reserved", ["sale", "return", "transfer_in", "transfer_out", "receipt"])
def test_reserved_movement_types_rejected(stock_env, reserved):
    client, db, ids, headers, movement = stock_env
    assert client.post("/inventory/movements", json=movement(movement_type=reserved),
                       headers=headers()).status_code == 422


@pytest.mark.parametrize(("movement_type", "quantity"), [
    ("opening", "0"), ("opening", "-1"), ("opening", "1.0001"), ("opening", "NaN"),
    ("adjustment", "0"), ("adjustment", "1.0001"),
])
def test_invalid_quantities_rejected(stock_env, movement_type, quantity):
    client, db, ids, headers, movement = stock_env
    body = movement(movement_type=movement_type, quantity=quantity)
    if movement_type == "adjustment":
        body["reason_id"] = str(ids["reason"])
    assert client.post("/inventory/movements", json=body, headers=headers()).status_code == 422


@pytest.mark.parametrize("role", ["owner", "finance", "warehouse_staff"])
def test_write_roles_can_record_movements(stock_env, role):
    client, db, ids, headers, movement = stock_env
    if role == "owner":
        auth = headers()
    else:
        db.execute(text("UPDATE platform.platform_user SET role=:role WHERE id=:id"), {"role": role, "id": ids["other"]})
        db.commit()
        auth = headers("other")
    assert client.post("/inventory/movements", json=movement(), headers=auth).status_code == 201


@pytest.mark.parametrize("role", ["sales_manager", "district_manager", "medical_rep", "admin", "read_only_auditor", "user"])
def test_other_roles_cannot_record_movements(stock_env, role):
    client, db, ids, headers, movement = stock_env
    db.execute(text("UPDATE platform.platform_user SET role=:role WHERE id=:id"), {"role": role, "id": ids["other"]})
    db.commit()
    assert client.post("/inventory/movements", json=movement(), headers=headers("other")).status_code == 403


@pytest.mark.parametrize("role", ["owner", "finance", "warehouse_staff", "read_only_auditor"])
def test_read_roles_can_view_stock(stock_env, role):
    client, db, ids, headers, movement = stock_env
    client.post("/inventory/movements", json=movement(), headers=headers())
    if role == "owner":
        auth = headers()
    else:
        db.execute(text("UPDATE platform.platform_user SET role=:role WHERE id=:id"), {"role": role, "id": ids["other"]})
        db.commit()
        auth = headers("other")
    assert client.get("/inventory/stock", headers=auth).status_code == 200
    assert client.get("/inventory/movements", headers=auth).status_code == 200


@pytest.mark.parametrize("role", ["sales_manager", "district_manager", "medical_rep"])
def test_branch_scoped_roles_without_assignment_are_denied(stock_env, role):
    # An available assignment table is not itself an access grant.
    client, db, ids, headers, movement = stock_env
    db.execute(text("UPDATE platform.platform_user SET role=:role WHERE id=:id"), {"role": role, "id": ids["other"]})
    db.commit()
    assert client.get("/inventory/stock", headers=headers("other")).status_code == 403


def test_owner_label_without_owner_flag_cannot_elevate_access(stock_env):
    client, db, ids, headers, movement = stock_env
    db.execute(text("UPDATE platform.platform_user SET role='owner' WHERE id=:id"), {"id": ids["other"]})
    db.commit()
    assert client.post("/inventory/movements", json=movement(), headers=headers("other")).status_code == 403


def test_audit_failure_rolls_back_movement_and_balance(stock_env, monkeypatch):
    from app.inventory import router as inventory_router
    client, db, ids, headers, movement = stock_env
    auth = headers()

    def audit_unavailable(*args, **kwargs):
        raise RuntimeError("Injected audit failure")

    monkeypatch.setattr(inventory_router, "log_audit", audit_unavailable)
    with pytest.raises(RuntimeError, match="Injected audit failure"):
        client.post("/inventory/movements", json=movement(), headers=auth)
    assert db.execute(text("SELECT count(*) FROM inventory.stock_movement")).scalar_one() == 0
    assert db.execute(text("SELECT count(*) FROM inventory.stock_balance")).scalar_one() == 0


def test_ledger_filters_by_product_and_type(stock_env):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    client.post("/inventory/movements", json=movement(quantity="10"), headers=auth)
    client.post("/inventory/movements", json=movement(product_id=str(ids["other_product"]), quantity="2"), headers=auth)
    assert len(client.get("/inventory/movements", headers=auth).json()) == 2
    assert len(client.get(f"/inventory/movements?product_id={ids['product']}", headers=auth).json()) == 1
    assert len(client.get("/inventory/movements?movement_type=opening", headers=auth).json()) == 2
    assert client.get("/inventory/movements?movement_type=sale", headers=auth).json() == []
