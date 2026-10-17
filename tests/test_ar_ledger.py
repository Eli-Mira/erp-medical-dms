"""Customer receivables ledger tests: real PostgreSQL, no mocks."""
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


@pytest.fixture
def ar_env():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids = {name: uuid4() for name in (
        "owner", "other", "branch", "other_branch", "territory", "customer", "other_customer", "reason")}
    for role, uid, owner in [("owner", ids["owner"], True), ("finance", ids["other"], False)]:
        db.execute(text("INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) VALUES (:id,:u,'unused',:role,:owner)"),
                   {"id": uid, "u": f"ar_test_{uid.hex}", "role": role, "owner": owner})
    for key in ("branch", "other_branch"):
        db.execute(text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'Test branch')"),
                   {"id": ids[key], "code": ids[key].hex[:20]})
    db.execute(text("INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,'Test territory')"),
               {"id": ids["territory"], "code": ids["territory"].hex[:20]})
    for key, branch in (("customer", "branch"), ("other_customer", "other_branch")):
        db.execute(text("INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:code,'Test customer',:branch,:terr)"),
                   {"id": ids[key], "code": ids[key].hex[:30], "branch": ids[branch], "terr": ids["territory"]})
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

        def entry(**overrides):
            body = {"customer_id": str(ids["customer"]), "entry_type": "opening",
                    "debit": "100.00", "entry_date": date.today().isoformat()}
            body.update(overrides)
            return body

        yield client, db, ids, headers, entry
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()


def test_ar_routes_require_authentication():
    with TestClient(app) as client:
        assert client.get("/ar/balances").status_code == 401
        assert client.get("/ar/entries").status_code == 401
        assert client.post("/ar/entries", json={}).status_code == 401


def test_opening_debit_and_payment_credit_change_balance(ar_env):
    client, db, ids, headers, entry = ar_env
    auth = headers()
    created = client.post("/ar/entries", json=entry(), headers=auth)
    assert created.status_code == 201, created.text
    assert created.json()["debit"] == "100.00"
    client.post("/ar/entries", json=entry(entry_type="payment", debit="0", credit="40.00"), headers=auth)
    balance = client.get(f"/ar/balances?customer_id={ids['customer']}", headers=auth).json()
    assert balance == [{"customer_id": str(ids["customer"]), "balance": "60.00"}]
    ledger = client.get(f"/ar/entries?customer_id={ids['customer']}", headers=auth).json()
    assert len(ledger) == 2
    events = db.execute(text("SELECT action,entity_type FROM audit.audit_log WHERE entity_type='ar_entry'")).all()
    assert len(events) == 2
    assert all((e.action, e.entity_type) == ("created", "ar_entry") for e in events)


def test_balance_is_debits_minus_credits(ar_env):
    client, db, ids, headers, entry = ar_env
    auth = headers()
    client.post("/ar/entries", json=entry(debit="1000.00"), headers=auth)
    client.post("/ar/entries", json=entry(entry_type="payment", debit="0", credit="250.00"), headers=auth)
    client.post("/ar/entries", json=entry(entry_type="credit_note", debit="0", credit="150.00"), headers=auth)
    balance = client.get(f"/ar/balances?customer_id={ids['customer']}", headers=auth).json()[0]["balance"]
    assert balance == "600.00"  # 1000 - 250 - 150


def test_invoice_entry_type_reserved_for_posting(ar_env):
    client, db, ids, headers, entry = ar_env
    response = client.post("/ar/entries", json=entry(entry_type="invoice"), headers=headers())
    assert response.status_code == 422, response.text
    assert client.get(f"/ar/entries?customer_id={ids['customer']}", headers=headers()).json() == []


def test_entry_requires_a_side_and_adjustment_requires_reason(ar_env):
    client, db, ids, headers, entry = ar_env
    auth = headers()
    assert client.post("/ar/entries", json=entry(debit="0", credit="0"), headers=auth).status_code == 422
    assert client.post("/ar/entries", json=entry(entry_type="adjustment", debit="5.00"), headers=auth).status_code == 422
    assert client.post("/ar/entries", json=entry(entry_type="adjustment", debit="5.00", reason_id=str(ids["reason"])), headers=auth).status_code == 201


def test_unknown_customer_rejected(ar_env):
    client, db, ids, headers, entry = ar_env
    assert client.post("/ar/entries", json=entry(customer_id=str(uuid4())), headers=headers()).status_code == 422


@pytest.mark.parametrize("role", ["owner", "finance"])
def test_write_roles_can_record_entries(ar_env, role):
    client, db, ids, headers, entry = ar_env
    if role == "owner":
        auth = headers()
    else:
        db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"), {"r": role, "id": ids["other"]})
        db.commit()
        auth = headers("other")
    assert client.post("/ar/entries", json=entry(), headers=auth).status_code == 201


@pytest.mark.parametrize("role", ["sales_manager", "district_manager", "read_only_auditor", "warehouse_staff", "medical_rep", "admin", "user"])
def test_other_roles_cannot_record_entries(ar_env, role):
    client, db, ids, headers, entry = ar_env
    db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"), {"r": role, "id": ids["other"]})
    db.commit()
    assert client.post("/ar/entries", json=entry(), headers=headers("other")).status_code == 403


@pytest.mark.parametrize("role", ["owner", "finance", "sales_manager", "district_manager", "read_only_auditor"])
def test_read_roles_can_view_balances(ar_env, role):
    client, db, ids, headers, entry = ar_env
    if role == "owner":
        auth = headers()
    else:
        db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"), {"r": role, "id": ids["other"]})
        db.commit()
        auth = headers("other")
    assert client.get("/ar/balances", headers=auth).status_code == 200


@pytest.mark.parametrize("role", ["warehouse_staff", "medical_rep", "admin"])
def test_non_ar_roles_cannot_view_balances(ar_env, role):
    client, db, ids, headers, entry = ar_env
    db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"), {"r": role, "id": ids["other"]})
    db.commit()
    assert client.get("/ar/balances", headers=headers("other")).status_code == 403


def test_branch_scoped_manager_sees_only_assigned_branch(ar_env):
    client, db, ids, headers, entry = ar_env
    # customer (branch A) and other_customer (branch B) both have balances
    client.post("/ar/entries", json=entry(), headers=headers())
    client.post("/ar/entries", json=entry(customer_id=str(ids["other_customer"])), headers=headers())
    db.execute(text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"), {"id": ids["other"]})
    db.execute(text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
               {"u": ids["other"], "b": ids["branch"]})
    db.commit()
    auth = headers("other")
    balances = client.get("/ar/balances", headers=auth).json()
    assert balances == [{"customer_id": str(ids["customer"]), "balance": "100.00"}]
    # direct lookup of the other branch's customer is denied
    assert client.get(f"/ar/balances?customer_id={ids['other_customer']}", headers=auth).status_code == 404
    assert client.get(f"/ar/balances?customer_id={ids['customer']}", headers=auth).status_code == 200


def test_manager_without_branch_assignment_sees_nothing(ar_env):
    client, db, ids, headers, entry = ar_env
    client.post("/ar/entries", json=entry(), headers=headers())
    db.execute(text("UPDATE platform.platform_user SET role='district_manager' WHERE id=:id"), {"id": ids["other"]})
    db.commit()
    assert client.get("/ar/balances", headers=headers("other")).json() == []
