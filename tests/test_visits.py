"""Tests for customer stock visits (V2 §2B.10, §2B.11)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

pytest_plugins = ["test_invoice_api"]


def test_create_and_list_visit(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    customer_id = ids["customer"]
    product_id = ids["product"]

    payload = {
        "customer_id": str(customer_id),
        "visit_date": date.today().isoformat(),
        "notes": "Regular stock check",
        "lines": [
            {
                "product_id": str(product_id),
                "quantity_prev": "10",
                "quantity_delivered": "5",
                "quantity_returned": "1",
                "quantity_current": "8",
                "amount": "150.00",
                "payment_method": "Cash",
            }
        ],
    }
    res = client.post("/visits", headers=headers("owner"), json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["customer_id"] == str(customer_id)
    assert len(data["lines"]) == 1
    # sell_through = prev (10) + delivered (5) - returned (1) - current (8) = 6
    assert data["lines"][0]["sell_through"] == "6.000"

    # List visits
    listing = client.get("/visits", headers=headers("owner"))
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1


def test_visit_deletion_audited(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    customer_id = ids["customer"]
    product_id = ids["product"]

    payload = {
        "customer_id": str(customer_id),
        "visit_date": date.today().isoformat(),
        "lines": [{"product_id": str(product_id), "quantity_prev": "5"}],
    }
    res = client.post("/visits", headers=headers("owner"), json=payload)
    assert res.status_code == 201
    visit_id = res.json()["id"]

    del_res = client.delete(f"/visits/{visit_id}", headers=headers("owner"))
    assert del_res.status_code == 200

    audit = db.execute(
        text("SELECT action FROM audit.audit_log WHERE entity_id=:id AND entity_type='stock_visit'"),
        {"id": visit_id},
    ).scalar()
    assert audit == "deleted"
