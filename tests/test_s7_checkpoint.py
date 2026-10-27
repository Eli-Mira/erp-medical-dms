"""S7 acceptance controls on the runner-owned PostgreSQL database only."""

import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine
from app.main import app

pytest_plugins = ["test_invoice_api", "test_inventory_api"]


@pytest.fixture(autouse=True)
def disposable_s7_database():
    assert os.environ.get("APP_ENV") == "test"
    assert engine.url.database.startswith("dms_cycle_test_")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT current_database()")).scalar_one()
            == engine.url.database
        )


def visit_payload(ids, *, customer="customer", batch=False, day=15, current="8"):
    return {
        "customer_id": str(ids[customer]),
        "visit_date": date(2026, 10, day).isoformat(),
        "notes": "Header note",
        "lines": [
            {
                "product_id": str(ids["product"]),
                "batch_id": str(ids["batch"]) if batch else None,
                "quantity_prev": "10.125",
                "quantity_delivered": "5.250",
                "quantity_returned": "1.125",
                "quantity_current": current,
                "notes": "Line note",
            }
        ],
    }


def create(client, auth, payload):
    response = client.post("/visits", headers=auth, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def held(client, auth, ids):
    response = client.get(
        "/visits/held-stock",
        headers=auth,
        params={"customer_id": str(ids["customer"]), "product_id": str(ids["product"])},
    )
    assert response.status_code == 200, response.text
    return response.json()


def effects(db):
    return tuple(
        db.execute(text("SELECT count(*) FROM " + table)).scalar_one()
        for table in (
            "sales.customer_stock_visit",
            "sales.customer_stock_visit_line",
            "sales.customer_held_stock",
        )
    ) + (
        db.execute(
            text("SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_visit'")
        ).scalar_one(),
    )


def test_rep_cannot_create_outside_assigned_territory(invoice_env):
    client, db, ids, _, headers = invoice_env
    auth = headers("other")
    before = effects(db)
    response = client.post(
        "/visits", headers=auth, json=visit_payload(ids, customer="other_customer")
    )
    assert response.status_code == 404, response.text
    assert effects(db) == before


def test_rep_cannot_delete_another_reps_visit(invoice_env):
    client, db, ids, _, headers = invoice_env
    row = create(client, headers(), visit_payload(ids))
    auth = headers("other")
    before = effects(db)
    response = client.delete("/visits/" + row["id"], headers=auth)
    assert response.status_code == 404, response.text
    assert effects(db) == before


def test_rep_held_stock_is_territory_scoped(invoice_env):
    client, _, ids, _, headers = invoice_env
    create(client, headers(), visit_payload(ids, customer="other_customer"))
    response = client.get("/visits/held-stock", headers=headers("other"))
    assert response.status_code == 200, response.text
    assert response.json() == {"total": 0, "items": []}


def test_manager_reads_all_rep_visits_district_only_assigned_territory(invoice_env):
    client, db, ids, _, headers = invoice_env
    auth = headers()
    allowed = create(client, auth, visit_payload(ids))
    denied = create(client, auth, visit_payload(ids, customer="other_customer"))
    db.execute(
        text("UPDATE platform.platform_user SET role='district_manager' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    manager_auth = headers("other")
    response = client.get("/visits", headers=manager_auth)
    assert response.status_code == 200, response.text
    assert [r["id"] for r in response.json()["items"]] == [allowed["id"]]
    db.execute(
        text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    response = client.get("/visits", headers=manager_auth)
    assert response.status_code == 200, response.text
    assert {r["id"] for r in response.json()["items"]} == {allowed["id"], denied["id"]}


@pytest.mark.parametrize("role", ["admin", "finance", "warehouse_staff", "user"])
def test_unauthorized_roles_denied_server_side(invoice_env, role):
    client, db, ids, _, headers = invoice_env
    db.execute(
        text("UPDATE platform.platform_user SET role=:role WHERE id=:id"),
        {"role": role, "id": ids["other"]},
    )
    db.commit()
    auth = headers("other")
    assert client.get("/visits", headers=auth).status_code == 403
    assert client.get("/visits/held-stock", headers=auth).status_code == 403
    assert (
        client.post("/visits", headers=auth, json=visit_payload(ids)).status_code == 403
    )
    assert client.delete("/visits/" + str(uuid4()), headers=auth).status_code == 403


def test_rep_own_visit_and_server_bound_actor(invoice_env):
    client, _, ids, _, headers = invoice_env
    owner_row = create(client, headers(), visit_payload(ids))
    auth = headers("other")
    own = create(client, auth, visit_payload(ids, day=16, current="7.125"))
    assert own["rep_id"] == own["created_by"] == str(ids["other"])
    assert own["lines"][0]["sell_through"] == "7.125"
    response = client.get("/visits", headers=auth, params={"rep_id": str(ids["owner"])})
    assert response.status_code == 200, response.text
    assert [r["id"] for r in response.json()["items"]] == [own["id"]]
    assert owner_row["id"] != own["id"]
    forged = visit_payload(ids)
    forged["rep_id"] = str(ids["owner"])
    assert client.post("/visits", headers=auth, json=forged).status_code == 422


def test_visit_page_limits_headers_not_lines(invoice_env):
    client, _, ids, _, headers = invoice_env
    auth = headers()
    payload = visit_payload(ids)
    payload["lines"].append({"product_id": str(ids["exempt"]), "quantity_prev": "1"})
    row = create(client, auth, payload)
    create(client, auth, visit_payload(ids, day=14))
    response = client.get("/visits", headers=auth, params={"limit": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2 and len(body["items"]) == 1
    assert body["items"][0] == row
    assert row["notes"] == "Header note"
    assert (
        next(
            line for line in row["lines"] if line["product_id"] == str(ids["product"])
        )["notes"]
        == "Line note"
    )
    assert len(row["lines"]) == 2


@pytest.mark.parametrize("batch", [False, True])
def test_repeat_visit_updates_exactly_one_held_tuple(invoice_env, batch):
    client, _, ids, _, headers = invoice_env
    auth = headers()
    first = create(client, auth, visit_payload(ids, batch=batch, day=14, current="12"))
    second = create(client, auth, visit_payload(ids, batch=batch, current="8.125"))
    body = held(client, auth, ids)
    assert body["total"] == 1, body
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity_on_hand"] == "8.125"
    assert body["items"][0]["last_visit_id"] == second["id"] != first["id"]


def test_backdated_visit_and_delete_rebuild_latest_observation(invoice_env):
    client, _, ids, _, headers = invoice_env
    auth = headers()
    latest = create(client, auth, visit_payload(ids, current="8"))
    older = create(client, auth, visit_payload(ids, day=14, current="12"))
    assert held(client, auth, ids)["items"][0]["last_visit_id"] == latest["id"]
    assert client.delete("/visits/" + latest["id"], headers=auth).status_code == 200
    body = held(client, auth, ids)
    assert body["total"] == 1
    assert body["items"][0]["last_visit_id"] == older["id"]
    assert body["items"][0]["quantity_on_hand"] == "12.000"
    assert client.delete("/visits/" + older["id"], headers=auth).status_code == 200
    assert held(client, auth, ids) == {"total": 0, "items": []}


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity_prev": "-1"},
        {"quantity_current": "20"},
        {"quantity_returned": "20"},
        {"quantity_prev": "NaN"},
        {"quantity_current": "Infinity"},
        {"quantity_prev": True},
        {"quantity_current": "1.0001"},
        {"sell_through": "0"},
        {"quantity_prev": "999999999.999", "quantity_delivered": "999999999.999"},
    ],
)
def test_invalid_visit_quantities_leave_no_effects(invoice_env, changes):
    client, db, ids, _, headers = invoice_env
    auth = headers()
    payload = visit_payload(ids)
    payload["lines"][0].update(changes)
    before = effects(db)
    response = client.post("/visits", headers=auth, json=payload)
    assert response.status_code == 422, response.text
    assert effects(db) == before


def test_duplicate_products_and_mismatched_batches_rejected(invoice_env):
    client, db, ids, _, headers = invoice_env
    auth = headers()
    payload = visit_payload(ids)
    payload["lines"].append(dict(payload["lines"][0]))
    before = effects(db)
    with TestClient(app, raise_server_exceptions=False) as raw:
        assert raw.post("/visits", headers=auth, json=payload).status_code == 422
    assert effects(db) == before
    payload = visit_payload(ids, batch=True)
    payload["lines"][0]["product_id"] = str(ids["exempt"])
    assert client.post("/visits", headers=auth, json=payload).status_code == 422
    assert effects(db) == before


@pytest.mark.parametrize("failure", ["audit", "response"])
def test_visit_failure_rolls_back_whole_transaction(invoice_env, monkeypatch, failure):
    from app.visits import repo, router

    _client, db, ids, _, headers = invoice_env
    auth = headers()
    before = effects(db)
    if failure == "audit":

        def fail(*args, **kwargs):
            raise RuntimeError("S7 synthetic audit failure")

        monkeypatch.setattr(router, "log_audit", fail)
    else:
        original = repo.create_visit

        def invalid(*args, **kwargs):
            row = original(*args, **kwargs)
            row.pop("lines")
            return row

        monkeypatch.setattr(repo, "create_visit", invalid)
    with TestClient(app, raise_server_exceptions=False) as raw:
        assert (
            raw.post("/visits", headers=auth, json=visit_payload(ids)).status_code
            == 500
        )
    assert effects(db) == before


def test_db_rejects_duplicate_null_batch_held_tuple(invoice_env):
    client, db, ids, _, headers = invoice_env
    create(client, headers(), visit_payload(ids))
    with pytest.raises(IntegrityError) as caught, db.begin_nested():
        db.execute(
            text(
                "INSERT INTO sales.customer_held_stock(customer_id,product_id,quantity_on_hand) VALUES (:c,:p,0)"
            ),
            {"c": ids["customer"], "p": ids["product"]},
        )
    assert caught.value.orig.sqlstate == "23505"


def seed_expiry(db, ids, offsets):
    today = db.execute(text("SELECT CURRENT_DATE")).scalar_one()
    result = {}
    for offset in offsets:
        bid = uuid4()
        db.execute(
            text(
                "INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date) VALUES (:id,:p,:w,:bn,:ed)"
            ),
            {
                "id": bid,
                "p": ids["product"],
                "w": ids["warehouse"],
                "bn": "S7-" + str(offset),
                "ed": today + timedelta(days=offset),
            },
        )
        db.execute(
            text(
                "INSERT INTO inventory.stock_balance(warehouse_id,product_id,batch_id,quantity) VALUES (:w,:p,:b,1.125)"
            ),
            {"w": ids["warehouse"], "p": ids["product"], "b": bid},
        )
        result[offset] = str(bid)
    db.commit()
    return result


def test_expiry_exact_default_boundaries_and_empty_state(stock_env):
    client, db, ids, headers, _ = stock_env
    auth = headers()
    assert client.get("/inventory/expiry-warnings", headers=auth).json() == []
    batches = seed_expiry(db, ids, [-1, 0, 30, 31, 60])
    response = client.get("/inventory/expiry-warnings", headers=auth)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert {r["id"] for r in rows} == {batches[0], batches[30]}
    assert [r["days_until_expiry"] for r in rows] == [0, 30]
    assert all(Decimal(r["quantity"]) == Decimal("1.125") for r in rows)


def test_expiry_configured_window_and_legacy_put_preservation(stock_env):
    client, db, ids, headers, _ = stock_env
    auth = headers()
    batches = seed_expiry(db, ids, [31, 45, 46])
    payload = {
        "stock_cover_window_days": 30,
        "overstock_threshold_days": 180,
        "expiry_warning_days": 45,
    }
    response = client.put("/settings/inventory-policy", headers=auth, json=payload)
    assert response.status_code == 200 and response.json() == payload
    rows = client.get("/inventory/expiry-warnings", headers=auth).json()
    assert {r["id"] for r in rows} == {batches[31], batches[45]}
    payload.pop("expiry_warning_days")
    response = client.put("/settings/inventory-policy", headers=auth, json=payload)
    assert response.status_code == 200 and response.json()["expiry_warning_days"] == 45


def test_expiry_scope_role_and_explicit_warehouse_denial(stock_env):
    client, db, ids, headers, _ = stock_env
    seed_expiry(db, ids, [1])
    db.execute(
        text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    auth = headers("other")
    assert client.get("/inventory/expiry-warnings", headers=auth).status_code == 403
    db.execute(
        text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
        {"u": ids["other"], "b": ids["branch"]},
    )
    db.commit()
    response = client.get("/inventory/expiry-warnings", headers=auth)
    assert response.status_code == 200 and len(response.json()) == 1
    assert (
        client.get(
            "/inventory/expiry-warnings",
            headers=auth,
            params={"warehouse_id": str(uuid4())},
        ).status_code
        == 404
    )
    db.execute(
        text("UPDATE platform.platform_user SET role='medical_rep' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    assert client.get("/inventory/expiry-warnings", headers=auth).status_code == 403
    assert client.get("/inventory/expiry-warnings").status_code == 401
