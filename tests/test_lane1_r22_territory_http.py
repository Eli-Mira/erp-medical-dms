"""Territory targets must work without inventing a representative."""

import os
import re
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from test_invoice_api import invoice_env as invoice_env  # noqa: PLC0414


@pytest.fixture(autouse=True)
def require_owned_verifier_database():
    from app.db import engine

    expected = make_url(os.environ["DATABASE_URL"])
    assert os.environ.get("APP_ENV") == "test"
    assert expected.host in {"localhost", "127.0.0.1", "::1"}
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", expected.database or "")
    assert engine.url == expected
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == expected.database


def test_owner_can_set_a_territory_product_target_without_a_rep(invoice_env):
    client, db, ids, _invoice_payload, headers = invoice_env
    auth = headers("owner")
    payload = {
        "territory_id": str(ids["territory"]),
        "product_id": str(ids["product"]),
        "period_month": "2026-10-15",
        "target_quantity": "125.500",
    }
    response = client.post("/targets", headers=auth, json=payload)
    assert response.status_code == 201, (
        "A territory-level target must not require a representative: " + response.text
    )
    target = response.json()
    assert target["territory_id"] == payload["territory_id"]
    assert target["rep_id"] is None
    assert target["product_id"] == payload["product_id"]
    assert target["period_month"] == "2026-10-01"
    assert Decimal(target["target_quantity"]) == Decimal("125.500")
    assert target["actual_quantity"] is None
    fetched = client.get(
        "/targets",
        headers=auth,
        params={"territory_id": payload["territory_id"], "month": "2026-10-01"},
    )
    assert fetched.status_code == 200
    assert fetched.json() == [target]
    event = (
        db.execute(
            text(
                "SELECT actor_user_id,new_values FROM audit.audit_log "
                "WHERE entity_type='sales_target' AND entity_id=:id AND action='upserted'"
            ),
            {"id": target["id"]},
        )
        .mappings()
        .one()
    )
    assert event["actor_user_id"] == ids["owner"]
    assert Decimal(event["new_values"]["target_quantity"]) == Decimal("125.500")
