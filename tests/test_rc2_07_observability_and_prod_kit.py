import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as app_main
import app.db as app_db


def test_livez_and_readyz_and_request_id():
    client = TestClient(app_main.app)

    # /livez default
    resp = client.get("/livez")
    assert resp.status_code == 200
    json_body = resp.json()
    assert json_body.get("status") == "alive"
    assert "X-Request-ID" in resp.headers
    assert resp.headers["X-Request-ID"]

    # /livez with explicit request id
    custom_id = "trace-abc-123"
    resp = client.get("/livez", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id

    # /readyz
    resp = client.get("/readyz")
    assert resp.status_code == 200
    json_body = resp.json()
    assert json_body.get("status") == "ready"
    assert json_body.get("db") == "ok"

    # /health
    resp = client.get("/health")
    assert resp.status_code == 200
    json_body = resp.json()
    assert json_body.get("status") == "ok"


def test_readyz_returns_503_without_leaking_credentials_on_db_error(monkeypatch):
    def raise_error(*args, **kwargs):
        raise RuntimeError(
            "postgresql://secret_user:TOP_SECRET_PW@127.0.0.1/db"
        )

    monkeypatch.setattr(app_db.engine, "connect", raise_error)

    client = TestClient(app_main.app)
    resp = client.get("/readyz")
    assert resp.status_code == 503
    assert "TOP_SECRET_PW" not in resp.text
    json_body = resp.json()
    assert json_body.get("status") == "degraded"


def test_dockerfile_non_root_and_healthcheck():
    dockerfile_path = Path(__file__).resolve().parents[1] / "Dockerfile"
    content = dockerfile_path.read_text()

    assert "USER app" in content
    assert "HEALTHCHECK" in content
    assert "/livez" in content
    assert "alembic" in content


def test_requirements_pinned():
    req_path = Path(__file__).resolve().parents[1] / "requirements.txt"
    lines = req_path.read_text().splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # must contain exact pinning with ==
        assert "==" in stripped, f"Requirement not pinned exactly: {stripped}"
        # must not contain any loose specifiers
        for bad in (">=", "<=", "~=", "!=", ">", "<"):
            assert bad not in stripped, f"Loose specifier in requirement: {stripped}"


def test_compose_prod_hardened_and_zero_secrets():
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.prod.yml"
    content = compose_path.read_text()

    lowered = content.lower()
    assert "no-new-privileges:true" in lowered
    assert "cap_drop" in lowered
    assert "read_only: true" in lowered
    assert "127.0.0.1:" in content
    assert "POSTING_ENABLED" in content

    for line in content.splitlines():
        if "PASSWORD" in line and ":" in line:
            key, val = line.split(":", 1)
            val = val.strip()
            assert val.startswith("${") and val.endswith("}"), f"Password not env placeholder: {line}"

    assert "eyJ" not in content


def test_db_pool_and_alembic_logger_preservation():
    # Verify pre_ping is enabled on the pool
    assert getattr(app_db.engine.pool, "_pre_ping", False) is True

    env_path = Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    content = env_path.read_text()
    assert "disable_existing_loggers=False" in content


def test_cloudflare_runbook_covers_eli_a7():
    runbook_path = (
        Path(__file__).resolve().parents[1] / "docs" / "CLOUDFLARE_FREE_TUNNEL_RUNBOOK.md"
    )
    content = runbook_path.read_text(encoding="utf-8")

    # 2FA mention
    assert re.search(r"2FA|2.?Factor", content, re.IGNORECASE)

    # recovery codes mention
    assert "recovery codes" in content.lower()

    # LAN / loopback UAT fallback mention
    assert re.search(r"LAN|loopback", content, re.IGNORECASE)
    assert "uat" in content.lower() and "fallback" in content.lower()

    # Ensure no hard‑coded secrets appear in the repo
    assert not re.search(r"TOP_SECRET_PW|eyJ", content)
    # Zero secrets documented – we just ensure the file does not contain any secret literals
    assert "no tunnel tokens" in content.lower() or "zero secrets" in content.lower()
