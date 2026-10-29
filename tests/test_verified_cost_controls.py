"""Focused provenance, authorization and quarantine controls for Slice 1a."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.inventory import service as stock
from app.main import app
from app.sales import service as sales

pytest_plugins = ["test_invoice_api"]


def _path(invoice, line_id=None):
    return f"/invoices/{invoice['id']}/lines/{line_id or invoice['lines'][0]['id']}/verified-cost"


def _cost(**changes):
    return {
        "version": 1,
        "unit_cost": "60.00",
        "evidence_ref": "SYNTHETIC-CARRYING-COST",
        **changes,
    }


@pytest.mark.parametrize("role", ["owner", "finance"])
def test_authorized_cost_verification_is_private_and_actor_bound(invoice_env, role):
    client, db, ids, payload, headers = invoice_env
    owner = headers()
    invoice = client.post("/invoices", json=payload, headers=owner).json()
    if role == "finance":
        db.execute(
            text("UPDATE platform.platform_user SET role='finance' WHERE id=:id"),
            {"id": ids["other"]},
        )
        db.commit()
    actor = ids["owner"] if role == "owner" else ids["other"]
    response = client.post(
        _path(invoice),
        json=_cost(),
        headers=headers("owner" if role == "owner" else "other"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["verified_by"] == str(actor)
    assert response.json()["version"] == 2
    public = client.get(f"/invoices/{invoice['id']}", headers=owner).json()
    assert public["grand_total"] == invoice["grand_total"]
    assert public["lines"][0]["unit_price"] == "114.00"
    assert "verified_unit_cost" not in public["lines"][0]
    event = (
        db.execute(
            text(
                "SELECT actor_user_id, new_values FROM audit.audit_log WHERE action='cost_verified' AND entity_id=:id"
            ),
            {"id": UUID(invoice["lines"][0]["id"])},
        )
        .mappings()
        .one()
    )
    assert event["actor_user_id"] == actor
    assert event["new_values"]["unit_cost"] == "60.00"
    assert (
        client.post(f"/invoices/{invoice['id']}/post", headers=owner).status_code == 409
    )


@pytest.mark.parametrize("cost", ["0.00", "60.00"])
def test_verified_api_cost_reaches_issue_and_compensating_void(posting_env, cost):
    client, db, ids, auth, invoice, _payload = posting_env
    response = client.post(_path(invoice), json=_cost(unit_cost=cost), headers=auth)
    assert response.status_code == 200, response.text
    sales.post_invoice_atomic(db, UUID(invoice["id"]), ids["owner"])
    reason = uuid4()
    db.execute(
        text(
            "INSERT INTO audit.reason_code(id, code, category) VALUES (:id,:code,'void')"
        ),
        {"id": reason, "code": reason.hex[:30]},
    )
    sales.reverse_invoice_atomic(db, UUID(invoice["id"]), ids["owner"], reason)
    movements = (
        db.execute(
            text(
                "SELECT unit_cost, cost_status FROM inventory.stock_movement WHERE source_id=:id"
            ),
            {"id": UUID(invoice["id"])},
        )
        .mappings()
        .all()
    )
    assert len(movements) == 2
    assert all(
        row["unit_cost"] == Decimal(cost) and row["cost_status"] == "cost_verified"
        for row in movements
    )
    immutable = client.post(_path(invoice), json=_cost(version=4), headers=auth)
    assert immutable.status_code == 409


def test_legacy_price_is_not_backfilled_or_reused_as_reversal_cost(posting_env):
    from datetime import date

    from app.finance import ar

    _client, db, ids, _auth, invoice, _payload = posting_env
    invoice_id = UUID(invoice["id"])
    original_id, _ = stock.record_movement(
        db,
        actor_id=ids["owner"],
        warehouse_id=ids["warehouse"],
        product_id=ids["product"],
        batch_id=None,
        movement_type="sale",
        quantity=-2,
        unit_cost=Decimal("114.00"),
        source_type="invoice",
        source_id=invoice_id,
        invoice_line_id=UUID(invoice["lines"][0]["id"]),
    )
    ar.record_sale(
        db,
        customer_id=ids["customer"],
        invoice_id=invoice_id,
        amount=Decimal(invoice["grand_total"]),
        on_date=date.fromisoformat(invoice["invoice_date"]),
        actor_id=ids["owner"],
    )
    db.execute(
        text(
            "UPDATE sales.sales_invoice SET posting_status='Posted', posted_at=now(), posted_by=:actor, version=version+1 WHERE id=:id"
        ),
        {"actor": ids["owner"], "id": invoice_id},
    )
    reason = uuid4()
    db.execute(
        text(
            "INSERT INTO audit.reason_code(id,code,category) VALUES (:id,:code,'void')"
        ),
        {"id": reason, "code": reason.hex[:30]},
    )
    sales.reverse_invoice_atomic(db, invoice_id, ids["owner"], reason)
    original = stock.fetch_movement(db, original_id)
    assert original["unit_cost"] == Decimal("114.00")
    assert original["cost_status"] == "cost_unverified"
    compensating = (
        db.execute(
            text(
                "SELECT unit_cost, cost_status FROM inventory.stock_movement WHERE reverses_movement_id=:id"
            ),
            {"id": original_id},
        )
        .mappings()
        .one()
    )
    assert compensating["unit_cost"] is None
    assert compensating["cost_status"] == "cost_unverified"


def test_missing_cost_is_unknown_not_zero_or_selling_price(posting_env):
    _client, db, ids, _auth, invoice, _payload = posting_env
    sales.post_invoice_atomic(db, UUID(invoice["id"]), ids["owner"])
    row = (
        db.execute(
            text(
                "SELECT unit_cost, cost_status FROM inventory.stock_movement WHERE source_id=:id"
            ),
            {"id": UUID(invoice["id"])},
        )
        .mappings()
        .one()
    )
    assert row["unit_cost"] is None
    assert row["cost_status"] == "cost_unverified"


@pytest.mark.parametrize(
    "role",
    [
        "medical_rep",
        "sales_manager",
        "district_manager",
        "warehouse_staff",
        "read_only_auditor",
        "admin",
        "owner",
    ],
)
def test_other_roles_cannot_attest_cost(invoice_env, role):
    client, db, ids, payload, headers = invoice_env
    invoice = client.post("/invoices", json=payload, headers=headers()).json()
    db.execute(
        text("UPDATE platform.platform_user SET role=:role WHERE id=:id"),
        {"role": role, "id": ids["other"]},
    )
    db.commit()
    response = client.post(_path(invoice), json=_cost(), headers=headers("other"))
    assert response.status_code == 403, response.text
    assert (
        db.execute(
            text(
                "SELECT verified_unit_cost FROM sales.sales_invoice_line WHERE id=:id"
            ),
            {"id": UUID(invoice["lines"][0]["id"])},
        ).scalar_one()
        is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"unit_cost": "-0.01"},
        {"unit_cost": "NaN"},
        {"unit_cost": "Infinity"},
        {"unit_cost": "60.001"},
        {"unit_cost": "10000000000.00"},
        {"unit_cost": True},
        {"unit_cost": None},
        {"evidence_ref": "   "},
        {"evidence_ref": "x" * 241},
        {"version": True},
        {"verified_by": str(uuid4())},
        {"cost_status": "cost_verified"},
    ],
)
def test_invalid_or_forged_cost_input_is_rejected(posting_env, changes):
    client, db, _ids, auth, invoice, _payload = posting_env
    response = client.post(_path(invoice), json=_cost(**changes), headers=auth)
    assert response.status_code == 422, response.text
    assert (
        db.execute(
            text(
                "SELECT verified_unit_cost FROM sales.sales_invoice_line WHERE id=:id"
            ),
            {"id": UUID(invoice["lines"][0]["id"])},
        ).scalar_one()
        is None
    )


def test_finance_cannot_attest_outside_assigned_territory(invoice_env):
    client, db, ids, payload, headers = invoice_env
    invoice = client.post(
        "/invoices",
        json={**payload, "customer_id": str(ids["other_customer"])},
        headers=headers(),
    ).json()
    db.execute(
        text("UPDATE platform.platform_user SET role='finance' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    assert (
        client.post(_path(invoice), json=_cost(), headers=headers("other")).status_code
        == 404
    )


def test_unknown_line_and_unauthenticated_verification_are_denied(posting_env):
    client, _db, _ids, auth, invoice, _payload = posting_env
    assert (
        client.post(_path(invoice, uuid4()), json=_cost(), headers=auth).status_code
        == 404
    )
    assert client.post(_path(invoice), json=_cost()).status_code == 401


def test_stale_cost_edit_rejected_and_draft_replacement_clears_proof(posting_env):
    client, db, _ids, auth, invoice, payload = posting_env
    assert client.post(_path(invoice), json=_cost(), headers=auth).status_code == 200
    assert (
        client.post(
            _path(invoice), json=_cost(unit_cost="55.00"), headers=auth
        ).status_code
        == 409
    )
    edited = client.put(
        f"/invoices/{invoice['id']}", json={**payload, "version": 2}, headers=auth
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["lines"][0]["id"] != invoice["lines"][0]["id"]
    assert (
        db.execute(
            text(
                "SELECT verified_unit_cost FROM sales.sales_invoice_line WHERE invoice_id=:id"
            ),
            {"id": UUID(invoice["id"])},
        ).scalar_one()
        is None
    )
    assert (
        db.execute(
            text("SELECT count(*) FROM audit.audit_log WHERE action='cost_verified'")
        ).scalar_one()
        == 1
    )


def test_verified_movement_cannot_forge_cost_against_source(posting_env):
    client, db, ids, auth, invoice, _payload = posting_env
    assert client.post(_path(invoice), json=_cost(), headers=auth).status_code == 200
    with pytest.raises(IntegrityError):
        stock.record_movement(
            db,
            actor_id=ids["owner"],
            warehouse_id=ids["warehouse"],
            product_id=ids["product"],
            batch_id=None,
            movement_type="sale",
            quantity=Decimal(-2),
            unit_cost=Decimal("114.00"),
            cost_status="cost_verified",
            source_type="invoice",
            source_id=UUID(invoice["id"]),
            invoice_line_id=UUID(invoice["lines"][0]["id"]),
        )
    db.rollback()
    assert db.execute(
        text(
            "SELECT quantity FROM inventory.stock_balance WHERE warehouse_id=:w AND product_id=:p"
        ),
        {"w": ids["warehouse"], "p": ids["product"]},
    ).scalar_one() == Decimal("10.000")
    assert (
        db.execute(text("SELECT count(*) FROM inventory.stock_movement")).scalar_one()
        == 0
    )


def test_cost_audit_failure_rolls_back_proof_and_version(posting_env, monkeypatch):
    _client, db, _ids, auth, invoice, _payload = posting_env
    from app.sales import router

    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(router, "log_audit", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert (
            client.post(_path(invoice), json=_cost(), headers=auth).status_code == 500
        )
    assert (
        db.execute(
            text(
                "SELECT verified_unit_cost FROM sales.sales_invoice_line WHERE invoice_id=:id"
            ),
            {"id": UUID(invoice["id"])},
        ).scalar_one()
        is None
    )
    assert (
        db.execute(
            text("SELECT version FROM sales.sales_invoice WHERE id=:id"),
            {"id": UUID(invoice["id"])},
        ).scalar_one()
        == 1
    )


@pytest.mark.parametrize("reason", ["damaged", "unsuitable", "good condition", "تالف"])
def test_every_new_return_is_quarantined_not_approved_or_valued(invoice_env, reason):
    client, db, ids, _payload, headers = invoice_env
    response = client.post(
        "/returns",
        headers=headers(),
        json={
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "batch_id": str(ids["batch"]),
            "quantity": "3",
            "return_date": "2026-10-01",
            "reason": reason,
            "status": "approved",
            "approved_by": str(ids["owner"]),
            "unit_cost": "0",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "quarantined"
    for table in (
        "inventory.stock_movement",
        "inventory.stock_balance",
        "finance.ar_entry",
    ):
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    assert (
        client.post(
            f"/returns/{response.json()['id']}/release", headers=headers()
        ).status_code
        == 404
    )


def test_return_audit_failure_does_not_leave_intake(invoice_env, monkeypatch):
    _client, db, ids, _payload, headers = invoice_env
    from app.returns import router

    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")

    auth = headers()
    monkeypatch.setattr(router, "log_audit", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/returns",
            headers=auth,
            json={
                "customer_id": str(ids["customer"]),
                "product_id": str(ids["product"]),
                "warehouse_id": str(ids["warehouse"]),
                "quantity": "3",
                "return_date": "2026-10-01",
            },
        )
    assert response.status_code == 500
    assert db.execute(text("SELECT count(*) FROM sales.sales_return")).scalar_one() == 0
