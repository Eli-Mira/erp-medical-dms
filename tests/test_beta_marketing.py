"""Contained HTTP tests. Parent must migrate a fresh task-owned PostgreSQL DB first.

BETA_MARKETING_TEST_URL must name a disposable dms_cycle_test_<32hex> database.
Authentication is overridden here; production authentication is a separate gate.
"""

import importlib
import os
import re
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture
def setup():
    url = os.environ.get("BETA_MARKETING_TEST_URL")
    if not url:
        pytest.skip("Explicit task-owned PostgreSQL URL required")
    parsed = make_url(url)
    assert parsed.get_backend_name() == "postgresql"
    assert bool(re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", parsed.database or ""))
    module = importlib.import_module("app.marketing.router")
    engine = create_engine(url)
    ids = {
        name: str(uuid4())
        for name in ("actor", "territory", "other", "product", "inactive")
    }
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO platform.platform_user (id, username, password_hash, role, is_owner) VALUES (:id, :name, 'not-a-login', 'owner', true)"
            ),
            {"id": ids["actor"], "name": "beta_" + ids["actor"]},
        )
        for name in ("territory", "other"):
            db.execute(
                text(
                    "INSERT INTO master_data.master_territory (id, code, name_ar) VALUES (:id, :code, :name)"
                ),
                {"id": ids[name], "code": uuid4().hex[:20], "name": name},
            )
        for name in ("product", "inactive"):
            db.execute(
                text(
                    "INSERT INTO master_data.master_product (id, sku, name_ar, base_price, is_active) VALUES (:id, :sku, :name, 1, :active)"
                ),
                {
                    "id": ids[name],
                    "sku": uuid4().hex,
                    "name": name,
                    "active": name != "inactive",
                },
            )
        db.execute(
            text(
                "INSERT INTO platform.user_territory (user_id, territory_id) VALUES (:actor, :territory)"
            ),
            ids,
        )
    user = {"id": ids["actor"], "role": "owner", "is_owner": True, "is_active": True}

    def database():
        with Session(engine) as session:
            try:
                yield session
            finally:
                session.rollback()

    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_db] = database
    app.dependency_overrides[module.get_current_user] = lambda: user
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, engine, ids, user, module
    # The parent drops the entire task-owned database after all gates.
    engine.dispose()


def spend(ids):
    return {
        "territory_id": ids["territory"],
        "kol_id": None,
        "spend_date": "2026-10-30",
        "amount": "12.34",
        "activity_type": "meeting",
        "notes": "Beta",
        "product_ids": [ids["product"]],
    }


def test_create_reopen_edit_stale_and_audit(setup):
    client, engine, ids, _user, _module = setup
    response = client.post("/marketing/spend", json=spend(ids))
    assert response.status_code == 201, response.text
    sid = response.json()["id"]
    original = client.get("/marketing/spend/" + sid).json()
    body = {
        **spend(ids),
        "amount": "20.00",
        "product_ids": [],
        "revision": original["revision"],
    }
    response = client.patch("/marketing/spend/" + sid, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["product_ids"] == []
    assert client.patch("/marketing/spend/" + sid, json=body).status_code == 409
    objective_ids = []
    for label in ("first", "second"):
        payload = {
            "spend_id": sid,
            "territory_id": ids["territory"],
            "product_id": ids["product"],
            "objective": label,
            "expected_kpi": "10",
            "actual_result": "8",
            "followup_notes": "call",
        }
        response = client.post("/marketing/objectives", json=payload)
        assert response.status_code == 201, response.text
        oid = response.json()["id"]
        objective_ids.append(oid)
        reopened = client.get("/marketing/objectives/" + oid).json()
        response = client.patch(
            "/marketing/objectives/" + oid,
            json={**payload, "actual_result": "11", "revision": reopened["revision"]},
        )
        assert response.status_code == 200, response.text
        assert (
            client.get("/marketing/objectives/" + oid).json()["actual_result"] == "11"
        )
    with Session(engine) as independent:
        assert (
            independent.execute(
                text("SELECT amount FROM marketing.marketing_spend WHERE id=:id"),
                {"id": sid},
            ).scalar()
            == 20
        )
        assert (
            independent.execute(
                text(
                    "SELECT count(*) FROM marketing.marketing_spend_product WHERE spend_id=:id"
                ),
                {"id": sid},
            ).scalar()
            == 0
        )
        assert (
            independent.execute(
                text(
                    "SELECT count(*) FROM marketing.marketing_objective WHERE spend_id=:id"
                ),
                {"id": sid},
            ).scalar()
            == 2
        )
        assert (
            independent.execute(
                text(
                    "SELECT count(*) FROM audit.audit_log WHERE entity_id=:id AND actor_user_id=:actor"
                ),
                {"id": sid, "actor": ids["actor"]},
            ).scalar()
            == 2
        )


@pytest.mark.parametrize(
    "change",
    [
        {"amount": "NaN"},
        {"amount": "Infinity"},
        {"amount": "-1"},
        {"amount": "0.001"},
        {"amount": "1000000000000.00"},
        {"product_ids": ["broken"]},
        {"territory_id": "broken"},
        {"kol_id": "broken"},
        {"created_by": "forged"},
        {"spend_date": "bad"},
    ],
)
def test_invalid_create(setup, change):
    client, _engine, ids, _user, _module = setup
    assert (
        client.post("/marketing/spend", json={**spend(ids), **change}).status_code
        == 422
    )


def test_reference_scope_and_read_only(setup):
    client, _engine, ids, user, _module = setup
    for product in (ids["inactive"], str(uuid4())):
        assert (
            client.post(
                "/marketing/spend", json={**spend(ids), "product_ids": [product]}
            ).status_code
            == 422
        )
    user.update(role="sales_manager", is_owner=False)
    assert (
        client.post(
            "/marketing/spend", json={**spend(ids), "territory_id": ids["other"]}
        ).status_code
        == 403
    )
    assert client.post("/marketing/spend", json=spend(ids)).status_code == 201
    user["role"] = "read_only_auditor"
    assert client.post("/marketing/spend", json=spend(ids)).status_code == 403
    user.update(role="owner", is_owner=True, is_active=False)
    assert client.post("/marketing/spend", json=spend(ids)).status_code == 403


def test_audit_failure_rolls_back_create_and_update(setup, monkeypatch):
    client, engine, ids, _user, module = setup
    response = client.post("/marketing/spend", json=spend(ids))
    assert response.status_code == 201
    sid = response.json()["id"]
    revision = client.get("/marketing/spend/" + sid).json()["revision"]

    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(module, "log_audit", fail)
    assert client.post("/marketing/spend", json=spend(ids)).status_code == 500
    assert (
        client.patch(
            "/marketing/spend/" + sid,
            json={
                **spend(ids),
                "amount": "99.00",
                "product_ids": [],
                "revision": revision,
            },
        ).status_code
        == 500
    )
    with Session(engine) as independent:
        assert (
            independent.execute(
                text(
                    "SELECT count(*) FROM marketing.marketing_spend WHERE created_by=:actor"
                ),
                ids,
            ).scalar()
            == 1
        )
        assert (
            str(
                independent.execute(
                    text("SELECT amount FROM marketing.marketing_spend WHERE id=:id"),
                    {"id": sid},
                ).scalar()
            )
            == "12.34"
        )
        assert (
            independent.execute(
                text(
                    "SELECT count(*) FROM marketing.marketing_spend_product WHERE spend_id=:id"
                ),
                {"id": sid},
            ).scalar()
            == 1
        )


def test_detail_preserves_exact_money_string(setup):
    client, _engine, ids, _user, _module = setup
    response = client.post("/marketing/spend", json=spend(ids))
    assert response.status_code == 201
    detail = client.get("/marketing/spend/" + response.json()["id"])
    assert detail.status_code == 200
    assert detail.json()["amount"] == "12.34"


def test_list_preserves_existing_territory_scope(setup):
    client, _engine, ids, user, _module = setup
    own = client.post("/marketing/spend", json=spend(ids)).json()["id"]
    other = client.post(
        "/marketing/spend", json={**spend(ids), "territory_id": ids["other"]}
    ).json()["id"]
    user.update(role="sales_manager", is_owner=False)
    visible = {row["id"] for row in client.get("/marketing/spend").json()}
    assert own in visible and other not in visible


@pytest.mark.parametrize("method", ["create", "update"])
@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("spend", "activity_type"),
        ("spend", "notes"),
        ("objectives", "objective"),
        ("objectives", "expected_kpi"),
        ("objectives", "actual_result"),
        ("objectives", "followup_notes"),
    ],
)
def test_null_text_is_rejected_without_writes(setup, kind, field, method):
    client, engine, ids, _user, _module = setup
    payload = (
        spend(ids)
        if kind == "spend"
        else {
            "territory_id": ids["territory"],
            "product_id": ids["product"],
            "objective": "Synthetic valid objective",
            "expected_kpi": "10",
            "actual_result": "8",
            "followup_notes": "Synthetic follow-up",
        }
    )
    path = "/marketing/" + kind
    if method == "update":
        created = client.post(path, json=payload)
        assert created.status_code == 201
        path += "/" + created.json()["id"]
        detail = client.get(path)
        assert detail.status_code == 200
        payload["revision"] = detail.json()["revision"]
        if kind == "spend":
            payload["product_ids"] = []

    def snapshot():
        with engine.connect() as db:
            return {
                relation: tuple(
                    db.execute(
                        text(
                            "SELECT to_jsonb(r)::text FROM "
                            + relation
                            + " r ORDER BY 1"
                        )
                    ).scalars()
                )
                for relation in (
                    "marketing.marketing_spend",
                    "marketing.marketing_spend_product",
                    "marketing.marketing_objective",
                    "audit.audit_log",
                )
            }

    before = snapshot()
    payload[field] = "Synthetic\u0000invalid"
    response = (
        client.post(path, json=payload)
        if method == "create"
        else client.patch(path, json=payload)
    )
    assert response.status_code == 422
    assert snapshot() == before
