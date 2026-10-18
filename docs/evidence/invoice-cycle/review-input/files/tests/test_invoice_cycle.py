"""Full Invoice → Stock → AR → Collection → Payment Void → Invoice Reversal cycle.

Savepoint regressions; independent committed races live in test_invoice_cycle_safety.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.finance import ar
from app.main import app


@pytest.fixture
def cycle_env():
    """Fresh DB with all fixtures for full cycle test."""
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
            {"id": uid, "u": f"cycle_{uid.hex}", "role": role, "owner": owner},
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
            {"id": rid, "code": f"CYC_{cat}_{rid.hex[:10]}", "cat": cat},
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

        yield client, db, ids, headers
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()


def test_full_cycle_invoice_post_collect_void_reverse(cycle_env):
    """Full cycle: Post → Partial Collect → Full Collect → Void Receipt → Reverse Invoice."""
    client, db, ids, headers = cycle_env
    import app.config as cfg
    import app.finance.payment_router as pr
    import app.sales.router as sr

    orig_cfg = cfg.POSTING_ENABLED
    orig_sr = sr.POSTING_ENABLED
    orig_pr = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    sr.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # 1. Create draft invoice (3 units = 342.00)
        payload = {
            "invoice_no": f"CYC-{uuid4().hex[:20]}",
            "branch_id": str(ids["branch"]),
            "warehouse_id": str(ids["warehouse"]),
            "customer_id": str(ids["customer"]),
            "invoice_date": datetime.now(UTC).astimezone().date().isoformat(),
            "lines": [
                {
                    "product_id": str(ids["product"]),
                    "quantity": "3",
                    "discount_pct": "0",
                }
            ],
        }
        inv = client.post("/invoices", json=payload, headers=headers()).json()
        assert inv["grand_total"] == "342.00"
        assert inv["posting_status"] == "Draft"

        # 2. POST invoice
        post = client.post(f"/invoices/{inv['id']}/post", headers=headers())
        assert post.status_code == 200, post.text
        posted = post.json()
        assert posted["posting_status"] == "Posted"
        assert posted["grand_total"] == "342.00"
        assert posted["version"] == 2
        # Stock: 10 -> 7
        stock_before = db.execute(
            text(
                "SELECT quantity FROM inventory.stock_balance "
                "WHERE warehouse_id=:w AND product_id=:p"
            ),
            {"w": ids["warehouse"], "p": ids["product"]},
        ).scalar_one()
        assert str(stock_before) == "7.000"
        # AR: 342 debit
        assert ar.customer_balance(db, ids["customer"]) == Decimal("342.00")

        # 3. Partial collection: 100.00
        coll1 = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "CYC-R1",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "100.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        assert coll1.status_code == 201
        assert ar.customer_balance(db, ids["customer"]) == Decimal("242.00")

        # 4. Full collection: remaining 242.00
        coll2 = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "CYC-R2",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "242.00",
                "method": "transfer",
            },
            headers=headers("finance_user"),
        )
        assert coll2.status_code == 201
        assert ar.customer_balance(db, ids["customer"]) == Decimal("0.00")

        # 5. Void first receipt (100.00 adjustment debit -> balance back to 100)
        void1 = client.post(
            f"/collections/{coll1.json()['id']}/void",
            json={"version": 1, "reason_id": str(ids["reason_void"])},
            headers=headers("finance_user"),
        )
        assert void1.status_code == 200
        assert ar.customer_balance(db, ids["customer"]) == Decimal("100.00")

        # 6. Void second receipt (balance back to 342)
        void2 = client.post(
            f"/collections/{coll2.json()['id']}/void",
            json={"version": 1, "reason_id": str(ids["reason_void"])},
            headers=headers("finance_user"),
        )
        assert void2.status_code == 200
        assert ar.customer_balance(db, ids["customer"]) == Decimal("342.00")

        # 7. Reverse invoice (stock back to 10, AR credit_note 342 -> balance 0)
        rev = client.post(
            f"/invoices/{posted['id']}/reverse",
            json={
                "version": posted["version"],
                "reason_id": str(ids["reason_reversal"]),
            },
            headers=headers("owner"),
        )
        assert rev.status_code == 200, rev.text
        reversed_inv = rev.json()
        assert reversed_inv["posting_status"] == "Voided"
        assert reversed_inv["void_reason_id"] == str(ids["reason_reversal"])

        stock_after = db.execute(
            text(
                "SELECT quantity FROM inventory.stock_balance "
                "WHERE warehouse_id=:w AND product_id=:p"
            ),
            {"w": ids["warehouse"], "p": ids["product"]},
        ).scalar_one()
        assert str(stock_after) == "10.000"
        assert ar.customer_balance(db, ids["customer"]) == Decimal("0.00")

        # 8. Verify original rows retained
        # Invoice header
        inv_row = db.execute(
            text(
                "SELECT grand_total, posting_status, posted_at, voided_at FROM sales.sales_invoice WHERE id=:i"
            ),
            {"i": UUID(posted["id"])},
        ).one()
        assert str(inv_row.grand_total) == "342.00"
        assert inv_row.posting_status == "Voided"
        assert inv_row.posted_at is not None  # posted_at retained
        assert inv_row.voided_at is not None

        # Original invoice lines retained
        lines = db.execute(
            text(
                "SELECT line_no, quantity, unit_price, vat_rate, vat_amount FROM sales.sales_invoice_line "
                "WHERE invoice_id=:i ORDER BY line_no"
            ),
            {"i": UUID(posted["id"])},
        ).fetchall()
        assert len(lines) == 1
        assert str(lines[0].quantity) == "3.000"
        assert str(lines[0].vat_rate) == "14.00"

        # Stock movements: sale (-3) + return (+3)
        movements = db.execute(
            text(
                "SELECT movement_type, quantity FROM inventory.stock_movement WHERE source_id=:i "
                "ORDER BY created_at"
            ),
            {"i": UUID(posted["id"])},
        ).fetchall()
        assert len(movements) == 2
        assert (
            movements[0].movement_type == "sale"
            and str(movements[0].quantity) == "-3.000"
        )
        assert (
            movements[1].movement_type == "return"
            and str(movements[1].quantity) == "3.000"
        )

        # AR entries: invoice (342 debit) + payment x2 (100+242 credit) + adjustment x2 (100+242 debit) + credit_note (342 credit)
        ar_entries = db.execute(
            text(
                "SELECT entry_type, debit, credit FROM finance.ar_entry WHERE invoice_id=:i "
                "ORDER BY created_at"
            ),
            {"i": UUID(posted["id"])},
        ).fetchall()
        assert len(ar_entries) == 6
        types = [e.entry_type for e in ar_entries]
        assert types == [
            "invoice",
            "payment",
            "payment",
            "adjustment",
            "adjustment",
            "credit_note",
        ]
        # Verify amounts
        assert (
            str(ar_entries[0].debit) == "342.00" and str(ar_entries[0].credit) == "0.00"
        )
        assert (
            str(ar_entries[1].credit) == "100.00" and str(ar_entries[1].debit) == "0.00"
        )
        assert (
            str(ar_entries[2].credit) == "242.00" and str(ar_entries[2].debit) == "0.00"
        )
        assert (
            str(ar_entries[3].debit) == "100.00" and str(ar_entries[3].credit) == "0.00"
        )
        assert (
            str(ar_entries[4].debit) == "242.00" and str(ar_entries[4].credit) == "0.00"
        )
        assert (
            str(ar_entries[5].credit) == "342.00" and str(ar_entries[5].debit) == "0.00"
        )

        # 9. Repeat operations rejected
        # Re-reverse
        rev2 = client.post(
            f"/invoices/{posted['id']}/reverse",
            json={
                "version": reversed_inv["version"],
                "reason_id": str(ids["reason_reversal"]),
            },
            headers=headers("owner"),
        )
        assert rev2.status_code == 409
        # Re-post
        post2 = client.post(f"/invoices/{posted['id']}/post", headers=headers())
        assert post2.status_code == 409
        # New collection on voided
        coll3 = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": reversed_inv["version"],
                "receipt_no": "CYC-R3",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "10.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        assert coll3.status_code == 409
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        sr.POSTING_ENABLED = orig_sr
        pr.POSTING_ENABLED = orig_pr


def test_sequential_collection_rejects_overpayment(cycle_env):
    """A second sequential receipt cannot exceed the remaining balance."""
    client, db, ids, headers = cycle_env
    import app.config as cfg
    import app.finance.payment_router as pr
    import app.sales.router as sr

    orig_cfg = cfg.POSTING_ENABLED
    orig_sr = sr.POSTING_ENABLED
    orig_pr = pr.POSTING_ENABLED
    cfg.POSTING_ENABLED = True
    sr.POSTING_ENABLED = True
    pr.POSTING_ENABLED = True
    try:
        # Create and post invoice
        payload = {
            "invoice_no": f"CONC-{uuid4().hex[:20]}",
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
        inv = client.post("/invoices", json=payload, headers=headers()).json()
        post = client.post(f"/invoices/{inv['id']}/post", headers=headers())
        posted = post.json()

        # Collect 150 via API first time -> succeeds
        resp1 = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "CONC-R1",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "150.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        assert resp1.status_code == 201
        assert ar.customer_balance(db, ids["customer"]) == Decimal("78.00")

        # Try to collect 150 again -> overpayment rejection
        resp2 = client.post(
            "/collections",
            json={
                "invoice_id": posted["id"],
                "invoice_version": posted["version"],
                "receipt_no": "CONC-R2",
                "receipt_date": datetime.now(UTC).astimezone().date().isoformat(),
                "amount": "150.00",
                "method": "cash",
            },
            headers=headers("finance_user"),
        )
        assert resp2.status_code == 409, resp2.text
        # Balance unchanged
        assert ar.customer_balance(db, ids["customer"]) == Decimal("78.00")
    finally:
        cfg.POSTING_ENABLED = orig_cfg
        sr.POSTING_ENABLED = orig_sr
        pr.POSTING_ENABLED = orig_pr


def test_flag_off_blocks_posting(cycle_env):
    """All four mutation types have independent coverage in cycle_safety."""
    client, _db, ids, headers = cycle_env
    import app.config
    import app.finance.payment_router as pr
    import app.sales.router as sr

    orig_app = app.config.POSTING_ENABLED
    orig_sr = sr.POSTING_ENABLED
    orig_pr = pr.POSTING_ENABLED
    app.config.POSTING_ENABLED = False
    sr.POSTING_ENABLED = False
    pr.POSTING_ENABLED = False
    try:
        payload = {
            "invoice_no": f"OFF-{uuid4().hex[:20]}",
            "branch_id": str(ids["branch"]),
            "warehouse_id": str(ids["warehouse"]),
            "customer_id": str(ids["customer"]),
            "invoice_date": datetime.now(UTC).astimezone().date().isoformat(),
            "lines": [
                {
                    "product_id": str(ids["product"]),
                    "quantity": "1",
                    "discount_pct": "0",
                }
            ],
        }
        inv = client.post("/invoices", json=payload, headers=headers()).json()

        # Post
        resp = client.post(f"/invoices/{inv['id']}/post", headers=headers())
        assert resp.status_code == 409

    finally:
        app.config.POSTING_ENABLED = orig_app
        sr.POSTING_ENABLED = orig_sr
        pr.POSTING_ENABLED = orig_pr
