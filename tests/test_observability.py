"""Observability tests: /livez, /readyz, X-Request-ID correlation, and JSON logs."""

import io
import json
import logging
from logging.config import fileConfig
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, http_logger
from app.observability import JsonLogFormatter, configure_handler_formatters


def test_livez_returns_alive_and_security_headers():
    with TestClient(app) as client:
        resp = client.get("/livez", headers={"X-Request-ID": "req-livez-123"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}
    assert resp.headers["X-Request-ID"] == "req-livez-123"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in resp.headers


def test_malicious_request_id_is_rejected_and_replaced():
    with TestClient(app) as client:
        resp = client.get("/livez", headers={"X-Request-ID": "bad\r\nid!@#" * 10})
    assert resp.status_code == 200
    req_id = resp.headers["X-Request-ID"]
    assert len(req_id) == 32
    assert req_id.isalnum()


def test_readyz_reports_ok_on_migrated_db():
    with TestClient(app) as client:
        resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "db": "ok"}


def test_readyz_returns_503_on_db_failure_without_secret_leak(monkeypatch):
    def _boom():
        raise RuntimeError("postgresql://secret_user:secret_pass@internal:5432/db")

    monkeypatch.setattr("app.main.engine.connect", _boom)
    with TestClient(app) as client:
        resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready", "db": "unavailable"}
    assert "secret_pass" not in resp.text
    assert "postgresql://" not in resp.text


def test_json_log_formatter_emits_single_line_and_redacts_auth():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonLogFormatter())
    http_logger.addHandler(handler)
    try:
        with TestClient(app) as client:
            resp = client.get(
                "/livez?token=should_not_log",
                headers={
                    "X-Request-ID": "trace-abc-99",
                    "Authorization": "Bearer supersecret_token_value",
                },
            )
            assert resp.status_code == 200
    finally:
        http_logger.removeHandler(handler)

    lines = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    assert any(
        item["request_id"] == "trace-abc-99"
        and item["path"] == "/livez"
        and item["status_code"] == 200
        for item in lines
    )
    raw_log = buf.getvalue()
    assert "supersecret_token_value" not in raw_log
    assert "should_not_log" not in raw_log


def test_text_log_formatter_supplies_request_id_and_survives_alembic_fileconfig(
    monkeypatch,
):
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    fileConfig(str(alembic_ini), disable_existing_loggers=False)
    assert http_logger.disabled is False

    monkeypatch.setenv("LOG_FORMAT", "text")
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    http_logger.addHandler(handler)
    configure_handler_formatters(http_logger)
    try:
        http_logger.info("startup_check")
        with TestClient(app) as client:
            resp = client.get("/livez", headers={"X-Request-ID": "trace-text-42"})
            assert resp.status_code == 200
    finally:
        http_logger.removeHandler(handler)
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        configure_handler_formatters(http_logger)

    output = buf.getvalue()
    assert "req=- startup_check" in output
    assert "req=trace-text-42 http_request" in output
