"""Payment receipt (collections) tests: create, void, list, overpayment guards."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.finance import ar, payments
from app.main import app


@pytest.fixture
def collections_env():
    """Fresh DB with a Posted invoice ready for collections."""
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids = {
        name: uuid4()
        for name in (
            "owner",
            "finance_user",
            "branch",
            "territory",
            "customer",
            "warehouse",
            "product",
            "reason_void",
            "reason_reversal",
        )
    }
    for role, uid, owner in [
        ("owner", ids["owner"], True),
        ("finance", ids["finance_user"], False),
    ]:
        db.execute(
            text(
                "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) "
                "VALUES (:id,:u,'unused',:role,:owner)"
            ),
            {"id": uid, "u": f"col_test_{uid.hex}", "role": role, "owner": owner},
        )
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'Test branch')"
        ),
        {"id": ids["branch"], "code": ids["branch"].hex[:20]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,'Test territory')"
        ),
        {"id": ids["territory"], "code": ids["territory"].hex[:20]},
    )
    # Assign finance_user to territory for customer access
    db.execute(
        text(
            "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:uid,:tid)"
        ),
        {"uid": ids["finance_user"], "tid": ids["territory"]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
            "VALUES (:id,:code,'Test customer',:b,:t)"
        ),
        {
            "id": ids["customer"],
            "code": ids["customer"].hex[:30],
            "b": ids["branch"],
            "t": ids["territory"],
        },
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:id,:b,:code,'Test warehouse')"
        ),
        {"id": ids["warehouse"], "b": ids["branch"], "code": ids["warehouse"].hex[:20]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) "
            "VALUES (:id,:sku,'Test product',114,'14.00')"
        ),
        {"id": ids["product"], "sku": ids["product"].hex},
    )
    db.execute(
        text(
            "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) VALUES (:w,:p,10)"
        ),
        {"w": ids["warehouse"], "p": ids["product"]},
    )
    for cat, rid in [
        ("void", ids["reason_void"]),
        ("reversal", ids["reason_reversal"]),
    ]:
        db.execute(
            text(
                "INSERT INTO audit.reason_code(id,code,category) VALUES (:id,:code,:cat)"
            ),
            {"id": rid, "code": f"COL_{cat}_{rid.hex[:10]}", "cat": cat},
        )
    db.commit()

    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:

        def headers(user="owner"):
            sid = uuid4()
            db.execute(
                text(
                    "INSERT INTO platform.platform_session(id,user_id,expires_at) "
                    "VALUES (:sid,:uid,now() + interval '1 hour')"
                ),
                {"sid": sid, "uid": ids[user]},
            )
            db.commit()
            return {"Authorization": f"Bearer {sid}"}

        # Create and post an invoice
        payload = {
            "invoice_no": f"C-{uuid4().hex[:20]}",
            "branch_id": str(ids["branch"]),
            "warehouse_id": str(ids["warehouse"]),
            "customer_id": str(ids["customer"]),
            "invoice_date": datetime.now(UTC).astimezone().date().isoformat(),
            "lines": [
                {
                    "product_id": str(ids["product"]),
                    "quantity": "2",
                    "discount_pct": "0",
                }
            ],
        }
        invoice = client.post("/invoices", json=payload, headers=headers()).json()
        import app.config as cfg
        import app.sales.router as invoice_router

        orig_cfg = cfg.POSTING_ENABLED
        orig_router = invoice_router.POSTING_ENABLED
        cfg.POSTING_ENABLED = True
        invoice_router.POSTING_ENABLED = True
        try:
            post_resp = client.post(
                f"/invoices/{invoice['id']}/post", headers=headers()
            )
            assert post_resp.status_code == 200, post_resp.text
            posted = post_resp.json()
        finally:
            cfg.POSTING_ENABLED = orig_cfg
            invoice_router.POSTING_ENABLED = orig_router

        yield client, db, ids, headers, posted
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()


def test_create_receipt_partial_payment(collections_env):
    client, db, ids, headers, posted = collections_env
    assert posted["grand_total"] == "228.00"

    # Enable collections gate for this test
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # Partial payment: 100
        resp = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-001",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "100.00",
                "method": "cash",
                "note": "Partial payment",
            },
            headers=headers("finance_user"),
        )
        assert resp.status_code == 201, resp.text
        receipt = resp.json()
        assert receipt["amount"] == "100.00"
        assert receipt["status"] == "Active"
        assert receipt["invoice_id"] == posted["id"]
        assert receipt["customer_id"] == posted["customer_id"]
        assert receipt["branch_id"] == posted["branch_id"]

        # AR balance reduced by payment amount
        assert ar.customer_balance(db, ids["customer"]) == Decimal("128.00")
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_create_receipt_final_payment(collections_env):
    client, db, ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # Full payment
        resp = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-FULL",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "228.00",
                "method": "transfer",
            },
            headers=headers("finance_user"),
        )
        assert resp.status_code == 201, resp.text
        assert ar.customer_balance(db, ids["customer"]) == Decimal("0.00")
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_overpayment_rejected(collections_env):
    client, db, ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # Try to overpay
        resp = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-OVER",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "300.00",  # > 228
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        assert resp.status_code == 409, resp.text
        assert "overpayment" in resp.json()["detail"].lower()

        # Balance unchanged
        assert ar.customer_balance(db, ids["customer"]) == Decimal("228.00")
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_partial_then_final_sum_rejects_overpayment(collections_env):
    client, db, ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # First partial
        client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-1",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "150.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        # Second that would exceed
        resp = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-2",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "100.00",
                "method": "cash",  # 150+100 > 228
            },
            headers=headers("finance_user"),
        )
        assert resp.status_code == 409
        # Balance: still only 150 collected
        assert ar.customer_balance(db, ids["customer"]) == Decimal("78.00")
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_receipt_number_unique_per_branch(collections_env):
    client, _db, _ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # First receipt
        resp = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-DUP",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "50.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        assert resp.status_code == 201
        # Duplicate receipt_no in same branch -> 409
        resp = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-DUP",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "50.00",
                "method": "check",
            },
            headers=headers("finance_user"),
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_receipt_requires_posted_invoice(collections_env):
    client, _db, ids, headers, _posted = collections_env
    # Create a draft invoice
    payload = {
        "invoice_no": f"D-{uuid4().hex[:20]}",
        "branch_id": str(ids["branch"]),
        "warehouse_id": str(ids["warehouse"]),
        "customer_id": str(ids["customer"]),
        "invoice_date": datetime.now(UTC).astimezone().date().isoformat(),
        "lines": [
            {"product_id": str(ids["product"]), "quantity": "1", "discount_pct": "0"}
        ],
    }
    draft = client.post("/invoices", json=payload, headers=headers()).json()
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        resp = client.post(
            "/collections",
            json={
                "invoice_id": draft["id"],
                "invoice_version": draft["version"],
                "receipt_no": "RCT-DRAFT",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "10.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        assert resp.status_code == 409
        assert "posted" in resp.json()["detail"].lower()
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_void_receipt_appends_ar_adjustment(collections_env):
    client, db, ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # Create receipt
        create = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-VOID",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "100.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        assert create.status_code == 201
        receipt = create.json()
        assert ar.customer_balance(db, ids["customer"]) == Decimal("128.00")

        # Void it
        void_resp = client.post(
            f"/collections/{receipt['id']}/void",
            json={"version": 1, "reason_id": str(ids["reason_void"])},
            headers=headers("finance_user"),
        )
        assert void_resp.status_code == 200, void_resp.text
        voided = void_resp.json()
        assert voided["status"] == "Voided"
        assert voided["void_reason_id"] == str(ids["reason_void"])

        # AR balance restored (adjustment debit added)
        assert ar.customer_balance(db, ids["customer"]) == Decimal("228.00")

        # Original receipt retained
        assert payments.fetch_receipt(db, UUID(receipt["id"]))["status"] == "Voided"
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_duplicate_void_receipt_returns_409(collections_env):
    client, _db, ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        create = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-DUPV",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "50.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        receipt = create.json()
        # First void
        client.post(
            f"/collections/{receipt['id']}/void",
            json={"version": 1, "reason_id": str(ids["reason_void"])},
            headers=headers("finance_user"),
        )
        # Second void -> 409
        resp = client.post(
            f"/collections/{receipt['id']}/void",
            json={"version": 2, "reason_id": str(ids["reason_void"])},
            headers=headers("finance_user"),
        )
        assert resp.status_code == 409
        assert "active" in resp.json()["detail"].lower()
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_list_receipts_scoped(collections_env):
    client, _db, _ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # Create a couple
        client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-L1",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "50.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-L2",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "50.00",
                "method": "check",
            },
            headers=headers("finance_user"),
        )

        resp = client.get(
            f"/collections?invoice_id={posted['id']}", headers=headers("owner")
        )
        assert resp.status_code == 200
        receipts = resp.json()
        assert len(receipts) == 2
        assert all(r["invoice_id"] == posted["id"] for r in receipts)
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_invalid_amount_rejected(collections_env):
    client, _db, _ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        for bad_amt in ["0", "-10.00", "abc", "1.001"]:
            resp = client.post(
                "/collections",
                json={
                    "invoice_id": posted["id"],
                    "invoice_version": posted["version"],
                    "receipt_no": f"RCT-BAD-{bad_amt}",
                    "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                    "amount": bad_amt,
                    "method": "cash",
                },
                headers=headers("finance_user"),
            )
            assert resp.status_code == 422, f"Should reject {bad_amt}: {resp.text}"
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router


def test_invalid_method_rejected(collections_env):
    client, _db, _ids, headers, posted = collections_env
    import app.config as cfg
    import app.finance.payment_router as pr

    orig_cfg = cfg.POSTING_ENABLED
    orig_router = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        resp = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "RCT-BADM",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "10.00",
                "method": "crypto",
            },
            headers=headers("finance_user"),
        )
        assert resp.status_code == 422
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        pr.POSTING_ENABLED = orig_router
