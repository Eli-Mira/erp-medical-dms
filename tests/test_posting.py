"""Atomic Invoice -> Stock -> AR posting transaction (called directly).

The HTTP endpoint POST /invoices/{id}/post stays disabled (409); these tests
exercise app.sales.service.post_invoice_atomic directly, which is the tested
transaction that would sit behind the endpoint once posting is enabled.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app
from app.inventory.service import InsufficientStock
from app.sales.service import post_invoice_atomic


@pytest.fixture
def posting_env():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids = {name: uuid4() for name in ("owner", "branch", "territory", "customer", "warehouse", "product")}
    db.execute(text("INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) VALUES (:id,:u,'unused','owner',true)"),
               {"id": ids["owner"], "u": f"post_test_{ids['owner'].hex}"})
    db.execute(text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'Test branch')"),
               {"id": ids["branch"], "code": ids["branch"].hex[:20]})
    db.execute(text("INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,'Test territory')"),
               {"id": ids["territory"], "code": ids["territory"].hex[:20]})
    db.execute(text("INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:code,'Test customer',:b,:t)"),
               {"id": ids["customer"], "code": ids["customer"].hex[:30], "b": ids["branch"], "t": ids["territory"]})
    db.execute(text("INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:b,:code,'Test warehouse')"),
               {"id": ids["warehouse"], "b": ids["branch"], "code": ids["warehouse"].hex[:20]})
    db.execute(text("INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'Test product',114,'14.00')"),
               {"id": ids["product"], "sku": ids["product"].hex})
    # opening stock of 10 units, no batch
    db.execute(text("INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) VALUES (:w,:p,10)"),
               {"w": ids["warehouse"], "p": ids["product"]})
    db.commit()

    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        sid = uuid4()
        db.execute(text("INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:sid,:uid,now() + interval '1 hour')"),
                   {"sid": sid, "uid": ids["owner"]})
        db.commit()
        auth = {"Authorization": f"Bearer {sid}"}
        payload = {"invoice_no": f"P-{uuid4().hex[:20]}", "branch_id": str(ids["branch"]),
                   "warehouse_id": str(ids["warehouse"]), "customer_id": str(ids["customer"]),
                   "invoice_date": date.today().isoformat(),
                   "lines": [{"product_id": str(ids["product"]), "quantity": "2", "discount_pct": "0"}]}
        invoice = client.post("/invoices", json=payload, headers=auth).json()
        yield client, db, ids, auth, invoice, payload
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()


def _stock(db, ids):
    return db.execute(text(
        "SELECT quantity FROM inventory.stock_balance WHERE warehouse_id=:w AND product_id=:p AND batch_id IS NULL"),
        {"w": ids["warehouse"], "p": ids["product"]}).scalar_one()


def test_post_invoice_atomic_decrements_stock_creates_ar_and_posts(posting_env):
    from app.finance import ar
    client, db, ids, auth, invoice, payload = posting_env
    assert invoice["grand_total"] == "228.00"  # 2 x 114 incl 14% VAT
    posted = post_invoice_atomic(db, UUID(invoice["id"]), ids["owner"])
    db.commit()

    assert posted["posting_status"] == "Posted"
    assert posted["posted_by"] == ids["owner"]
    assert posted["posted_at"] is not None
    assert posted["version"] == 2
    # stock decremented 10 -> 8, movement recorded as a sale sourced from the invoice
    assert str(_stock(db, ids)) == "8.000"
    movement = db.execute(text(
        "SELECT movement_type, quantity, source_type, source_id FROM inventory.stock_movement WHERE source_id=:i"),
        {"i": UUID(invoice["id"])}).one()
    assert movement.movement_type == "sale"
    assert str(movement.quantity) == "-2.000"
    assert movement.source_type == "invoice"
    # AR debit equals the invoice grand total
    assert ar.customer_balance(db, ids["customer"]) == Decimal("228.00")
    entry = db.execute(text("SELECT entry_type, debit, credit FROM finance.ar_entry WHERE invoice_id=:i"),
                       {"i": UUID(invoice["id"])}).one()
    assert (entry.entry_type, str(entry.debit), str(entry.credit)) == ("invoice", "228.00", "0.00")


def test_post_insufficient_stock_rolls_back_everything(posting_env):
    from app.finance import ar
    client, db, ids, auth, invoice, payload = posting_env
    db.execute(text("UPDATE inventory.stock_balance SET quantity=1 WHERE warehouse_id=:w AND product_id=:p"),
               {"w": ids["warehouse"], "p": ids["product"]})
    db.commit()
    with pytest.raises(InsufficientStock):
        post_invoice_atomic(db, UUID(invoice["id"]), ids["owner"])
    db.rollback()
    # nothing changed: still Draft, stock intact, no movement, no AR entry
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).json()["posting_status"] == "Draft"
    assert str(_stock(db, ids)) == "1.000"
    assert db.execute(text("SELECT count(*) FROM inventory.stock_movement")).scalar_one() == 0
    assert ar.customer_balance(db, ids["customer"]) == Decimal("0.00")


def test_post_rejects_non_draft_invoice(posting_env):
    client, db, ids, auth, invoice, payload = posting_env
    post_invoice_atomic(db, UUID(invoice["id"]), ids["owner"])
    db.commit()
    with pytest.raises(ValueError):
        post_invoice_atomic(db, UUID(invoice["id"]), ids["owner"])


def test_posting_http_endpoint_stays_disabled(posting_env):
    client, db, ids, auth, invoice, payload = posting_env
    response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    assert response.status_code == 409
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).json()["posting_status"] == "Draft"
