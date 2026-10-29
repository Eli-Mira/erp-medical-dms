"""Shared pytest fixtures for the posting tests.

`posting_env` lives here (rather than in tests/test_posting.py) so that any
test module in this directory can request it without duplicating setup.
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


@pytest.fixture(autouse=True)
def isolated_financial_database(request):
    if request.module.__name__.split(".")[-1] not in {
        "test_posting",
        "test_posting_flag",
        "test_collections",
        "test_invoice_reversal",
        "test_invoice_cycle",
        "test_invoice_cycle_controls",
        "test_invoice_cycle_safety",
        "test_invoice_list",
        "test_master_api",
        "test_master_data_b",
        "test_transfers",
        "test_returns",
        "test_cost_quarantine",
        "test_verified_cost_controls",
        "test_cost_quarantine_migration",
        "test_marketing",
        "test_audit_read",
        "test_permission_isolation",
        "test_reason_codes",
        "test_search",
        "test_private_accounts",
        "test_inventory_batches",
        "test_inventory_cover",
        "test_sales_targets",
        "test_sales_report",
                "test_settings_policy",
                "test_management_summary",
                "test_i1_reports",
                "test_visits",
            }:
                return
    assert os.environ.get("APP_ENV") == "test", "Use scripts/verify_invoice_cycle.py"
    assert engine.url.database.startswith("dms_cycle_test_"), (
        "Refusing non-disposable financial tests"
    )
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT current_database()")).scalar_one()
            == engine.url.database
        )


@pytest.fixture
def posting_env():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids = {
        name: uuid4()
        for name in ("owner", "branch", "territory", "customer", "warehouse", "product")
    }
    db.execute(
        text(
            "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) VALUES (:id,:u,'unused','owner',true)"
        ),
        {"id": ids["owner"], "u": f"post_test_{ids['owner'].hex}"},
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
    db.execute(
        text(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:code,'Test customer',:b,:t)"
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
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:b,:code,'Test warehouse')"
        ),
        {"id": ids["warehouse"], "b": ids["branch"], "code": ids["warehouse"].hex[:20]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'Test product',114,'14.00')"
        ),
        {"id": ids["product"], "sku": ids["product"].hex},
    )
    # opening stock of 10 units, no batch
    # (no stock UPDATE here; test that needs depleted stock updates it in-place)
    db.execute(
        text(
            "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) VALUES (:w,:p,10)"
        ),
        {"w": ids["warehouse"], "p": ids["product"]},
    )
    db.commit()

    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        sid = uuid4()
        db.execute(
            text(
                "INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:sid,:uid,now() + interval '1 hour')"
            ),
            {"sid": sid, "uid": ids["owner"]},
        )
        db.commit()
        auth = {"Authorization": f"Bearer {sid}"}
        payload = {
            "invoice_no": f"P-{uuid4().hex[:20]}",
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
        invoice = client.post("/invoices", json=payload, headers=auth).json()
        yield client, db, ids, auth, invoice, payload
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()
