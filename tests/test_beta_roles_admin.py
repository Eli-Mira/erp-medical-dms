"""Run only against a parent-created, migrated, task-owned disposable PostgreSQL DB.

Bind application configuration to that same DB before importing this module.
BETA_ROLES_TEST_DATABASE_URL must name dms_cycle_test_<unique suffix>.
The parent seeds at least two canonical branch records before running this module
and drops the entire database afterwards; immutable audit rows are not deleted.
"""

import os
import re
from uuid import UUID, uuid4

import pytest
from app.auth import repo
from app.auth.router import router
from app.db import get_db
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="module")
def database():
    value = os.environ.get("BETA_ROLES_TEST_DATABASE_URL")
    if not value:
        pytest.fail(
            "Set BETA_ROLES_TEST_DATABASE_URL to the task-owned disposable database"
        )
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or not bool(
        re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", url.database or "")
    ):
        pytest.fail("Refusing a database outside the dms_cycle_test_ namespace")
    engine = create_engine(url)
    sessions = sessionmaker(bind=engine)
    with engine.connect() as connection:
        actual = connection.execute(text("SELECT current_database()")).scalar_one()
        assert actual == url.database
        branches = (
            connection.execute(
                text("SELECT id FROM master_data.master_branch ORDER BY id LIMIT 2")
            )
            .scalars()
            .all()
        )
        assert len(branches) == 2, (
            "Parent must seed two canonical branches in this disposable DB"
        )
    try:
        yield sessions, [str(value) for value in branches]
    finally:
        engine.dispose()


@pytest.fixture
def case(database):
    sessions, branches = database
    suffix = uuid4().hex
    accounts = {}
    with sessions() as db:
        for label, role, owner in (
            ("owner", "owner", True),
            ("target", "medical_rep", False),
            ("denied", "admin", False),
        ):
            username = "beta_" + label + "_" + suffix
            repo.create_user(
                db,
                username,
                "test-only-not-a-provisioning-policy",
                role=role,
                is_owner=owner,
            )
            user = repo.get_user_by_username(db, username)
            sid = repo.create_session(db, user["id"])
            accounts[label] = {"id": str(user["id"]), "token": str(sid)}
        db.commit()
    app = FastAPI()
    app.include_router(router)

    def dependency():
        with sessions() as db:
            try:
                yield db
            finally:
                db.rollback()

    app.dependency_overrides[get_db] = dependency
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, sessions, accounts, branches


def headers(account):
    return {"Authorization": "Bearer " + account["token"]}


def body(role="sales_manager", active=True, branches=None):
    return {
        "role": role,
        "is_active": active,
        "branch_ids": [] if branches is None else branches,
    }


def snapshot(sessions, uid):
    with sessions() as db:
        user = repo.administration_users(db, uid)[0]
        tokens = (
            db.execute(
                text(
                    "SELECT id FROM platform.platform_session WHERE user_id=:id ORDER BY id"
                ),
                {"id": uid},
            )
            .scalars()
            .all()
        )
        audit = (
            db.execute(
                text(
                    "SELECT actor_user_id, action, old_values, new_values FROM audit.audit_log WHERE entity_type='platform_user' AND entity_id=:id ORDER BY created_at, id"
                ),
                {"id": uid},
            )
            .mappings()
            .all()
        )
        return user, [str(value) for value in tokens], [dict(row) for row in audit]


@pytest.mark.parametrize("active", [True, False])
def test_json_uuid_strings_persist_audit_and_revoke_all_sessions(case, active):
    client, sessions, accounts, branches = case
    target = accounts["target"]
    with sessions() as db:
        repo.create_session(db, target["id"])
        db.commit()
    before, tokens, _ = snapshot(sessions, target["id"])
    assert len(tokens) == 2
    # Exercise the HTTP JSON contract, not Python model validation with UUID objects.
    wire_branches = [value.upper() for value in reversed(branches)]
    assert all(isinstance(value, str) for value in wire_branches)
    response = client.put(
        "/auth/users/" + target["id"],
        headers=headers(accounts["owner"]),
        json=body(active=active, branches=wire_branches),
    )
    assert response.status_code == 200, response.text
    after, remaining, audit = snapshot(sessions, target["id"])
    assert after == response.json()
    assert after["role"] == "sales_manager"
    assert after["is_active"] is active
    assert after["branch_ids"] == sorted(str(UUID(value)) for value in wire_branches)
    assert remaining == []
    assert len(audit) == 1
    assert str(audit[0]["actor_user_id"]) == accounts["owner"]["id"]
    assert audit[0]["action"] == "updated"
    assert audit[0]["old_values"] == before
    assert audit[0]["new_values"] == after
    assert client.get("/auth/me", headers=headers(target)).status_code == 401
    assert set(after) == {
        "id",
        "username",
        "role",
        "is_owner",
        "is_active",
        "branch_ids",
    }
    assert "password_hash" not in response.text
    assert "access_token" not in response.text
    assert all(token not in response.text for token in tokens)


def test_owner_reads_safe_user_list_and_canonical_options(case):
    client, _, accounts, branches = case
    response = client.get("/auth/users", headers=headers(accounts["owner"]))
    assert response.status_code == 200, response.text
    for row in response.json():
        assert set(row) == {
            "id",
            "username",
            "role",
            "is_owner",
            "is_active",
            "branch_ids",
        }
    assert accounts["target"]["id"] in {row["id"] for row in response.json()}
    response = client.get("/auth/users/options", headers=headers(accounts["owner"]))
    assert response.status_code == 200, response.text
    from app.auth.rbac import ROLES

    assert response.json()["roles"] == list(ROLES)
    assert set(branches).issubset({row["id"] for row in response.json()["branches"]})


def test_branch_permission_loss_revokes_sessions(case):
    client, sessions, accounts, branches = case
    target = accounts["target"]
    with sessions() as db:
        db.execute(
            text(
                "INSERT INTO platform.user_branch (user_id, branch_id) VALUES (:uid, :bid)"
            ),
            {"uid": target["id"], "bid": branches[0]},
        )
        db.commit()
    response = client.put(
        "/auth/users/" + target["id"],
        headers=headers(accounts["owner"]),
        json=body(role="medical_rep"),
    )
    assert response.status_code == 200, response.text
    user, tokens, audit = snapshot(sessions, target["id"])
    assert user["branch_ids"] == []
    assert tokens == []
    assert audit[0]["old_values"]["branch_ids"] == [branches[0]]
    assert client.get("/auth/me", headers=headers(target)).status_code == 401


def test_non_owner_cannot_read_options_list_or_write(case):
    client, sessions, accounts, _ = case
    target = accounts["target"]
    before = snapshot(sessions, target["id"])
    for label in ("target", "denied"):
        auth = headers(accounts[label])
        assert client.get("/auth/users", headers=auth).status_code == 403
        assert client.get("/auth/users/options", headers=auth).status_code == 403
        assert (
            client.put(
                "/auth/users/" + target["id"], headers=auth, json=body()
            ).status_code
            == 403
        )
    assert snapshot(sessions, target["id"]) == before


@pytest.mark.parametrize(
    "extra",
    [
        {"is_owner": True},
        {"is_owner": False},
        {"actor_user_id": "forged-actor"},
        {"territory_ids": [str(uuid4())]},
        {"password_hash": "must-not-be-returned"},
        {"access_token": "must-not-be-returned"},
        {"unexpected": "must-not-be-returned"},
    ],
)
def test_valid_uuid_json_with_forged_or_extra_fields_is_rejected_without_echo(
    case, extra
):
    client, sessions, accounts, branches = case
    target = accounts["target"]
    before = snapshot(sessions, target["id"])
    response = client.put(
        "/auth/users/" + target["id"],
        headers=headers(accounts["owner"]),
        json={**body(branches=branches), **extra},
    )
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "Invalid user administration payload"}
    assert "must-not-be-returned" not in response.text
    assert "forged-actor" not in response.text
    assert snapshot(sessions, target["id"]) == before


@pytest.mark.parametrize(
    "change",
    [
        {"branch_ids": ["not-a-uuid"]},
        {"branch_ids": ["00000000-0000-0000-0000-00000000000z"]},
        {"branch_ids": [123]},
        {"branch_ids": [None]},
        {"branch_ids": "not-a-list"},
        {"branch_ids": None},
        {"is_active": "false"},
        {"is_active": 0},
        {"is_active": 1},
        {"is_active": None},
        {"role": 123},
    ],
)
def test_malformed_uuid_and_coercible_noncontract_values_do_not_write(case, change):
    client, sessions, accounts, branches = case
    target = accounts["target"]
    before = snapshot(sessions, target["id"])
    response = client.put(
        "/auth/users/" + target["id"],
        headers=headers(accounts["owner"]),
        json={**body(branches=branches), **change},
    )
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "Invalid user administration payload"}
    assert snapshot(sessions, target["id"]) == before


@pytest.mark.parametrize(
    "raw",
    [
        '{"role":',
        "null",
        "[]",
        "{}",
        '{"role":"sales_manager","is_active":true}',
    ],
)
def test_malformed_or_incomplete_json_does_not_write(case, raw):
    client, sessions, accounts, _ = case
    target = accounts["target"]
    before = snapshot(sessions, target["id"])
    response = client.put(
        "/auth/users/" + target["id"],
        headers={**headers(accounts["owner"]), "Content-Type": "application/json"},
        content=raw,
    )
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "Invalid user administration payload"}
    assert snapshot(sessions, target["id"]) == before


@pytest.mark.parametrize(
    "payload",
    [
        body(role="invented_role"),
        body(role="owner"),
        body(branches=[str(uuid4())]),
    ],
)
def test_invalid_roles_and_nonexistent_references_do_not_write(case, payload):
    client, sessions, accounts, _ = case
    target = accounts["target"]
    before = snapshot(sessions, target["id"])
    response = client.put(
        "/auth/users/" + target["id"], headers=headers(accounts["owner"]), json=payload
    )
    assert response.status_code == 422
    assert snapshot(sessions, target["id"]) == before


@pytest.mark.parametrize("oversized", [False, True])
def test_duplicate_normalized_or_oversized_branch_assignments_do_not_write(
    case, oversized
):
    client, sessions, accounts, branches = case
    target = accounts["target"]
    before = snapshot(sessions, target["id"])
    values = (
        [str(uuid4()) for _ in range(501)]
        if oversized
        else [branches[0], branches[0].upper()]
    )
    response = client.put(
        "/auth/users/" + target["id"],
        headers=headers(accounts["owner"]),
        json=body(branches=values),
    )
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "Invalid branch assignments"}
    assert snapshot(sessions, target["id"]) == before


def test_audit_failure_rolls_back_user_assignments_and_session_deletion(
    case, monkeypatch
):
    client, sessions, accounts, branches = case
    target = accounts["target"]
    before = snapshot(sessions, target["id"])

    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(repo, "log_audit", fail)
    response = client.put(
        "/auth/users/" + target["id"],
        headers=headers(accounts["owner"]),
        json=body(active=False, branches=branches),
    )
    assert response.status_code == 500
    assert snapshot(sessions, target["id"]) == before
    assert client.get("/auth/me", headers=headers(target)).status_code == 200


def test_noop_preserves_sessions_and_does_not_append_audit(case):
    client, sessions, accounts, _ = case
    target = accounts["target"]
    before = snapshot(sessions, target["id"])
    response = client.put(
        "/auth/users/" + target["id"],
        headers=headers(accounts["owner"]),
        json=body(role="medical_rep"),
    )
    assert response.status_code == 200, response.text
    assert snapshot(sessions, target["id"]) == before


@pytest.mark.parametrize(
    "payload", [body(role="admin"), body(role="owner", active=False)]
)
def test_self_lockout_is_rejected(case, payload):
    client, sessions, accounts, _ = case
    owner = accounts["owner"]
    before = snapshot(sessions, owner["id"])
    response = client.put(
        "/auth/users/" + owner["id"], headers=headers(owner), json=payload
    )
    assert response.status_code == 409
    assert snapshot(sessions, owner["id"]) == before


def test_self_branch_permission_loss_is_rejected(case):
    client, sessions, accounts, branches = case
    owner = accounts["owner"]
    with sessions() as db:
        db.execute(
            text(
                "INSERT INTO platform.user_branch (user_id, branch_id) VALUES (:uid, :bid)"
            ),
            {"uid": owner["id"], "bid": branches[0]},
        )
        db.commit()
    before = snapshot(sessions, owner["id"])
    response = client.put(
        "/auth/users/" + owner["id"], headers=headers(owner), json=body(role="owner")
    )
    assert response.status_code == 409
    assert snapshot(sessions, owner["id"]) == before


def test_disabling_another_owner_preserves_the_actor_owner(case):
    client, sessions, accounts, _ = case
    username = "beta_other_owner_" + uuid4().hex
    with sessions() as db:
        repo.create_user(db, username, "test-only", role="owner", is_owner=True)
        other = repo.get_user_by_username(db, username)
        uid = str(other["id"])
        sid = str(repo.create_session(db, uid))
        db.commit()
    response = client.put(
        "/auth/users/" + uid,
        headers=headers(accounts["owner"]),
        json=body(role="owner", active=False),
    )
    assert response.status_code == 200, response.text
    assert snapshot(sessions, uid)[1] == []
    assert (
        client.get("/auth/me", headers={"Authorization": "Bearer " + sid}).status_code
        == 401
    )
    assert client.get("/auth/me", headers=headers(accounts["owner"])).status_code == 200


def test_last_active_owner_cannot_be_disabled(case):
    client, sessions, accounts, _ = case
    owner = accounts["owner"]
    # This entire database belongs to this module and is dropped by the parent.
    with sessions() as db:
        db.execute(
            text(
                "UPDATE platform.platform_user SET is_active=false WHERE is_owner AND id<>:id"
            ),
            {"id": owner["id"]},
        )
        db.commit()
    before = snapshot(sessions, owner["id"])
    response = client.put(
        "/auth/users/" + owner["id"],
        headers=headers(owner),
        json=body(role="owner", active=False),
    )
    assert response.status_code == 409
    assert snapshot(sessions, owner["id"]) == before
    with sessions() as db:
        assert repo.active_owner_count(db) == 1
