"""Current-contract territory target controls, not manufactured historical RED."""

import importlib.util
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from test_invoice_api import invoice_env as invoice_env  # noqa: PLC0414
from test_lane1_r22_territory_http import (
    require_owned_verifier_database as require_owned_verifier_database,  # noqa: PLC0414
)
from test_sales_targets import _month_start, _seed_posted_sale


def _territory_payload(ids, **changes):
    return {
        "territory_id": str(ids["territory"]),
        "product_id": str(ids["product"]),
        "period_month": _month_start().isoformat(),
        "target_quantity": "100.000",
        **changes,
    }


def test_territory_actuals_distinguish_product_book_other_scope_period_and_draft(
    invoice_env,
):
    from app import config

    assert config.POSTING_ENABLED is False
    client, db, ids, draft_payload, headers = invoice_env
    auth = headers("owner")
    _seed_posted_sale(
        db,
        ids,
        rep=ids["other"],
        product=ids["product"],
        qty="30",
        day_of_month=2,
        seq=1,
    )
    _seed_posted_sale(
        db,
        ids,
        rep=ids["other"],
        product=ids["exempt"],
        qty="20",
        day_of_month=3,
        seq=2,
    )
    db.commit()
    draft = client.post("/invoices", headers=auth, json=draft_payload)
    assert draft.status_code == 201, draft.text
    assert draft.json()["posting_status"] == "Draft"
    prior = (_month_start() - timedelta(days=1)).replace(day=1)
    payloads = [
        _territory_payload(ids),
        _territory_payload(ids, product_id=None),
        _territory_payload(ids, territory_id=str(ids["other_territory"])),
        _territory_payload(ids, period_month=prior.isoformat()),
    ]
    created = []
    for payload in payloads:
        response = client.post("/targets", headers=auth, json=payload)
        assert response.status_code == 201, response.text
        created.append(response.json())
    assert Decimal(created[0]["actual_quantity"]) == Decimal("30.000")
    assert Decimal(created[1]["actual_quantity"]) == Decimal("50.000")
    assert created[2]["actual_quantity"] is None
    assert created[3]["actual_quantity"] is None
    changed = client.post(
        "/targets",
        headers=auth,
        json=_territory_payload(ids, target_quantity="125.500"),
    )
    assert changed.status_code == 201, changed.text
    assert changed.json()["id"] == created[0]["id"]
    assert Decimal(changed.json()["target_quantity"]) == Decimal("125.500")
    filtered = client.get(
        "/targets",
        headers=auth,
        params={
            "territory_id": str(ids["territory"]),
            "month": _month_start().isoformat(),
        },
    )
    assert filtered.status_code == 200
    assert {row["id"] for row in filtered.json()} == {
        created[0]["id"],
        created[1]["id"],
    }
    assert config.POSTING_ENABLED is False


@pytest.mark.parametrize("scope", ["neither", "both"])
def test_territory_target_requires_exactly_one_scope(invoice_env, scope):
    client, _db, ids, _payload, headers = invoice_env
    payload = _territory_payload(ids)
    if scope == "neither":
        payload.pop("territory_id")
    else:
        payload["rep_id"] = str(ids["other"])
    response = client.post("/targets", headers=headers("owner"), json=payload)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["territory_id", "product_id"])
def test_unknown_territory_target_reference_is_rejected(invoice_env, field):
    client, _db, ids, _payload, headers = invoice_env
    response = client.post(
        "/targets",
        headers=headers("owner"),
        json=_territory_payload(ids, **{field: str(uuid4())}),
    )
    assert response.status_code == 422, response.text


def test_territory_target_does_not_expand_medical_rep_access(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    payload = _territory_payload(ids)
    assert (
        client.post("/targets", headers=headers("owner"), json=payload).status_code
        == 201
    )
    rep = headers("other")
    assert client.post("/targets", headers=rep, json=payload).status_code == 403
    response = client.get(
        "/targets", headers=rep, params={"territory_id": str(ids["territory"])}
    )
    assert response.status_code == 200
    assert response.json() == []
    assert client.get("/targets").status_code == 401


def test_populated_territory_downgrade_preserves_data_and_blocks_competing_writer(
    invoice_env,
):
    from app.db import engine

    client, db, ids, _payload, headers = invoice_env
    response = client.post(
        "/targets", headers=headers("owner"), json=_territory_payload(ids)
    )
    assert response.status_code == 201, response.text
    target_id = response.json()["id"]
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0022_territory_targets.py"
    )
    spec = importlib.util.spec_from_file_location("r22_owned_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with (
        Operations.context(MigrationContext.configure(db.connection())),
        pytest.raises(RuntimeError, match="territory targets must be preserved"),
    ):
        migration.downgrade()
    assert str(
        db.scalar(
            text("SELECT territory_id FROM sales.sales_target WHERE id=:id"),
            {"id": target_id},
        )
    ) == str(ids["territory"])
    with engine.connect() as competitor:
        competitor.execute(text("SET LOCAL lock_timeout = '150ms'"))
        with pytest.raises(OperationalError) as blocked:
            competitor.execute(
                text(
                    "INSERT INTO sales.sales_target(rep_id,period_month,target_quantity,created_by) VALUES (:rep,:month,1,:owner)"
                ),
                {"rep": ids["other"], "month": _month_start(), "owner": ids["owner"]},
            )
        assert blocked.value.orig.sqlstate == "55P03"
        competitor.rollback()
    assert str(
        db.scalar(
            text("SELECT territory_id FROM sales.sales_target WHERE id=:id"),
            {"id": target_id},
        )
    ) == str(ids["territory"])
