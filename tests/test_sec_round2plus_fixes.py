import json
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

# Provided fixture that supplies the testing environment.
from test_invoice_api import invoice_env  # noqa: F401


def _role_headers(db: Session, role: str) -> dict:
    """
    Create a temporary user with the given role, generate a session token,
    commit everything and return an Authorization header.
    """
    user_id = uuid4()
    # Insert user – the actual columns may vary; include required fields.
    db.execute(
        text(
            """
            INSERT INTO platform.platform_user
                (id, username, password_hash, role, is_owner, is_active, created_at, updated_at)
            VALUES
                (:id, :username, :pwd, :role, false, true, now(), now())
            """
        ),
        {
            "id": str(user_id),
            "username": f"{role}_{uuid4()}",
            # Dummy hash – login will never be attempted with this user.
            "pwd": "not_used",
            "role": role,
        },
    )
    # Insert a session for the user.
    session_id = uuid4()
    db.execute(
        text(
            """
            INSERT INTO platform.platform_session
                (id, user_id, expires_at, created_at)
            VALUES
                (:sid, :uid, now() + interval '1 hour', now())
            """
        ),
        {"sid": str(session_id), "uid": str(user_id)},
    )
    db.commit()
    return {"Authorization": f"Bearer {session_id}"}


def test_p1_h01_audit_excludes_private_accounts_for_non_owners(invoice_env):
    client, db, ids, payload, headers = invoice_env

    # Owner creates a private account entry.
    resp = client.post(
        "/private-accounts",
        json={
            "account_label": "VAULT_H01",
            "entry_date": "2026-11-21",
            "debit": "100.00",
            "credit": "0.00",
        },
        headers=headers("owner"),
    )
    assert resp.status_code == 201

    # Owner can see it in the audit endpoint.
    resp = client.get("/audit?entity_type=private_account_entry", headers=headers("owner"))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1

    # Non‑owner roles must not see any private‑account audit rows.
    for role in ("finance", "read_only_auditor"):
        role_hdr = _role_headers(db, role)
        # General audit – must contain no entity_type that starts with "private_account".
        resp_all = client.get("/audit", headers=role_hdr)
        assert resp_all.status_code == 200
        for row in resp_all.json():
            assert not str(row.get("entity_type", "")).startswith("private_account")

        # Filtered audit – must be an empty list.
        resp_filtered = client.get(
            "/audit?entity_type=private_account_entry", headers=role_hdr
        )
        assert resp_filtered.status_code == 200
        assert resp_filtered.json() == []


def test_p1_h02_over_return_rejected_on_invoice(invoice_env):
    client, db, ids, payload, headers = invoice_env

    # Create a draft invoice.
    resp = client.post("/invoices", json=payload, headers=headers("owner"))
    assert resp.status_code == 201
    inv_id = resp.json()["id"]

    # Quantity that was invoiced (as Decimal).
    invoiced_qty = Decimal(str(payload["lines"][0]["quantity"]))

    # Attempt to return more than invoiced → 422.
    resp = client.post(
        "/returns",
        json={
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "quantity": str(invoiced_qty + Decimal("5")),
            "return_date": "2026-11-21",
            "invoice_id": inv_id,
        },
        headers=headers("owner"),
    )
    assert resp.status_code == 422

    # Return exactly the invoiced quantity → 201.
    resp = client.post(
        "/returns",
        json={
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "quantity": str(invoiced_qty),
            "return_date": "2026-11-21",
            "invoice_id": inv_id,
        },
        headers=headers("owner"),
    )
    assert resp.status_code == 201

    # Any further return on the same invoice should be rejected → 422.
    resp = client.post(
        "/returns",
        json={
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "quantity": "1",
            "return_date": "2026-11-21",
            "invoice_id": inv_id,
        },
        headers=headers("owner"),
    )
    assert resp.status_code == 422


def test_p1_m01_reason_codes_rejects_bad_types_422(invoice_env):
    client, db, ids, payload, headers = invoice_env

    # Bad type for code (int instead of str)
    resp = client.post(
        "/reason-codes", json={"code": 12345}, headers=headers("owner")
    )
    assert resp.status_code == 422

    # Bad type for name_ar (list instead of str)
    resp = client.post(
        "/reason-codes",
        json={"code": "RC_BAD", "name_ar": ["bad"]},
        headers=headers("owner"),
    )
    assert resp.status_code == 422

    # Unexpected extra field
    resp = client.post(
        "/reason-codes",
        json={"code": "RC_EXTRA", "unknown": "x"},
        headers=headers("owner"),
    )
    assert resp.status_code == 422


def test_p1_m02_request_body_size_and_field_caps(invoice_env):
    client, db, ids, payload, headers = invoice_env

    # 1. Oversized raw body (greater than 1 MB) → 413.
    large_body = b'{"a":"' + b"x" * 1_150_000 + b'"}'
    resp = client.post(
        "/master/customers",
        content=large_body,
        headers={
            **headers("owner"),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 413

    # 2. Oversized address field (1000 characters) → 422.
    resp = client.post(
        "/master/customers",
        json={"name": "BigAddrCo", "address": "A" * 1000, "phone": "123"},
        headers=headers("owner"),
    )
    assert resp.status_code == 422

    # 3. Oversized return reason (1000 characters) → 422.
    resp = client.post(
        "/returns",
        json={
            "customer_id": str(ids["customer"]),
            "product_id": str(ids["product"]),
            "warehouse_id": str(ids["warehouse"]),
            "quantity": "1",
            "return_date": "2026-11-21",
            "reason": "R" * 1000,
        },
        headers=headers("owner"),
    )
    assert resp.status_code == 422


def test_p1_m03_header_nul_byte_rejected_422():
    # Directly invoke the ASGI app to ensure a NUL byte in the header is processed.
    import asyncio
    from app.main import app

    async def _call_app():
        status = None

        # Minimal HTTP scope with a bad header containing a NUL byte.
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "method": "GET",
            "path": "/health",
            "query_string": b"",
            "headers": [(b"user-agent", b"bad\x00ua")],
            "client": ("testclient", 12345),
            "server": ("testserver", 80),
        }

        async def receive():
            return {"type": "http.request"}

        async def send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]

        await app(scope, receive, send)
        return status

    status_code = asyncio.run(_call_app())
    assert status_code == 422


def test_p1_m04_csv_formula_neutralization():
    from app.finance.exports import cell

    dangerous = [
        "=CMD|x",
        "+1+1",
        "-1+1",
        "@SUM(1,1)",
        "\t=1+1",
        "\r=1+1",
        "\n=1+1",
        " =1+1",
        "   +1+1",
    ]
    for value in dangerous:
        assert cell(value).startswith("'")

    # Normal numeric strings are left untouched.
    assert cell("-123.45") == "-123.45"
    assert cell("100.00") == "100.00"


def test_p1_m05_idle_13h_session_rejected(invoice_env):
    client, db, ids, payload, headers = invoice_env

    # Insert a user with a known password.
    from app.auth.security import hash_password

    uname = f"idle_user_{uuid4().hex[:10]}"
    pwd_raw = "IdleTest#2026!"
    pwd_hash = hash_password(pwd_raw)

    user_id = uuid4()
    db.execute(
        text(
            """
            INSERT INTO platform.platform_user
                (id, username, password_hash, role, is_owner, is_active, created_at, updated_at)
            VALUES
                (:id, :username, :pwd, :role, false, true, now(), now())
            """
        ),
        {
            "id": str(user_id),
            "username": uname,
            "pwd": pwd_hash,
            "role": "finance",
        },
    )
    db.commit()

    # Perform login to obtain a token.
    resp = client.post(
        "/auth/login",
        json={"username": uname, "password": pwd_raw},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Locate the session created for this login.
    sess_id = db.scalar(
        select(text("id"))
        .select_from(text("platform.platform_session"))
        .where(text("user_id = :uid")),
        {"uid": str(user_id)},
    )
    assert sess_id is not None

    # Push `created_at` back 13 hours, keep `expires_at` in the future.
    db.execute(
        text(
            """
            UPDATE platform.platform_session
            SET created_at = now() - interval '13 hours',
                expires_at = now() + interval '11 hours'
            WHERE id = :sid
            """
        ),
        {"sid": str(sess_id)},
    )
    db.commit()

    # The stale session must now be rejected.
    resp = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


def test_p1_m06_telegram_bot_mention_boundary():
    aiogram_bot = pytest.importorskip("app.telegram.aiogram_bot")

    # Mention that should be considered *not* a bot call.
    assert not aiogram_bot._has_bot_mention(
        "@elsebaey_erp_bot_fake /sales", "elsebaey_erp_bot"
    )

    # Proper mention.
    assert aiogram_bot._has_bot_mention(
        "@elsebaey_erp_bot /sales", "elsebaey_erp_bot"
    )
