import uuid
from sqlalchemy import text
from app.auth import repo
from app.auth.router import _resolve_client_ip, login_limiter
from test_invoice_api import invoice_env  # noqa: F401

from types import SimpleNamespace

def test_resolve_client_ip_ignores_spoofed_headers_when_untrusted(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "")
    req = SimpleNamespace(
        client=SimpleNamespace(host="198.51.100.10"),
        headers={"x-forwarded-for": "203.0.113.9", "cf-connecting-ip": "203.0.113.8"},
    )
    assert _resolve_client_ip(req) == ("198.51.100.10", "198.51.100.10")

def test_resolve_client_ip_honors_forwarded_headers_from_trusted_proxy(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "127.0.0.1,10.0.0.0/8")
    req_cf = SimpleNamespace(
        client=SimpleNamespace(host="10.1.2.3"),
        headers={"cf-connecting-ip": "203.0.113.42"},
    )
    assert _resolve_client_ip(req_cf) == ("203.0.113.42", "203.0.113.42")
    req_xff = SimpleNamespace(
        client=SimpleNamespace(host="10.1.2.3"),
        headers={"x-forwarded-for": "198.51.100.7, 203.0.113.55, 10.9.9.9"},
    )
    assert _resolve_client_ip(req_xff) == ("203.0.113.55", "203.0.113.55")

def test_unauthenticated_user_admin_returns_401_before_422(invoice_env):
    client, db, ids, _, headers = invoice_env
    resp = client.put(
        f"/auth/users/{uuid.uuid4()}",
        content=b"{invalid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code in (401, 403)

def test_failed_login_and_login_logout_audited_with_ua_and_no_password(invoice_env):
    client, db, ids, _, headers = invoice_env
    # reset limiter state
    if hasattr(login_limiter, "reset"):
        login_limiter.reset()
    elif hasattr(login_limiter, "_attempts"):
        login_limiter._attempts.clear()
    # failed login attempt
    resp = client.post(
        "/auth/login",
        json={"username": "ghost_rc204", "password": "SUPER_SECRET_WRONG_PW_999"},
        headers={"User-Agent": "RC204-Agent/1.0"},
    )
    assert resp.status_code == 401
    row = db.execute(
        text(
            "SELECT actor_user_id, user_agent, new_values FROM audit.audit_log "
            "WHERE action = 'login_failed' ORDER BY created_at DESC LIMIT 1"
        )
    ).fetchone()
    assert row is not None
    assert row.actor_user_id is None
    assert row.user_agent == "RC204-Agent/1.0"
    new_vals = row.new_values
    assert new_vals["username"] == "ghost_rc204"
    assert "SUPER_SECRET_WRONG_PW_999" not in str(new_vals)
    # create a temporary user
    uname = f"rc204_{uuid.uuid4().hex[:8]}"
    repo.create_user(db, uname, "StrongPass!2026", role="sales_manager", is_owner=False)
    db.commit()
    # successful login
    resp = client.post(
        "/auth/login",
        json={"username": uname, "password": "StrongPass!2026"},
        headers={"User-Agent": "RC204-Login/2.0"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    row = db.execute(
        text(
            "SELECT user_agent FROM audit.audit_log WHERE action = 'login' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    ).fetchone()
    assert row is not None
    assert row.user_agent == "RC204-Login/2.0"
    # logout
    resp = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "RC204-Logout/3.0"},
    )
    assert resp.status_code == 200
    row = db.execute(
        text(
            "SELECT user_agent FROM audit.audit_log WHERE action = 'logout' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    ).fetchone()
    assert row is not None
    assert row.user_agent == "RC204-Logout/3.0"
