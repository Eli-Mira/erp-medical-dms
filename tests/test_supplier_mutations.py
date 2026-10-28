"""Supplier lifecycle, permissions and audit snapshots on disposable PostgreSQL."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db import engine


@pytest.fixture(autouse=True)
def disposable_supplier_database():
    assert os.environ.get("APP_ENV") == "test", "Use scripts/verify_invoice_cycle.py"
    assert engine.url.database.startswith("dms_cycle_test_")


@pytest.fixture
def supplier_env(posting_env):
    client, db, ids, auth, *_ = posting_env
    result = client.post(
        "/master/suppliers",
        headers=auth,
        json={
            "code": "S-" + uuid4().hex[:20],
            "name_ar": "Synthetic supplier",
        },
    )
    assert result.status_code == 201, result.text
    return client, db, ids, auth, result.json()


def record(db, sid):
    return dict(
        db.execute(
            text(
                "SELECT id,code,name_ar,name_en,contact_phone,address,is_active "
                "FROM master_data.master_supplier WHERE id=:id"
            ),
            {"id": sid},
        )
        .mappings()
        .one()
    )


def audit(db, sid, action):
    return (
        db.execute(
            text(
                "SELECT actor_user_id,old_values,new_values FROM audit.audit_log "
                "WHERE entity_type='master_supplier' AND entity_id=:id AND action=:action"
            ),
            {"id": sid, "action": action},
        )
        .mappings()
        .one()
    )


def test_patch_updates_supplier_with_audit_old_new_values(supplier_env):
    client, db, ids, auth, created = supplier_env
    response = client.patch(
        f"/master/suppliers/{created['id']}",
        headers=auth,
        json={"contact_phone": "+20-100-1234", "address": "Synthetic address"},
    )
    assert response.status_code == 200, response.text
    expected = {
        **created,
        "contact_phone": "+20-100-1234",
        "address": "Synthetic address",
    }
    assert response.json() == expected
    stored = record(db, created["id"])
    assert str(stored.pop("id")) == created["id"]
    assert {"id": created["id"], **stored} == expected
    row = audit(db, created["id"], "updated")
    assert row["actor_user_id"] == ids["owner"]
    assert row["old_values"] == created
    assert row["new_values"] == expected


def test_delete_is_soft_idempotent_and_reactivation_retains_identity(supplier_env):
    client, db, ids, auth, created = supplier_env
    path = f"/master/suppliers/{created['id']}"
    for _ in range(2):
        response = client.delete(path, headers=auth)
        assert response.status_code == 204, response.text
        assert response.content == b""
    inactive = {**created, "is_active": False}
    assert client.get(path, headers=auth).json() == inactive
    assert record(db, created["id"])["is_active"] is False
    assert created["id"] not in {
        r["id"] for r in client.get("/master/suppliers", headers=auth).json()
    }
    row = audit(db, created["id"], "deactivated")
    assert row["actor_user_id"] == ids["owner"]
    assert row["old_values"] == created
    assert row["new_values"] == inactive
    response = client.patch(path, headers=auth, json={"is_active": True})
    assert response.status_code == 200, response.text
    assert response.json() == created
    assert record(db, created["id"])["is_active"] is True
    row = audit(db, created["id"], "updated")
    assert row["old_values"] == inactive
    assert row["new_values"] == created
    assert created["id"] in {
        r["id"] for r in client.get("/master/suppliers", headers=auth).json()
    }


@pytest.mark.parametrize("method", ["patch", "delete"])
@pytest.mark.parametrize(
    "role,flag,active",
    [
        ("finance", False, True),
        ("finance", True, True),
        ("admin", False, True),
        ("read_only_auditor", False, True),
        ("medical_rep", False, True),
        ("owner", False, True),
        ("owner", True, False),
    ],
)
def test_mutations_deny_nonowners_and_disabled_accounts(
    supplier_env, method, role, flag, active
):
    client, db, _ids, _auth, created = supplier_env
    uid, sid = uuid4(), uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner,is_active) "
            "VALUES (:id,:u,'unused',:r,:o,:a)"
        ),
        {"id": uid, "u": uid.hex, "r": role, "o": flag, "a": active},
    )
    db.execute(
        text(
            "INSERT INTO platform.platform_session(id,user_id,expires_at) "
            "VALUES (:s,:u,now()+interval '1 hour')"
        ),
        {"s": sid, "u": uid},
    )
    db.commit()
    kwargs = {"headers": {"Authorization": f"Bearer {sid}"}}
    if method == "patch":
        kwargs["json"] = {"name_ar": "Forbidden change"}
    response = getattr(client, method)(f"/master/suppliers/{created['id']}", **kwargs)
    assert response.status_code == (403 if active else 401), response.text
    assert record(db, created["id"])["name_ar"] == created["name_ar"]
    assert record(db, created["id"])["is_active"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"code": None},
        {"name_ar": None},
        {"is_active": None},
        {"code": " "},
        {"name_ar": ""},
        {"code": "X" * 31},
        {"name_ar": "X" * 201},
        {"is_active": "true"},
        {"is_active": 1},
        {"id": "forged"},
        {"created_at": "2026-01-01"},
        {"actor_user_id": "forged"},
    ],
)
def test_patch_rejects_invalid_and_server_controlled_fields(supplier_env, payload):
    client, db, _ids, auth, created = supplier_env
    response = client.patch(
        f"/master/suppliers/{created['id']}", json=payload, headers=auth
    )
    assert response.status_code == 422, response.text
    stored = record(db, created["id"])
    assert str(stored.pop("id")) == created["id"]
    assert {"id": created["id"], **stored} == created
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM audit.audit_log "
                "WHERE entity_type='master_supplier' AND entity_id=:id"
            ),
            {"id": created["id"]},
        ).scalar_one()
        == 1
    )


def test_patch_duplicate_code_rolls_back(supplier_env):
    client, db, _ids, auth, created = supplier_env
    other = client.post(
        "/master/suppliers",
        headers=auth,
        json={"code": "OTHER-" + uuid4().hex[:15], "name_ar": "Other synthetic"},
    ).json()
    response = client.patch(
        f"/master/suppliers/{other['id']}", json={"code": created["code"]}, headers=auth
    )
    assert response.status_code == 409, response.text
    assert record(db, other["id"])["code"] == other["code"]
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM audit.audit_log "
                "WHERE entity_type='master_supplier' AND entity_id=:id"
            ),
            {"id": other["id"]},
        ).scalar_one()
        == 1
    )


def test_patch_can_clear_nullable_fields(supplier_env):
    client, _db, _ids, auth, created = supplier_env
    path = f"/master/suppliers/{created['id']}"
    assert (
        client.patch(path, json={"name_en": "Optional"}, headers=auth).status_code
        == 200
    )
    response = client.patch(path, json={"name_en": None}, headers=auth)
    assert response.status_code == 200, response.text
    assert response.json()["name_en"] is None


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
@pytest.mark.parametrize(
    "identifier,status",
    [
        ("00000000-0000-0000-0000-000000000000", 404),
        ("not-a-uuid", 422),
    ],
)
def test_missing_and_malformed_ids(posting_env, method, identifier, status):
    client, _db, _ids, auth, *_ = posting_env
    kwargs = {"headers": auth}
    if method == "patch":
        kwargs["json"] = {"contact_phone": "x"}
    response = getattr(client, method)(f"/master/suppliers/{identifier}", **kwargs)
    assert response.status_code == status, response.text
