"""Posted invoice reversal tests: exact stock+AR compensation, append-only."""
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app
from app.finance import ar
from app.inventory import service as inventory


@pytest.fixture
def reversal_env():
    """Fresh DB connection with a posted invoice ready for reversal."""
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids = {name: uuid4() for name in (
        "owner", "finance_user", "branch", "territory", "customer",
        "warehouse", "product", "reason_void", "reason_reversal"
    )}
    for role, uid, owner in [
        ("owner", ids["owner"], True),
        ("finance", ids["finance_user"], False),
    ]:
        db.execute(text(
            "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) "
            "VALUES (:id,:u,'unused',:role,:owner)"
        ), {"id": uid, "u": f"rev_test_{uid.hex}", "role": role, "owner": owner})
    db.execute(text(
        "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'Test branch')"
    ), {"id": ids["branch"], "code": ids["branch"].hex[:20]})
    db.execute(text(
        "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,'Test territory')"
    ), {"id": ids["territory"], "code": ids["territory"].hex[:20]})
    # Assign finance_user to territory for customer access
    db.execute(text(
        "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:uid,:tid)"
    ), {"uid": ids["finance_user"], "tid": ids["territory"]})
    db.execute(text(
        "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
        "VALUES (:id,:code,'Test customer',:b,:t)"
    ), {"id": ids["customer"], "code": ids["customer"].hex[:30],
        "b": ids["branch"], "t": ids["territory"]})
    db.execute(text(
        "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
        "VALUES (:id,:b,:code,'Test warehouse')"
    ), {"id": ids["warehouse"], "b": ids["branch"], "code": ids["warehouse"].hex[:20]})
    db.execute(text(
        "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) "
        "VALUES (:id,:sku,'Test product',114,'14.00')"
    ), {"id": ids["product"], "sku": ids["product"].hex})
    db.execute(text(
        "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) VALUES (:w,:p,10)"
    ), {"w": ids["warehouse"], "p": ids["product"]})
    # Reasons: void and reversal
    for cat, rid in [("void", ids["reason_void"]), ("reversal", ids["reason_reversal"])]:
        db.execute(text(
            "INSERT INTO audit.reason_code(id,code,category) VALUES (:id,:code,:cat)"
        ), {"id": rid, "code": f"REV_{cat}_{rid.hex[:10]}", "cat": cat})
    db.commit()

    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        def headers(user="owner"):
            sid = uuid4()
            db.execute(text(
                "INSERT INTO platform.platform_session(id,user_id,expires_at) "
                "VALUES (:sid,:uid,now() + interval '1 hour')"
            ), {"sid": sid, "uid": ids[user]})
            db.commit()
            return {"Authorization": f"Bearer {sid}"}

        # Create draft then post via service to get a Posted invoice
        payload = {
            "invoice_no": f"R-{uuid4().hex[:20]}", "branch_id": str(ids["branch"]),
            "warehouse_id": str(ids["warehouse"]), "customer_id": str(ids["customer"]),
            "invoice_date": date.today().isoformat(),
            "lines": [{"product_id": str(ids["product"]), "quantity": "2", "discount_pct": "0"}],
        }
        invoice = client.post("/invoices", json=payload, headers=headers()).json()
        # Post it (enable flag for this test)
        import app.config as cfg
        original = cfg.POSTING_ENABLED
        import app.sales.router as invoice_router
        orig_router = invoice_router.POSTING_ENABLED
        cfg.POSTING_ENABLED = True
        invoice_router.POSTING_ENABLED = True
        try:
            post_resp = client.post(f"/invoices/{invoice['id']}/post", headers=headers())
            assert post_resp.status_code == 200, post_resp.text
            posted = post_resp.json()
            yield client, db, ids, headers, posted
        finally:
            cfg.POSTING_ENABLED = original
            invoice_router.POSTING_ENABLED = orig_router
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()


def _stock(db, ids):
    return db.execute(text(
        "SELECT quantity FROM inventory.stock_balance "
        "WHERE warehouse_id=:w AND product_id=:p AND batch_id IS NULL"
    ), {"w": ids["warehouse"], "p": ids["product"]}).scalar_one()


def test_reverse_invoice_atomic_restores_stock_and_ar(reversal_env):
    from app.sales.service import reverse_invoice_atomic
    client, db, ids, headers, posted = reversal_env
    assert posted["posting_status"] == "Posted"
    assert posted["grand_total"] == "228.00"
    # Before: stock 8 (10 - 2), AR balance 228
    assert str(_stock(db, ids)) == "8.000"
    assert ar.customer_balance(db, ids["customer"]) == Decimal("228.00")

    reversed_inv = reverse_invoice_atomic(db, UUID(posted["id"]), ids["owner"], ids["reason_reversal"])
    db.commit()

    assert reversed_inv["posting_status"] == "Voided"
    assert str(reversed_inv["voided_by"]) == str(ids["owner"])
    assert str(reversed_inv["void_reason_id"]) == str(ids["reason_reversal"])
    assert str(_stock(db, ids)) == "10.000"  # back to original
    # Return movement recorded
    movement = db.execute(text(
        "SELECT movement_type, quantity FROM inventory.stock_movement "
        "WHERE source_id=:i AND movement_type='return'"),
        {"i": UUID(posted["id"])}).one()
    assert movement.movement_type == "return"
    assert str(movement.quantity) == "2.000"
    # AR credit_note entry
    assert ar.customer_balance(db, ids["customer"]) == Decimal("0.00")
    entry = db.execute(text(
        "SELECT entry_type, debit, credit FROM finance.ar_entry WHERE invoice_id=:i "
        "AND entry_type='credit_note'"),
        {"i": UUID(posted["id"])}).one()
    assert (entry.entry_type, str(entry.debit), str(entry.credit)) == ("credit_note", "0.00", "228.00")
    # Original invoice row retained
    orig = db.execute(text(
        "SELECT grand_total, posting_status FROM sales.sales_invoice WHERE id=:i"),
        {"i": UUID(posted["id"])}).one()
    assert str(orig.grand_total) == "228.00"
    assert orig.posting_status == "Voided"


def test_reversal_requires_active_reversal_reason(reversal_env):
    import app.config as cfg
    import app.finance.payment_router as pr
    client, db, ids, headers, posted = reversal_env
    orig_cfg = cfg.POSTING_ENABLED
    orig_pr = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # Make reason inactive -> 422
        db.execute(text("UPDATE audit.reason_code SET is_active=false WHERE id=:id"),
                   {"id": ids["reason_reversal"]})
        db.commit()
        resp = client.post(f"/invoices/{posted['id']}/reverse", json={
            "version": posted["version"], "reason_id": str(ids["reason_reversal"])
        }, headers=headers("owner"))
        assert resp.status_code == 422
        assert "reason" in resp.json()["detail"].lower()
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_pr


def test_reversal_refused_when_active_receipts_exist(reversal_env):
    from app.sales.service import reverse_invoice_atomic
    from app.finance import payments
    client, db, ids, headers, posted = reversal_env
    # Create an Active receipt
    payments.create_receipt(db,
        invoice_id=UUID(posted["id"]), branch_id=ids["branch"],
        customer_id=ids["customer"], receipt_no="RCT-001",
        receipt_date=date.today(), amount=Decimal("100.00"),
        method="cash", note=None, actor_id=ids["owner"])
    db.commit()

    with pytest.raises(ValueError, match="Active receipts exist"):
        reverse_invoice_atomic(db, UUID(posted["id"]), ids["owner"], ids["reason_reversal"])


def test_reverse_endpoint_owner_and_finance(reversal_env):
    client, db, ids, headers, posted = reversal_env
    import app.config as cfg
    import app.sales.router as sr
    orig_cfg = cfg.POSTING_ENABLED
    orig_sr = sr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    sr.POSTING_ENABLED = True
    try:
        # Owner: success
        resp = client.post(f"/invoices/{posted['id']}/reverse",
            json={"version": posted["version"], "reason_id": str(ids["reason_reversal"])},
            headers=headers("owner"))
        assert resp.status_code == 200, resp.text
        assert resp.json()["posting_status"] == "Voided"
        assert resp.json()["void_reason_id"] == str(ids["reason_reversal"])
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        sr.POSTING_ENABLED = orig_sr

    # Finance role test
    payload = {
        "invoice_no": f"R2-{uuid4().hex[:20]}", "branch_id": str(ids["branch"]),
        "warehouse_id": str(ids["warehouse"]), "customer_id": str(ids["customer"]),
        "invoice_date": date.today().isoformat(),
        "lines": [{"product_id": str(ids["product"]), "quantity": "1", "discount_pct": "0"}],
    }
    invoice = client.post("/invoices", json=payload, headers=headers("finance_user")).json()
    cfg.POSTING_ENABLED = True
    sr.POSTING_ENABLED = True
    try:
        post_resp = client.post(f"/invoices/{invoice['id']}/post", headers=headers("finance_user"))
        assert post_resp.status_code == 200
        posted2 = post_resp.json()
        resp = client.post(f"/invoices/{posted2['id']}/reverse",
            json={"version": posted2["version"], "reason_id": str(ids["reason_reversal"])},
            headers=headers("finance_user"))
        assert resp.status_code == 200, resp.text
        assert resp.json()["posting_status"] == "Voided"
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        sr.POSTING_ENABLED = orig_sr


def test_reverse_endpoint_medical_rep_denied(reversal_env):
    client, db, ids, headers, posted = reversal_env
    import app.config as cfg
    import app.sales.router as sr
    cfg.POSTING_ENABLED = True
    sr.POSTING_ENABLED = True
    try:
        rep = uuid4()
        db.execute(text(
            "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) "
            "VALUES (:id,:u,'unused','medical_rep',false)"),
            {"id": rep, "u": f"rep_{rep.hex}"})
        db.commit()
        sid = uuid4()
        db.execute(text(
            "INSERT INTO platform.platform_session(id,user_id,expires_at) "
            "VALUES (:sid,:uid,now() + interval '1 hour')"),
            {"sid": sid, "uid": rep})
        db.commit()
        rep_auth = {"Authorization": f"Bearer {sid}"}
        resp = client.post(f"/invoices/{posted['id']}/reverse",
            json={"version": posted["version"], "reason_id": str(ids["reason_reversal"])},
            headers=rep_auth)
        assert resp.status_code == 403
    finally:
        cfg.POSTING_ENABLED = orig_cfg if 'orig_cfg' in locals() else False
        sr.POSTING_ENABLED = orig_sr if 'orig_sr' in locals() else False


def test_reversal_preserves_original_vat_and_line_snapshots(reversal_env):
    from app.sales.service import reverse_invoice_atomic
    client, db, ids, headers, posted = reversal_env
    # Add a mixed VAT line
    mixed_id = uuid4()
    db.execute(text(
        "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) "
        "VALUES (:id,:sku,'Mixed VAT',100,'5.00')"),
        {"id": mixed_id, "sku": mixed_id.hex})
    db.execute(text(
        "INSERT INTO sales.sales_invoice_line (id,invoice_id,line_no,product_id,batch_id,"
        "quantity,unit_price,discount_pct,net_price,line_total,vat_rate,vat_amount) "
        "VALUES (:id,:inv,2,:p,NULL,'1',100,'0',100,100,'5.00','5.00')"),
        {"id": uuid4(), "inv": UUID(posted["id"]), "p": mixed_id})
    # Update header totals
    db.execute(text(
            "UPDATE sales.sales_invoice SET grand_total='333.00', vat_amount='33.00', "
            "total_net='300.00', total_before_discount='333.00', total_discount='0.00' "
            "WHERE id=:i"),
            {"i": UUID(posted["id"])})
    db.commit()

    reversed_inv = reverse_invoice_atomic(db, UUID(posted["id"]), ids["owner"], ids["reason_reversal"])
    db.commit()

    # Original line snapshots retained
    lines = db.execute(text(
        "SELECT line_no, unit_price, vat_rate, vat_amount FROM sales.sales_invoice_line "
        "WHERE invoice_id=:i ORDER BY line_no"),
        {"i": UUID(posted["id"])}).fetchall()
    assert len(lines) == 2
    assert [str(r.vat_rate) for r in lines] == ["14.00", "5.00"]
    assert reversed_inv["posting_status"] == "Voided"
    assert str(reversed_inv["grand_total"]) == "333.00"