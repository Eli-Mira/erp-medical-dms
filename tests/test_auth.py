"""Auth + session integration tests (P2.4 / P2.6).

Runs only in the approved disposable database. UUID-scoped test users are
deactivated; immutable audit rows and their actors live until database removal."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.security import hash_password
from app.db import SessionLocal
from app.main import app

client = TestClient(app)


def _seed(username: str, password: str = "p@ss123") -> None:
    db = SessionLocal()
    db.execute(
        text(
            "INSERT INTO platform.platform_user "
            "(id, username, password_hash, role, is_owner, is_active, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :u, :p, :role, :owner, true, now(), now())"
        ),
        {"u": username, "p": hash_password(password), "role": "user", "owner": False},
    )
    db.commit()
    db.close()


def _cleanup(username: str) -> None:
    db = SessionLocal()
    # Keep audit history and its actor FK; the runner removes this entire database.
    db.execute(
        text("UPDATE platform.platform_user SET is_active=false WHERE username = :u"),
        {"u": username},
    )
    db.commit()
    db.close()


def test_login_me_logout_happy_path():
    uname = f"test_{uuid.uuid4().hex[:8]}"
    _seed(uname, "p@ss123")
    try:
        r = client.post("/auth/login", json={"username": uname, "password": "p@ss123"})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == uname
        assert me.json()["is_owner"] is False

        lo = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert lo.status_code == 200

        # session invalidated after logout
        me2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me2.status_code == 401
    finally:
        _cleanup(uname)


def test_login_bad_password_rejected():
    uname = f"test_{uuid.uuid4().hex[:8]}"
    _seed(uname, "p@ss123")
    try:
        r = client.post("/auth/login", json={"username": uname, "password": "wrong"})
        assert r.status_code == 401
    finally:
        _cleanup(uname)


def test_login_unknown_user_rejected():
    r = client.post("/auth/login", json={"username": "nobody_zzz", "password": "x"})
    assert r.status_code == 401


def test_logout_without_token_does_not_crash():
    r = client.post("/auth/logout")
    assert r.status_code == 401  # HTTPBearer rejects a missing bearer token


# --- P2.5 RBAC: private/owner boundary (D10) ---
def _seed_owner(username: str, password: str = "p@ss123") -> None:
    db = SessionLocal()
    db.execute(
        text(
            "INSERT INTO platform.platform_user "
            "(id, username, password_hash, role, is_owner, is_active, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :u, :p, :role, :owner, true, now(), now())"
        ),
        {"u": username, "p": hash_password(password), "role": "user", "owner": True},
    )
    db.commit()
    db.close()


def test_owner_boundary_user_forbidden():
    # D10: non-owner accounts must NOT reach the owner-only panel.
    uname = f"test_{uuid.uuid4().hex[:8]}"
    _seed(uname, "p@ss123")
    try:
        r = client.post("/auth/login", json={"username": uname, "password": "p@ss123"})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        r2 = client.get("/owner/panel", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 403
    finally:
        _cleanup(uname)


def test_owner_boundary_owner_allowed():
    # D10: owner accounts DO reach the owner-only panel.
    uname = f"test_{uuid.uuid4().hex[:8]}"
    _seed_owner(uname, "p@ss123")
    try:
        r = client.post("/auth/login", json={"username": uname, "password": "p@ss123"})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        r2 = client.get("/owner/panel", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["user"] == uname
    finally:
        _cleanup(uname)
