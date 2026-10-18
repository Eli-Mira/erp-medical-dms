"""Real committed lifecycle controls; refuses every non-disposable database."""

import os
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


def sql(statement, **params):
    with engine.begin() as connection:
        result = connection.execute(text(statement), params)
        return [dict(row) for row in result.mappings()] if result.returns_rows else []


def scalar(statement, **params):
    return next(iter(sql(statement, **params)[0].values()))


@pytest.fixture
def life(monkeypatch):
    assert os.environ.get("APP_ENV") == "test"
    assert engine.url.database.startswith("dms_cycle_test_")
    assert scalar("SELECT current_database()") == engine.url.database
    import app.finance.payment_router as payments_router
    import app.sales.router as sales_router

    monkeypatch.setattr(sales_router, "POSTING_ENABLED", True)
    monkeypatch.setattr(payments_router, "POSTING_ENABLED", True)

    def clear():
        # This fixture owns synthetic state only in the freshly-created disposable DB.
        sql(
            "TRUNCATE platform.platform_user, master_data.master_branch, "
            "master_data.master_product, master_data.master_territory, audit.reason_code CASCADE"
        )

    clear()
    ids = {
        name: uuid4()
        for name in (
            "branch",
            "other_branch",
            "territory",
            "other_territory",
            "warehouse",
            "other_warehouse",
            "customer",
            "other_customer",
            "product",
            "product2",
            "reason",
        )
    }
    auth = {}
    for role in (
        "owner",
        "finance",
        "sales_manager",
        "district_manager",
        "medical_rep",
        "read_only_auditor",
        "warehouse_staff",
        "admin",
    ):
        uid, sid = uuid4(), uuid4()
        ids[role] = uid
        sql(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
            "VALUES (:i,:u,'synthetic-unused',:r,:o)",
            i=uid,
            u=uid.hex,
            r=role,
            o=role == "owner",
        )
        sql(
            "INSERT INTO platform.platform_session(id,user_id,expires_at) "
            "VALUES (:s,:u,now()+interval '1 hour')",
            s=sid,
            u=uid,
        )
        auth[role] = {"Authorization": f"Bearer {sid}"}
    for prefix in ("", "other_"):
        sql(
            "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:i,:c,'Synthetic')",
            i=ids[prefix + "branch"],
            c=uuid4().hex[:20],
        )
        sql(
            "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:i,:c,'Synthetic')",
            i=ids[prefix + "territory"],
            c=uuid4().hex[:20],
        )
        sql(
            "INSERT INTO master_data.master_warehouse(id,code,name_ar,branch_id) "
            "VALUES (:i,:c,'Synthetic',:b)",
            i=ids[prefix + "warehouse"],
            c=uuid4().hex[:20],
            b=ids[prefix + "branch"],
        )
        sql(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
            "VALUES (:i,:c,'Synthetic',:b,:t)",
            i=ids[prefix + "customer"],
            c=uuid4().hex[:20],
            b=ids[prefix + "branch"],
            t=ids[prefix + "territory"],
        )
    for role in auth:
        sql(
            "INSERT INTO platform.user_territory VALUES (:u,:t)",
            u=ids[role],
            t=ids["territory"],
        )
        sql(
            "INSERT INTO platform.user_branch VALUES (:u,:b)",
            u=ids[role],
            b=ids["branch"],
        )
    for key, price, vat in (("product", "114", "14"), ("product2", "105", "5")):
        sql(
            "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) "
            "VALUES (:i,:s,'Synthetic',:p,:v)",
            i=ids[key],
            s=uuid4().hex,
            p=Decimal(price),
            v=Decimal(vat),
        )
        sql(
            "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) VALUES (:w,:p,10)",
            w=ids["warehouse"],
            p=ids[key],
        )
    sql(
        "INSERT INTO audit.reason_code(id,code,category) VALUES (:i,:c,'void')",
        i=ids["reason"],
        c=uuid4().hex[:30],
    )
    client = TestClient(app, raise_server_exceptions=False)
    previous = app.dependency_overrides.get(get_db)

    def bounded_db():
        with Session(engine) as db:
            db.execute(text("SET LOCAL lock_timeout='5s'"))
            db.execute(text("SET LOCAL statement_timeout='12s'"))
            yield db

    app.dependency_overrides[get_db] = bounded_db

    def draft(quantity="2", lines=None, **overrides):
        payload = {
            "invoice_no": uuid4().hex[:30],
            "branch_id": str(ids["branch"]),
            "warehouse_id": str(ids["warehouse"]),
            "customer_id": str(ids["customer"]),
            "invoice_date": datetime.now(UTC).astimezone().date().isoformat(),
            "lines": lines
            or [{"product_id": str(ids["product"]), "quantity": quantity}],
        }
        payload.update(overrides)
        response = client.post("/invoices", json=payload, headers=auth["owner"])
        assert response.status_code == 201, response.text
        return response.json()

    def post(invoice=None):
        invoice = draft() if invoice is None else invoice
        response = client.post(f"/invoices/{invoice['id']}/post", headers=auth["owner"])
        assert response.status_code == 200, response.text
        return response.json()

    def collect(invoice, amount="100.00", **overrides):
        payload = {
            "invoice_id": invoice["id"],
            "invoice_version": invoice["version"],
            "receipt_no": uuid4().hex[:30],
            "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
            "amount": amount,
            "method": "cash",
        }
        payload.update(overrides)
        return client.post("/collections", json=payload, headers=auth["finance"])

    def reverse(invoice, **overrides):
        payload = {"version": invoice["version"], "reason_id": str(ids["reason"])}
        payload.update(overrides)
        return client.post(
            f"/invoices/{invoice['id']}/reverse", json=payload, headers=auth["owner"]
        )

    def void(receipt, **overrides):
        payload = {"version": receipt["version"], "reason_id": str(ids["reason"])}
        payload.update(overrides)
        return client.post(
            f"/collections/{receipt['id']}/void", json=payload, headers=auth["finance"]
        )

    env = SimpleNamespace(
        ids=ids,
        auth=auth,
        client=client,
        draft=draft,
        post=post,
        collect=collect,
        reverse=reverse,
        void=void,
    )
    try:
        with client:
            yield env
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        clear()


def state(life):
    return {
        "invoices": sql("SELECT * FROM sales.sales_invoice ORDER BY id"),
        "lines": sql("SELECT * FROM sales.sales_invoice_line ORDER BY id"),
        "stock": sql("SELECT * FROM inventory.stock_balance ORDER BY id"),
        "movements": sql("SELECT * FROM inventory.stock_movement ORDER BY id"),
        "ar": sql("SELECT * FROM finance.ar_entry ORDER BY id"),
        "receipts": sql("SELECT * FROM finance.payment_receipt ORDER BY id"),
        "audits": sql("SELECT * FROM audit.audit_log ORDER BY id"),
    }


def test_posted_invoice_rejects_raw_snapshot_mutation(life):
    invoice = life.post()
    before = state(life)
    with pytest.raises(DBAPIError):
        sql(
            "UPDATE sales.sales_invoice SET invoice_no='tampered' WHERE id=:i",
            i=UUID(invoice["id"]),
        )
    assert state(life) == before


def test_posting_revalidates_source_grant(life):
    invoice = life.draft()
    sql(
        "DELETE FROM platform.user_branch WHERE user_id=:u", u=life.ids["sales_manager"]
    )
    before = state(life)
    response = life.client.post(
        f"/invoices/{invoice['id']}/post", headers=life.auth["sales_manager"]
    )
    assert response.status_code == 404, response.text
    assert state(life) == before


def test_reversal_links_exact_original_entries(life):
    invoice = life.post()
    sale = sql(
        "SELECT * FROM inventory.stock_movement WHERE source_id=:i AND movement_type='sale'",
        i=UUID(invoice["id"]),
    )[0]
    debit = sql(
        "SELECT * FROM finance.ar_entry WHERE invoice_id=:i AND entry_type='invoice'",
        i=UUID(invoice["id"]),
    )[0]
    response = life.reverse(invoice)
    assert response.status_code == 200, response.text
    counter = sql(
        "SELECT * FROM inventory.stock_movement WHERE source_id=:i AND movement_type='return'",
        i=UUID(invoice["id"]),
    )[0]
    credit = sql(
        "SELECT * FROM finance.ar_entry WHERE invoice_id=:i AND entry_type='credit_note'",
        i=UUID(invoice["id"]),
    )[0]
    assert counter["reverses_movement_id"] == sale["id"]
    assert counter["quantity"] == -sale["quantity"]
    assert counter["source_type"] == "invoice"
    assert credit["reverses_entry_id"] == debit["id"]
    assert credit["credit"] == debit["debit"]


def test_collection_list_respects_territory_revocation(life):
    invoice = life.post()
    receipt = life.collect(invoice).json()
    sql("DELETE FROM platform.user_territory WHERE user_id=:u", u=life.ids["finance"])
    response = life.client.get("/collections", headers=life.auth["finance"])
    assert response.status_code == 200, response.text
    assert response.json() == []
    assert (
        life.client.get(
            f"/collections/{receipt['id']}", headers=life.auth["finance"]
        ).status_code
        == 404
    )


def test_receipt_void_links_the_original_payment(life):
    invoice = life.post()
    receipt = life.collect(invoice).json()
    assert life.void(receipt).status_code == 200
    entries = sql(
        "SELECT * FROM finance.ar_entry WHERE receipt_id=:r ORDER BY created_at",
        r=UUID(receipt["id"]),
    )
    assert len(entries) == 2
    payment, reversal = entries
    assert payment["entry_type"] == "payment"
    assert reversal["reverses_entry_id"] == payment["id"]
    assert reversal["debit"] == payment["credit"]
