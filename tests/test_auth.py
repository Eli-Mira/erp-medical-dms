"""Auth + session integration tests (P2.4 / P2.6).

Runs against the dev DB (docker). Seeds + deletes a per-test user (uuid-scoped
username) so the real DB is never polluted."""
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
    # Remove this test user's audit rows first: audit_log.actor_user_id →
    # platform_user.id (FK, immutable per §10), so the user can't be hard-deleted
    # while audit rows reference it. Test-only cleanup of test-generated rows.
    db.execute(
        text("DELETE FROM audit.audit_log WHERE actor_user_id IN "
             "(SELECT id FROM platform.platform_user WHERE username = :u)"),
        {"u": username},
    )
    db.execute(text("DELETE FROM platform.platform_user WHERE username = :u"), {"u": username})
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
