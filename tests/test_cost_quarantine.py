"""Slice 1a: actual costs are not selling prices; physical returns stay quarantined."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import text

from app.sales.service import post_invoice_atomic

pytest_plugins = ["test_invoice_api"]


def test_issue_stores_verified_cost_not_selling_price(posting_env):
    _client, db, ids, _auth, invoice, _payload = posting_env
    line_id = UUID(invoice["lines"][0]["id"])
    assert Decimal(invoice["lines"][0]["unit_price"]) == Decimal("114.00")
    # Synthetic finance/owner verification exists before the issue is posted.
    db.execute(
        text("""
        UPDATE sales.sales_invoice_line
        SET verified_unit_cost=60.00, cost_evidence_ref='SYNTHETIC-COST-60',
            cost_verified_by=:actor, cost_verified_at=now()
        WHERE id=:id
    """),
        {"actor": ids["owner"], "id": line_id},
    )
    post_invoice_atomic(db, UUID(invoice["id"]), ids["owner"])
    movement = (
        db.execute(
            text("""
        SELECT unit_cost, cost_status FROM inventory.stock_movement
        WHERE invoice_line_id=:id AND movement_type='sale'
    """),
            {"id": line_id},
        )
        .mappings()
        .one()
    )
    assert movement["unit_cost"] == Decimal("60.00")
    assert movement["cost_status"] == "cost_verified"


def test_damaged_return_does_not_increase_saleable_stock(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    auth = headers("owner")
    opening = client.post(
        "/inventory/movements",
        headers=auth,
        json={
            "warehouse_id": str(ids["warehouse"]),
            "product_id": str(ids["product"]),
            "batch_id": str(ids["batch"]),
            "movement_type": "opening",
            "quantity": "10",
        },
    )
    assert opening.status_code == 201, opening.text
    response = client.post(
        "/returns",
        headers=auth,
        json={
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "batch_id": str(ids["batch"]),
            "quantity": "3",
            "return_date": "2026-10-01",
            "reason": "damaged",
        },
    )
    assert response.status_code == 201, response.text
    quantity = db.execute(
        text("""
        SELECT quantity FROM inventory.stock_balance
        WHERE warehouse_id=:w AND product_id=:p AND batch_id=:b
    """),
        {"w": ids["warehouse"], "p": ids["product"], "b": ids["batch"]},
    ).scalar_one()
    assert quantity == Decimal("10.000")
    returned = (
        db.execute(
            text("SELECT status, quantity FROM sales.sales_return WHERE id=:id"),
            {"id": UUID(response.json()["id"])},
        )
        .mappings()
        .one()
    )
    assert returned["status"] == "quarantined"
    assert returned["quantity"] == Decimal("3.000")
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM inventory.stock_movement WHERE source_type='return'"
            )
        ).scalar_one()
        == 0
    )
