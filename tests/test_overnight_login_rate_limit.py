"""Desired contracts; execute only through the approved isolated disposable runner."""

import importlib
import os
import re
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import repo
from app.db import engine, get_db
from app.main import app

auth_router = importlib.import_module("app.auth.router")


@pytest.fixture
def login_env(monkeypatch):
    # This module is not admitted by conftest's existing module-name guard.
    # Parent must additionally establish exact runner ownership before execution.
    assert os.environ.get("APP_ENV") == "test", "Use the approved isolated runner"
    database = engine.url.database
    assert database and re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", database)
    assert get_db not in app.dependency_overrides
    clock = [1000.0]
    if hasattr(auth_router, "login_limiter"):
        monkeypatch.setattr(
            auth_router,
            "login_limiter",
            type(auth_router.login_limiter)(clock=lambda: clock[0]),
        )
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT current_database()")).scalar_one()
            == database
        )
        connection.rollback()
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        names = {
            name: "limit_" + uuid4().hex for name in ("active", "other", "disabled")
        }
        for name in names.values():
            repo.create_user(db, name, "correct-password")
        db.execute(
            text("UPDATE platform.platform_user SET is_active=false WHERE username=:u"),
            {"u": names["disabled"]},
        )
        db.commit()

        def test_db():
            yield db

        app.dependency_overrides[get_db] = test_db
        try:
            with TestClient(app) as client:
                yield client, db, names, clock
        finally:
            app.dependency_overrides.pop(get_db, None)
            db.close()
            transaction.rollback()


def attempt(client, username, password="wrong-password", headers=None):
    return client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers=headers,
    )


@pytest.mark.parametrize("account", ["active", "disabled", "unknown"])
def test_tenth_failure_is_401_and_eleventh_attempt_is_429(login_env, account):
    client, _db, names, _clock = login_env
    username = names.get(account, "unknown_" + uuid4().hex)
    for _ in range(10):
        response = attempt(client, username)
        assert response.status_code == 401, response.text
        assert response.json() == {"detail": "invalid credentials"}
    response = attempt(client, username)
    assert response.status_code == 429, response.text
    assert response.json() == {"detail": "Too many login attempts"}
    assert response.headers["retry-after"] == "300"


def test_window_boundary_and_rejected_attempts_do_not_extend_lockout(login_env):
    client, _db, names, clock = login_env
    for _ in range(10):
        assert attempt(client, names["active"]).status_code == 401
    clock[0] += 299.999
    response = attempt(client, names["active"], "correct-password")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"
    clock[0] = 1300.0
    assert attempt(client, names["active"], "correct-password").status_code == 200


def test_username_spray_and_forwarded_headers_cannot_bypass_direct_peer_limit(
    login_env,
):
    client, _db, _names, _clock = login_env
    for index in range(50):
        response = attempt(
            client,
            "unknown_spray_" + str(index),
            headers={"X-Forwarded-For": "192.0.2." + str(index + 1)},
        )
        assert response.status_code == 401, response.text
    response = attempt(
        client,
        "unknown_spray_final",
        headers={"X-Forwarded-For": "198.51.100.1", "Forwarded": "for=203.0.113.1"},
    )
    assert response.status_code == 429, response.text
    assert response.headers["retry-after"] == "300"


def test_successful_logins_do_not_accumulate_ip_failures(login_env):
    client, _db, names, _clock = login_env
    for _ in range(55):
        response = attempt(client, names["active"], "correct-password")
        assert response.status_code == 200, response.text
    assert attempt(client, names["other"]).status_code == 401
    assert attempt(client, names["other"], "correct-password").status_code == 200


def test_success_cannot_erase_prior_failures_for_the_account(login_env):
    client, _db, names, _clock = login_env
    for _ in range(9):
        assert attempt(client, names["active"]).status_code == 401
    assert attempt(client, names["active"], "correct-password").status_code == 200
    assert attempt(client, names["active"]).status_code == 401
    assert attempt(client, names["active"], "correct-password").status_code == 429
    assert attempt(client, names["other"], "correct-password").status_code == 200


def test_disabled_correct_password_has_uniform_failure(login_env):
    client, _db, names, _clock = login_env
    disabled = attempt(client, names["disabled"], "correct-password")
    unknown = attempt(client, "unknown_" + uuid4().hex, "correct-password")
    wrong = attempt(client, names["active"])
    assert disabled.status_code == unknown.status_code == wrong.status_code == 401
    assert (
        disabled.json()
        == unknown.json()
        == wrong.json()
        == {"detail": "invalid credentials"}
    )


def test_real_uuid_session_me_logout_and_disabled_session_behavior(login_env):
    client, db, names, _clock = login_env
    response = attempt(client, names["active"], "correct-password")
    assert response.status_code == 200, response.text
    assert response.json()["token_type"] == "bearer"
    token = response.json()["access_token"]
    UUID(token)
    headers = {"Authorization": "Bearer " + token}
    assert client.get("/auth/me", headers=headers).json()["username"] == names["active"]
    db.execute(
        text("UPDATE platform.platform_user SET is_active=false WHERE username=:u"),
        {"u": names["active"]},
    )
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401
    db.execute(
        text("UPDATE platform.platform_user SET is_active=true WHERE username=:u"),
        {"u": names["active"]},
    )
    db.commit()
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert (
        client.get(
            "/auth/me", headers={"Authorization": "Bearer not-a-uuid"}
        ).status_code
        == 401
    )


def test_account_limit_applies_across_direct_peers():
    from app.auth.rate_limit import FailedLoginLimiter

    limiter = FailedLoginLimiter(clock=lambda: 1000.0)
    for index in range(10):
        ticket, retry = limiter.reserve("same-account", "192.0.2." + str(index + 1))
        assert ticket is not None and retry == 0
        limiter.complete(ticket, failed=True)
    ticket, retry = limiter.reserve("same-account", "198.51.100.1")
    assert ticket is None and retry == 300


def test_parallel_reservations_cannot_overshoot_account_threshold():
    from app.auth.rate_limit import FailedLoginLimiter

    limiter = FailedLoginLimiter(clock=lambda: 1000.0)
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(
            executor.map(lambda _: limiter.reserve("account", "192.0.2.1"), range(64))
        )
    admitted = [ticket for ticket, retry in results if ticket is not None]
    assert len(admitted) == 10
    assert all(retry == 300 for ticket, retry in results if ticket is None)
    for ticket in admitted:
        limiter.complete(ticket, failed=False)
    ticket, retry = limiter.reserve("account", "192.0.2.1")
    assert ticket is not None and retry == 0


def test_state_capacity_fails_closed_without_evicting_active_failures_and_recovers():
    from app.auth.rate_limit import MAX_BUCKETS, FailedLoginLimiter

    clock = [1000.0]
    limiter = FailedLoginLimiter(clock=lambda: clock[0])
    for index in range(MAX_BUCKETS // 2):
        ticket, retry = limiter.reserve("account-" + str(index), "peer-" + str(index))
        assert ticket is not None and retry == 0
        limiter.complete(ticket, failed=True)
    assert len(limiter._buckets) == MAX_BUCKETS
    ticket, retry = limiter.reserve("new-account", "new-peer")
    assert ticket is None and retry == 300
    assert len(limiter._buckets) == MAX_BUCKETS
    clock[0] = 1300.0
    ticket, retry = limiter.reserve("new-account", "new-peer")
    assert ticket is not None and retry == 0
    assert len(limiter._buckets) == 2


def test_expired_completion_cannot_remove_new_reservations():
    from app.auth.rate_limit import FailedLoginLimiter

    clock = [1000.0]
    limiter = FailedLoginLimiter(clock=lambda: clock[0])
    old, _retry = limiter.reserve("account", "peer")
    clock[0] = 1300.0
    for _ in range(10):
        ticket, retry = limiter.reserve("account", "peer")
        assert ticket is not None and retry == 0
    limiter.complete(old, failed=False)
    ticket, retry = limiter.reserve("account", "peer")
    assert ticket is None and retry == 300
