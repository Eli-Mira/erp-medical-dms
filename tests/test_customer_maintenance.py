"""First B-01 customer-maintenance tracer; approved disposable runner only."""

import os
import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture
def customer_env():
    # This module is not admitted by conftest's financial-module allowlist.
    explicit_url = os.environ.get("DATABASE_URL")
    assert explicit_url, "Use scripts/verify_invoice_cycle.py; no default database"
    assert os.environ.get("APP_ENV") == "test"
    assert os.environ.get("POSTING_ENABLED") == "false"
    target = make_url(explicit_url)
    assert target.get_backend_name() == "postgresql"
    assert target.host in {"localhost", "127.0.0.1", "::1"}
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", target.database or "")

    from app.config import POSTING_ENABLED
    from app.db import engine, get_db
    from app.main import app

    assert POSTING_ENABLED is False
    assert engine.url == target, "Application engine must use the runner's exact URL"
    assert get_db not in app.dependency_overrides
    ids = {key: uuid4() for key in ("owner", "branch", "territory", "customer")}
    token = uuid4()
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            assert (
                connection.execute(text("SELECT current_database()")).scalar_one()
                == target.database
            )
            with Session(
                bind=connection, join_transaction_mode="create_savepoint"
            ) as db:
                db.execute(
                    text(
                        "INSERT INTO platform.platform_user "
                        "(id,username,password_hash,role,is_owner) "
                        "VALUES (:id,:username,'unused','owner',true)"
                    ),
                    {"id": ids["owner"], "username": "customer_test_" + token.hex},
                )
                db.execute(
                    text(
                        "INSERT INTO master_data.master_branch(id,code,name_ar) "
                        "VALUES (:id,:code,'Synthetic branch')"
                    ),
                    {"id": ids["branch"], "code": ids["branch"].hex[:20]},
                )
                db.execute(
                    text(
                        "INSERT INTO master_data.master_territory(id,code,name_ar) "
                        "VALUES (:id,:code,'Synthetic territory')"
                    ),
                    {"id": ids["territory"], "code": ids["territory"].hex[:20]},
                )
                db.execute(
                    text(
                        "INSERT INTO master_data.master_customer "
                        "(id,code,name_ar,branch_id,territory_id) "
                        "VALUES (:customer,:code,'Original synthetic customer',"
                        ":branch,:territory)"
                    ),
                    {**ids, "code": ids["customer"].hex[:30]},
                )
                db.execute(
                    text(
                        "INSERT INTO platform.platform_session(id,user_id,expires_at) "
                        "VALUES (:sid,:uid,now() + interval '1 hour')"
                    ),
                    {"sid": token, "uid": ids["owner"]},
                )
                db.commit()

                def get_test_db():
                    yield db

                app.dependency_overrides[get_db] = get_test_db
                try:
                    with TestClient(app) as client:
                        auth = {"Authorization": f"Bearer {token}"}
                        yield client, db, ids, auth
                finally:
                    app.dependency_overrides.pop(get_db, None)
        finally:
            transaction.rollback()


def test_owner_updates_customer_display_names_with_actor_audit(customer_env):
    client, db, ids, auth = customer_env
    payload = {"name_ar": "عميل اختباري محدث", "name_en": "Updated synthetic customer"}
    response = client.patch(
        f"/master/customers/{ids['customer']}", json=payload, headers=auth
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(ids["customer"])
    assert body["name_ar"] == payload["name_ar"]
    assert body["name_en"] == payload["name_en"]

    stored = (
        db.execute(
            text(
                "SELECT code,name_ar,name_en,branch_id,territory_id,is_active "
                "FROM master_data.master_customer WHERE id=:id"
            ),
            {"id": ids["customer"]},
        )
        .mappings()
        .one()
    )
    assert stored["name_ar"] == payload["name_ar"]
    assert stored["name_en"] == payload["name_en"]
    assert stored["code"] == ids["customer"].hex[:30]
    assert stored["branch_id"] == ids["branch"]
    assert stored["territory_id"] == ids["territory"]
    assert stored["is_active"] is True

    lookup = client.get("/master/customers", headers=auth)
    assert lookup.status_code == 200, lookup.text
    selected = next(row for row in lookup.json() if row["id"] == body["id"])
    assert selected["name_ar"] == payload["name_ar"]
    assert selected["name_en"] == payload["name_en"]
    audit = (
        db.execute(
            text(
                "SELECT actor_user_id,action,old_values,new_values "
                "FROM audit.audit_log WHERE entity_type='master_customer' "
                "AND entity_id=:id"
            ),
            {"id": ids["customer"]},
        )
        .mappings()
        .one()
    )
    assert audit["actor_user_id"] == ids["owner"]
    assert audit["action"] == "updated"
    assert audit["old_values"]["name_ar"] == "Original synthetic customer"
    assert audit["new_values"]["name_ar"] == payload["name_ar"]
    assert audit["new_values"]["name_en"] == payload["name_en"]


def customer_snapshot(db, customer_id):
    params = {"id": customer_id}
    customer = dict(
        db.execute(
            text("SELECT * FROM master_data.master_customer WHERE id=:id"), params
        )
        .mappings()
        .one()
    )
    audits = [
        dict(row)
        for row in db.execute(
            text(
                "SELECT * FROM audit.audit_log "
                "WHERE entity_type='master_customer' AND entity_id=:id ORDER BY id"
            ),
            params,
        ).mappings()
    ]
    return customer, audits


def test_empty_customer_patch_is_rejected_without_write_or_audit(customer_env):
    client, db, ids, auth = customer_env
    before = customer_snapshot(db, ids["customer"])
    response = client.patch(
        f"/master/customers/{ids['customer']}", json={}, headers=auth
    )
    assert response.status_code == 422, response.text
    assert customer_snapshot(db, ids["customer"]) == before


def test_null_arabic_name_is_rejected_without_write_or_audit(customer_env):
    client, db, ids, auth = customer_env
    before = customer_snapshot(db, ids["customer"])
    response = client.patch(
        f"/master/customers/{ids['customer']}", json={"name_ar": None}, headers=auth
    )
    assert response.status_code == 422, response.text
    assert customer_snapshot(db, ids["customer"]) == before


@pytest.mark.parametrize(
    "field,value",
    [("name_ar", "  اسم جزئي  "), ("name_en", "  Partial name  "), ("name_en", None)],
)
def test_partial_customer_patch_preserves_other_fields_and_audits_actor(
    customer_env, field, value
):
    client, db, ids, auth = customer_env
    db.execute(
        text(
            "UPDATE master_data.master_customer SET name_en='Original English' WHERE id=:id"
        ),
        {"id": ids["customer"]},
    )
    db.commit()
    before, audits_before = customer_snapshot(db, ids["customer"])
    expected = value.strip() if value is not None else None
    response = client.patch(
        f"/master/customers/{ids['customer']}", json={field: value}, headers=auth
    )
    assert response.status_code == 200, response.text
    after, audits = customer_snapshot(db, ids["customer"])
    assert after == {**before, field: expected}
    assert response.json()[field] == expected
    assert not audits_before and len(audits) == 1
    audit = audits[0]
    assert audit["actor_user_id"] == ids["owner"]
    assert audit["action"] == "updated"
    assert audit["old_values"][field] == before[field]
    assert audit["new_values"][field] == expected
    other = "name_en" if field == "name_ar" else "name_ar"
    assert audit["new_values"][other] == before[other]


@pytest.mark.parametrize("authenticated", [False, True])
def test_customer_patch_requires_a_valid_session_without_side_effects(
    customer_env, authenticated
):
    client, db, ids, _auth = customer_env
    before = customer_snapshot(db, ids["customer"])
    headers = {"Authorization": f"Bearer {uuid4()}"} if authenticated else {}
    response = client.patch(
        f"/master/customers/{ids['customer']}",
        json={"name_ar": "Unauthorized change"},
        headers=headers,
    )
    # HTTPBearer used 403 before FastAPI standardized missing credentials to 401.
    assert response.status_code in ({401} if authenticated else {401, 403})
    assert customer_snapshot(db, ids["customer"]) == before


@pytest.mark.parametrize(
    "role,owner,active,status",
    [
        ("finance", False, True, 403),
        ("sales_rep", False, True, 403),
        ("read_only_auditor", False, True, 403),
        ("owner", False, True, 403),
        ("finance", True, True, 403),
        ("owner", True, False, 401),
    ],
)
def test_customer_patch_requires_active_owner_role_and_flag(
    customer_env, role, owner, active, status
):
    client, db, ids, auth = customer_env
    db.execute(
        text(
            "UPDATE platform.platform_user SET role=:role,is_owner=:owner,is_active=:active "
            "WHERE id=:id"
        ),
        {"id": ids["owner"], "role": role, "owner": owner, "active": active},
    )
    db.commit()
    before = customer_snapshot(db, ids["customer"])
    response = client.patch(
        f"/master/customers/{ids['customer']}",
        json={"name_ar": "Unauthorized change"},
        headers=auth,
    )
    assert response.status_code == status, response.text
    assert customer_snapshot(db, ids["customer"]) == before


@pytest.mark.parametrize("field", ["code", "actor_user_id"])
def test_customer_patch_rejects_protected_or_spoofed_fields(customer_env, field):
    client, db, ids, auth = customer_env
    before = customer_snapshot(db, ids["customer"])
    response = client.patch(
        f"/master/customers/{ids['customer']}",
        json={"name_ar": "Valid name", field: str(uuid4())},
        headers=auth,
    )
    assert response.status_code == 422, response.text
    assert customer_snapshot(db, ids["customer"]) == before


@pytest.mark.parametrize("insert_audit_first", [False, True])
def test_customer_patch_rolls_back_update_and_audit_on_failure(
    customer_env, monkeypatch, insert_audit_first
):
    from app.master import router as master_router

    client, db, ids, auth = customer_env
    before = customer_snapshot(db, ids["customer"])
    real_audit = master_router.log_audit

    def fail_audit(*args, **kwargs):
        if insert_audit_first:
            real_audit(*args, **kwargs)
        raise RuntimeError("synthetic customer audit failure")

    monkeypatch.setattr(master_router, "log_audit", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic customer audit failure"):
        client.patch(
            f"/master/customers/{ids['customer']}",
            json={"name_ar": "Must roll back"},
            headers=auth,
        )
    assert customer_snapshot(db, ids["customer"]) == before


def test_customer_patch_rolls_back_update_and_audit_when_commit_fails(
    customer_env, monkeypatch
):
    client, db, ids, auth = customer_env
    before = customer_snapshot(db, ids["customer"])

    def fail_commit():
        raise RuntimeError("synthetic customer commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="synthetic customer commit failure"):
        client.patch(
            f"/master/customers/{ids['customer']}",
            json={"name_en": "Must roll back"},
            headers=auth,
        )
    assert customer_snapshot(db, ids["customer"]) == before


def test_missing_customer_patch_returns_404_without_audit(customer_env):
    client, db, ids, auth = customer_env
    missing = uuid4()
    before = customer_snapshot(db, ids["customer"])
    response = client.patch(
        f"/master/customers/{missing}", json={"name_en": "Missing"}, headers=auth
    )
    assert response.status_code == 404, response.text
    assert customer_snapshot(db, ids["customer"]) == before
    assert (
        db.execute(
            text("SELECT count(*) FROM audit.audit_log WHERE entity_id=:id"),
            {"id": missing},
        ).scalar_one()
        == 0
    )
