import pytest
from decimal import Decimal
from sqlalchemy import text

from app import config as app_config  # adjust import path as needed
from test_invoice_api import invoice_env  # noqa: F401


def _headers_for_role(db, role: str) -> dict:
    from uuid import uuid4

    uid = uuid4()
    sid = uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user "
            "(id, username, password_hash, role, is_owner, is_active, created_at, updated_at) "
            "VALUES (:uid, :u, 'x', :r, :own, true, now(), now())"
        ),
        {"uid": uid, "u": f"rc212_{role}_{uid.hex[:8]}", "r": role, "own": role == "owner"},
    )
    db.execute(
        text(
            "INSERT INTO platform.platform_session (id, user_id, expires_at) "
            "VALUES (:sid, :uid, now() + interval '1 hour')"
        ),
        {"sid": sid, "uid": uid},
    )
    db.commit()
    return {"Authorization": f"Bearer {sid}"}

def get_stock(db, warehouse_id, product_id):
    result = db.execute(
        text(
            "SELECT COALESCE(SUM(quantity), 0) FROM inventory.stock_balance "
            "WHERE warehouse_id = :wid AND product_id = :pid"
        ),
        {"wid": warehouse_id, "pid": product_id},
    ).scalar_one()
    return Decimal(result)


def get_ar_balance(db, customer_id):
    result = db.execute(
        text(
            "SELECT COALESCE(SUM(debit) - SUM(credit), 0) FROM finance.ar_entry "
            "WHERE customer_id = :cid"
        ),
        {"cid": customer_id},
    ).scalar_one()
    return Decimal(result)


def get_return_status(db, return_id):
    result = db.execute(
        text("SELECT status FROM sales.sales_return WHERE id = :rid"),
        {"rid": return_id},
    ).scalar_one()
    return result


@pytest.fixture
def create_return(client, ids, headers):
    def _create(qty):
        payload = {
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "quantity": qty,
            "return_date": "2026-11-21",
        }
        resp = client.post(
            "/returns",
            json=payload,
            headers=headers("owner"),
        )
        assert resp.status_code == 201
        return resp.json()["id"]
    return _create


def test_return_settle_blocked_when_posting_disabled(invoice_env, monkeypatch):
    client, db, ids, _, headers = invoice_env
    # create quarantined return
    payload = {
        "customer_id": str(ids["customer"]),
        "product_id": str(ids["product"]),
        "warehouse_id": str(ids["warehouse"]),
        "quantity": "3.000",
        "return_date": "2026-11-21",
    }
    resp = client.post("/returns", json=payload, headers=headers("owner"))
    assert resp.status_code == 201
    rid = resp.json()["id"]

    # disable posting
    monkeypatch.setattr(app_config, "POSTING_ENABLED", False)

    settle_resp = client.post(
        f"/returns/{rid}/settle",
        json={"decision": "approved_restock"},
        headers=headers("owner"),
    )
    assert settle_resp.status_code == 409
    assert get_return_status(db, rid) == "quarantined"


def test_return_settle_negative_rbac_controls(invoice_env, monkeypatch):
    client, db, ids, _, headers = invoice_env
    # enable posting
    monkeypatch.setattr(app_config, "POSTING_ENABLED", True)

    # create quarantined return
    payload = {
        "customer_id": str(ids["customer"]),
        "product_id": str(ids["product"]),
        "warehouse_id": str(ids["warehouse"]),
        "quantity": "1.000",
        "return_date": "2026-11-21",
    }
    resp = client.post("/returns", json=payload, headers=headers("owner"))
    assert resp.status_code == 201
    rid = resp.json()["id"]

    for role in ("warehouse_staff", "sales_manager", "medical_rep"):
        settle_resp = client.post(
            f"/returns/{rid}/settle",
            json={"decision": "approved_restock"},
            headers=_headers_for_role(db, role),
        )
        assert settle_resp.status_code == 403
        assert get_return_status(db, rid) == "quarantined"


def test_return_approved_restock_conserves_stock_credits_ar_and_reverses_14pct_vat(
    invoice_env, monkeypatch
):
    client, db, ids, _, headers = invoice_env
    monkeypatch.setattr(app_config, "POSTING_ENABLED", True)

    # update product pricing
    db.execute(
        text(
            "UPDATE master_data.master_product SET base_price = :price, vat_rate = :vat "
            "WHERE id = :pid"
        ),
        {"price": Decimal("114.00"), "vat": Decimal("14.00"), "pid": ids["product"]},
    )
    # seed opening AR debit
    db.execute(
        text(
            "INSERT INTO finance.ar_entry (customer_id, entry_type, entry_date, debit, credit, note, created_by) "
            "VALUES (:cid, 'opening', '2026-11-01', 1000.00, 0, 'opening', :uid)"
        ),
        {"cid": ids["customer"], "uid": ids["owner"]},
    )
    db.commit()

    stock_before = get_stock(db, ids["warehouse"], ids["product"])
    ar_before = get_ar_balance(db, ids["customer"])
    assert ar_before == Decimal("1000.00")

    # create quarantined return
    payload = {
        "customer_id": str(ids["customer"]),
        "product_id": str(ids["product"]),
        "warehouse_id": str(ids["warehouse"]),
        "quantity": "2.000",
        "return_date": "2026-11-21",
    }
    resp = client.post("/returns", json=payload, headers=headers("owner"))
    assert resp.status_code == 201
    rid = resp.json()["id"]
    assert get_return_status(db, rid) == "quarantined"
    assert get_stock(db, ids["warehouse"], ids["product"]) == stock_before
    assert get_ar_balance(db, ids["customer"]) == ar_before

    # settle approved_restock with credit note
    settle_body = {
        "decision": "approved_restock",
        "issue_credit_note": True,
    }
    settle_resp = client.post(
        f"/returns/{rid}/settle",
        json=settle_body,
        headers=_headers_for_role(db, "finance"),
    )
    assert settle_resp.status_code == 200
    data = settle_resp.json()
    assert data["status"] == "approved_restock"
    assert data["net_credit"] == "200.00"
    assert data["vat_reversal"] == "28.00"
    assert data["gross_credit"] == "228.00"
    assert data["restock_movement_id"] is not None
    assert data["credit_note_entry_id"] is not None

    # verify stock and AR changes
    stock_after = get_stock(db, ids["warehouse"], ids["product"])
    ar_after = get_ar_balance(db, ids["customer"])
    assert stock_after - stock_before == Decimal("2.000")
    assert ar_before - ar_after == Decimal("228.00")
    assert ar_after == Decimal("772.00")

    # double settlement should be blocked
    second_resp = client.post(
        f"/returns/{rid}/settle",
        json=settle_body,
        headers=_headers_for_role(db, "finance"),
    )
    assert second_resp.status_code == 409
    # ensure no further changes
    assert get_stock(db, ids["warehouse"], ids["product"]) == stock_after
    assert get_ar_balance(db, ids["customer"]) == ar_after


def test_full_invoice_sell_then_return_zeros_ar_and_restores_stock(
    invoice_env, monkeypatch
):
    client, db, ids, inv_payload, headers = invoice_env
    monkeypatch.setattr(app_config, "POSTING_ENABLED", True)

    # Seed 10.000 batched opening stock
    db.execute(
        text(
            "INSERT INTO inventory.stock_balance (warehouse_id, product_id, batch_id, quantity) "
            "VALUES (:wid, :pid, :bid, 10.000)"
        ),
        {"wid": ids["warehouse"], "pid": ids["product"], "bid": ids["batch"]},
    )
    db.commit()

    # Create and post invoice (qty=2, VAT-inclusive base_price=114.00, vat_rate=14.00 -> grand_total=228.00)
    inv_resp = client.post("/invoices", json=inv_payload, headers=headers("owner"))
    assert inv_resp.status_code == 201, inv_resp.text
    inv = inv_resp.json()
    assert inv["grand_total"] == "228.00"
    assert inv["vat_amount"] == "28.00"
    assert inv["total_net"] == "200.00"

    post_resp = client.post(f"/invoices/{inv['id']}/post", headers=headers("owner"))
    assert post_resp.status_code == 200, post_resp.text
    assert get_ar_balance(db, ids["customer"]) == Decimal("228.00")
    assert get_stock(db, ids["warehouse"], ids["product"]) == Decimal("8.000")

    # Full return linked to the posted invoice and settle as approved_restock
    ret_resp = client.post(
        "/returns",
        json={
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "batch_id": str(ids["batch"]),
            "invoice_id": inv["id"],
            "quantity": "2.000",
            "return_date": "2026-11-21",
        },
        headers=headers("owner"),
    )
    assert ret_resp.status_code == 201, ret_resp.text
    rid = ret_resp.json()["id"]

    settle_resp = client.post(
        f"/returns/{rid}/settle",
        json={"decision": "approved_restock", "issue_credit_note": True},
        headers=headers("owner"),
    )
    assert settle_resp.status_code == 200, settle_resp.text
    s = settle_resp.json()
    assert s["gross_credit"] == "228.00"
    assert s["vat_reversal"] == "28.00"
    assert s["net_credit"] == "200.00"

    # Exact round-trip conservation: AR balance == 0.00, stock == 10.000
    assert get_ar_balance(db, ids["customer"]) == Decimal("0.00")
    assert get_stock(db, ids["warehouse"], ids["product"]) == Decimal("10.000")


def test_return_scrapped_adds_zero_saleable_stock_and_0pct_vat_credit_note(
    invoice_env, monkeypatch
):
    client, db, ids, _, headers = invoice_env
    monkeypatch.setattr(app_config, "POSTING_ENABLED", True)

    # seed opening AR debit
    db.execute(
        text(
            "INSERT INTO finance.ar_entry (customer_id, entry_type, entry_date, debit, credit, note, created_by) "
            "VALUES (:cid, 'opening', '2026-11-01', 1000.00, 0, 'opening', :uid)"
        ),
        {"cid": ids["customer"], "uid": ids["owner"]},
    )
    db.commit()

    stock_before = get_stock(db, ids["warehouse"], ids["product"])
    ar_before = get_ar_balance(db, ids["customer"])

    # create quarantined return
    payload = {
        "customer_id": str(ids["customer"]),
        "product_id": str(ids["product"]),
        "warehouse_id": str(ids["warehouse"]),
        "quantity": "5.000",
        "return_date": "2026-11-21",
    }
    resp = client.post("/returns", json=payload, headers=headers("owner"))
    assert resp.status_code == 201
    rid = resp.json()["id"]
    assert get_return_status(db, rid) == "quarantined"

    # settle as scrapped with credit note
    settle_body = {
        "decision": "scrapped",
        "unit_price": "40.00",
        "vat_rate": "0.00",
        "issue_credit_note": True,
    }
    settle_resp = client.post(
        f"/returns/{rid}/settle",
        json=settle_body,
        headers=headers("owner"),
    )
    assert settle_resp.status_code == 200
    data = settle_resp.json()
    assert data["status"] == "scrapped"
    assert data["restock_movement_id"] is None
    assert data["net_credit"] == "200.00"
    assert data["vat_reversal"] == "0.00"
    assert data["gross_credit"] == "200.00"

    # verify stock unchanged and AR decreased
    stock_after = get_stock(db, ids["warehouse"], ids["product"])
    ar_after = get_ar_balance(db, ids["customer"])
    assert stock_after == stock_before
    assert ar_before - ar_after == Decimal("200.00")
    assert ar_after == Decimal("800.00")

    # attempt another settlement should be blocked
    second_resp = client.post(
        f"/returns/{rid}/settle",
        json={"decision": "approved_restock"},
        headers=headers("owner"),
    )
    assert second_resp.status_code == 409
    # ensure no further changes
    assert get_stock(db, ids["warehouse"], ids["product"]) == stock_after
    assert get_ar_balance(db, ids["customer"]) == ar_after
