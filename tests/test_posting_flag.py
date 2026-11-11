"""Feature-flag gate for the invoice posting endpoint.

The flag POSTING_ENABLED defaults to OFF. When OFF the endpoint keeps
returning 409 with the unchanged message; when ON it delegates to
app.sales.service.post_invoice_atomic.
"""

from uuid import UUID

import pytest

from app.sales import service
from app.sales.service import post_invoice_atomic

pytest_plugins = ["test_invoice_cycle_controls"]


def test_flag_defaults_off(posting_env, monkeypatch):
    """Without POSTING_ENABLED the endpoint stays 409 with the old message."""
    monkeypatch.delenv("POSTING_ENABLED", raising=False)
    monkeypatch.setattr("app.sales.router.POSTING_ENABLED", False)
    client, _db, _ids, auth, invoice, _payload = posting_env
    response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    assert response.status_code == 409
    assert "disabled" in response.json()["detail"].lower()
    # nothing was posted
    assert (
        client.get(f"/invoices/{invoice['id']}", headers=auth).json()["posting_status"]
        == "Draft"
    )


def test_flag_on_delegates_to_atomic(posting_env, monkeypatch):
    """With the flag ON the endpoint delegates to post_invoice_atomic once."""
    monkeypatch.setenv("POSTING_ENABLED", "true")
    monkeypatch.setattr("app.sales.router.POSTING_ENABLED", True)
    client, _db, ids, auth, invoice, _payload = posting_env

    calls = []

    def fake_post_invoice_atomic(db_, invoice_id, actor_id):
        calls.append({"db": db_, "invoice_id": invoice_id, "actor_id": actor_id})
        # a complete InvoiceOut-shaped dict so the route's model_validate passes
        return {
            **invoice,
            "posting_status": "Draft",
            "id": str(invoice_id),
            "version": 1,
        }

    real = service.post_invoice_atomic
    monkeypatch.setattr(service, "post_invoice_atomic", fake_post_invoice_atomic)
    try:
        response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    finally:
        # the real atomic function must not have been the one invoked
        assert service.post_invoice_atomic is fake_post_invoice_atomic

    assert response.status_code == 200
    body = response.json()
    assert body["posting_status"] == "Draft"
    assert body["id"] == invoice["id"]
    assert body["version"] == 1
    assert len(calls) == 1
    assert calls[0]["invoice_id"] == UUID(invoice["id"])
    assert calls[0]["actor_id"] == ids["owner"]
    # the real atomic function was never called: no DB side effects
    assert (
        client.get(f"/invoices/{invoice['id']}", headers=auth).json()["posting_status"]
        == "Draft"
    )
    assert real is post_invoice_atomic  # the original is untouched


def test_flag_on_with_depleted_stock_returns_409(posting_env, monkeypatch):
    """With the flag ON and depleted stock the endpoint returns 409, no exception."""
    from sqlalchemy import text

    monkeypatch.setenv("POSTING_ENABLED", "true")
    monkeypatch.setattr("app.sales.router.POSTING_ENABLED", True)
    client, db, ids, auth, invoice, _payload = posting_env
    # deplete stock to a single unit; the invoice line needs 2

    db.execute(
        text(
            "UPDATE inventory.stock_balance SET quantity=1 WHERE warehouse_id=:w AND product_id=:p"
        ),
        {"w": ids["warehouse"], "p": ids["product"]},
    )
    db.commit()

    response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    assert response.status_code == 409
    assert "stock" in response.json()["detail"].lower()
    # nothing was posted; the transaction rolled back
    assert (
        client.get(f"/invoices/{invoice['id']}", headers=auth).json()["posting_status"]
        == "Draft"
    )


def test_clean_import_defaults_off_without_router_patch():
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = os.environ.copy()
    env.pop("POSTING_ENABLED", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from app import config; "
                "from app.sales import router as sales; "
                "from app.finance import payment_router as payments; "
                "assert config.POSTING_ENABLED is False; "
                "assert sales.POSTING_ENABLED is False; "
                "assert payments.POSTING_ENABLED is False"
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("operation", ["post", "reverse", "collect", "void"])
def test_default_gate_refuses_authorized_mutations_without_writes(
    posting_env, operation
):
    from uuid import uuid4

    from sqlalchemy import text

    from app.finance import payment_router
    from app.sales import router

    client, db, _ids, auth, invoice, payload = posting_env
    assert router.POSTING_ENABLED is False
    assert payment_router.POSTING_ENABLED is False
    tables = (
        "sales.sales_invoice",
        "sales.sales_invoice_line",
        "inventory.stock_balance",
        "inventory.stock_movement",
        "finance.ar_entry",
        "finance.payment_receipt",
        "audit.audit_log",
    )
    before = {
        table: list(db.execute(text(f"SELECT * FROM {table} ORDER BY id")).mappings())
        for table in tables
    }
    assert before["sales.sales_invoice"] and before["audit.audit_log"]
    if operation == "post":
        path, body = f"/invoices/{invoice['id']}/post", None
    elif operation == "reverse":
        path = f"/invoices/{invoice['id']}/reverse"
        body = {"version": invoice["version"], "reason_id": str(uuid4())}
    elif operation == "collect":
        path = "/collections"
        body = {
            "invoice_id": invoice["id"],
            "invoice_version": invoice["version"],
            "receipt_no": uuid4().hex[:24],
            "receipt_date": payload["invoice_date"],
            "amount": "1.00",
            "method": "cash",
        }
    else:
        path = f"/collections/{uuid4()}/void"
        body = {"version": 1, "reason_id": str(uuid4())}
    response = client.post(path, json=body, headers=auth)
    assert response.status_code == 409, response.text
    assert "disabled" in response.json()["detail"].lower()
    after = {
        table: list(db.execute(text(f"SELECT * FROM {table} ORDER BY id")).mappings())
        for table in tables
    }
    assert after == before


def test_audit_insert_then_error_rolls_back_durable_draft(life, monkeypatch):
    from datetime import UTC, datetime
    from uuid import uuid4

    from sqlalchemy import text
    from test_invoice_cycle_controls import state

    from app.sales import router

    original = router.log_audit
    written = []

    def insert_then_fail(db, *args, **kwargs):
        original(db, *args, **kwargs)
        written.append(
            db.execute(text("SELECT count(*) FROM audit.audit_log")).scalar_one()
        )
        raise RuntimeError("synthetic failure after actual audit insert")

    before = state(life)
    monkeypatch.setattr(router, "log_audit", insert_then_fail)
    payload = {
        "invoice_no": uuid4().hex[:30],
        "branch_id": str(life.ids["branch"]),
        "warehouse_id": str(life.ids["warehouse"]),
        "customer_id": str(life.ids["customer"]),
        "invoice_date": datetime.now(UTC).date().isoformat(),
        "lines": [{"product_id": str(life.ids["product"]), "quantity": "2"}],
    }
    response = life.client.post("/invoices", json=payload, headers=life.auth["owner"])
    assert response.status_code == 500
    assert written == [1]
    # The existing state helper uses fresh committed-witness connections.
    assert state(life) == before


@pytest.mark.parametrize(
    "field", ["grand_total", "vat_amount", "created_by", "posting_status"]
)
def test_server_owned_values_are_durable_and_not_request_fields(life, field):
    from datetime import UTC, datetime
    from decimal import Decimal
    from uuid import uuid4

    from test_invoice_cycle_controls import sql, state

    payload = {
        "invoice_no": uuid4().hex[:30],
        "branch_id": str(life.ids["branch"]),
        "warehouse_id": str(life.ids["warehouse"]),
        "customer_id": str(life.ids["customer"]),
        "invoice_date": datetime.now(UTC).date().isoformat(),
        "lines": [
            {
                "product_id": str(life.ids["product"]),
                "quantity": "2",
                "discount_pct": "10",
            }
        ],
    }
    forged = {
        "grand_total": "0.01",
        "vat_amount": "0.01",
        "created_by": str(life.ids["finance"]),
        "posting_status": "Posted",
    }
    before = state(life)
    rejected = life.client.post(
        "/invoices",
        json={**payload, field: forged[field]},
        headers=life.auth["owner"],
    )
    assert rejected.status_code == 422, rejected.text
    assert state(life) == before
    response = life.client.post("/invoices", json=payload, headers=life.auth["owner"])
    assert response.status_code == 201, response.text
    invoice = response.json()
    identity = UUID(invoice["id"])
    stored = sql("SELECT * FROM sales.sales_invoice WHERE id=:i", i=identity)[0]
    amounts = tuple(stored[k] for k in ("grand_total", "total_net", "vat_amount"))
    assert all(isinstance(value, Decimal) for value in amounts)
    assert amounts == (Decimal("205.20"), Decimal("180.00"), Decimal("25.20"))
    assert stored["posting_status"] == invoice["posting_status"] == "Draft"
    assert stored["created_by"] == life.ids["owner"]
    assert invoice["created_by"] == str(life.ids["owner"])
    line = sql("SELECT * FROM sales.sales_invoice_line WHERE invoice_id=:i", i=identity)
    assert len(line) == 1
    assert line[0]["unit_price"] == Decimal("114.00")
    assert line[0]["vat_rate"] == Decimal("14.00")
    assert line[0]["line_total"] == Decimal("205.20")
    assert line[0]["vat_amount"] == Decimal("25.20")
    audits = sql("SELECT * FROM audit.audit_log WHERE entity_id=:i", i=identity)
    assert len(audits) == 1
    assert audits[0]["action"] == "created"
    assert audits[0]["actor_user_id"] == life.ids["owner"]
    assert audits[0]["new_values"]["created_by"] == str(life.ids["owner"])
    assert audits[0]["new_values"]["grand_total"] == "205.20"


@pytest.fixture
def audit_app_role(life):
    import os
    import re
    from uuid import uuid4

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.db import engine, get_db
    from app.main import app

    assert os.environ.get("APP_ENV") == "test"
    assert os.environ.get("ERP_VERIFY_RUNTIME")
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", engine.url.database)
    assert engine.url.host == "127.0.0.1" and engine.url.port == 5432
    role = "erp_app_audit_" + uuid4().hex[:24]
    quote = engine.dialect.identifier_preparer.quote
    app_engine = None
    previous = app.dependency_overrides[get_db]
    created = False
    try:
        with engine.begin() as connection:
            assert (
                connection.scalar(text("SELECT current_database()"))
                == engine.url.database
            )
            connection.execute(
                text(
                    f"CREATE ROLE {quote(role)} LOGIN NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
                )
            )
            tables = (
                connection.execute(
                    text(
                        "SELECT n.nspname, c.relname, "
                        "has_table_privilege(current_user,c.oid,'SELECT') AS can_select, "
                        "has_table_privilege(current_user,c.oid,'INSERT') AS can_insert, "
                        "has_table_privilege(current_user,c.oid,'UPDATE') AS can_update, "
                        "has_table_privilege(current_user,c.oid,'DELETE') AS can_delete, "
                        "has_table_privilege(current_user,c.oid,'TRUNCATE') AS can_truncate "
                        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE c.relkind IN ('r','p') AND n.nspname NOT LIKE 'pg_%' "
                        "AND n.nspname <> 'information_schema'"
                    )
                )
                .mappings()
                .all()
            )
            for schema in {row["nspname"] for row in tables}:
                connection.execute(
                    text(f"GRANT USAGE ON SCHEMA {quote(schema)} TO {quote(role)}")
                )
            # Mirror current app DML rights; never manufacture denial with a test-only REVOKE.
            for row in tables:
                rights = [
                    verb.upper()
                    for verb in ("select", "insert", "update", "delete", "truncate")
                    if row["can_" + verb]
                ]
                if rights:
                    connection.execute(
                        text(
                            f"GRANT {','.join(rights)} ON TABLE "
                            f"{quote(row['nspname'])}.{quote(row['relname'])} TO {quote(role)}"
                        )
                    )
        created = True
        app_engine = create_engine(engine.url.set(username=role, password=None))

        def app_db():
            with Session(app_engine) as db:
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                db.execute(text("SET LOCAL statement_timeout='12s'"))
                yield db

        app.dependency_overrides[get_db] = app_db
        yield app_engine, role
    finally:
        app.dependency_overrides[get_db] = previous
        if app_engine is not None:
            app_engine.dispose()
        if created:
            with engine.begin() as connection:
                connection.execute(text(f"DROP OWNED BY {quote(role)}"))
                connection.execute(text(f"DROP ROLE {quote(role)}"))


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "actor_user_id",
        "action",
        "entity_type",
        "entity_id",
        "old_values",
        "new_values",
        "ip_address",
        "user_agent",
        "created_at",
        "delete",
        "truncate",
    ],
)
def test_app_role_cannot_update_or_delete_audit_log(
    life, audit_app_role, field, monkeypatch, record_property
):
    import hashlib
    import json
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    from test_invoice_cycle_controls import sql

    app_engine, role = audit_app_role
    monkeypatch.setattr("app.sales.router.POSTING_ENABLED", False)
    monkeypatch.setattr("app.finance.payment_router.POSTING_ENABLED", False)
    with app_engine.connect() as connection:
        identity = dict(
            connection.execute(
                text(
                    "SELECT current_user AS effective_user, session_user AS login_user, "
                    "r.rolsuper, r.rolcreaterole, r.rolcreatedb, r.rolbypassrls, "
                    "(SELECT count(*) FROM pg_auth_members WHERE member=r.oid) AS memberships, "
                    "(SELECT pg_get_userbyid(relowner) FROM pg_class "
                    "WHERE oid='audit.audit_log'::regclass) AS table_owner "
                    "FROM pg_roles r WHERE rolname=current_user"
                )
            )
            .mappings()
            .one()
        )
        assert identity["effective_user"] == identity["login_user"] == role
        assert not any(
            identity[k]
            for k in ("rolsuper", "rolcreaterole", "rolcreatedb", "rolbypassrls")
        )
        assert identity["memberships"] == 0 and identity["table_owner"] != role
    invoice = life.draft()
    rows = sql("SELECT * FROM audit.audit_log ORDER BY id")
    target = [row for row in rows if row["entity_id"] == UUID(invoice["id"])]
    assert len(target) == 1 and target[0]["action"] == "created"
    assert target[0]["actor_user_id"] == life.ids["owner"]
    changed = {
        "id": uuid4(),
        "actor_user_id": life.ids["finance"],
        "action": "synthetic_tamper",
        "entity_type": "synthetic_witness",
        "entity_id": uuid4(),
        "old_values": '{"synthetic":"changed-old"}',
        "new_values": '{"synthetic":"changed-new"}',
        "ip_address": "192.0.2.10",
        "user_agent": "Synthetic audit witness",
        "created_at": datetime.now(UTC) + timedelta(seconds=1),
    }
    denied, sqlstate, affected = False, None, None
    with app_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ WRITE"))
            assert connection.scalar(text("SHOW transaction_read_only")) == "off"
            if field == "truncate":
                statement = "TRUNCATE audit.audit_log"
                params = {}
            elif field == "delete":
                statement = "DELETE FROM audit.audit_log WHERE id=:id"
                params = {"id": target[0]["id"]}
            else:
                if field in {"old_values", "new_values"}:
                    expression = "CAST(:changed AS jsonb)"
                elif field == "ip_address":
                    expression = "CAST(:changed AS inet)"
                else:
                    expression = ":changed"
                statement = (
                    f"UPDATE audit.audit_log SET {field}={expression} WHERE id=:id"
                )
                params = {"id": target[0]["id"], "changed": changed[field]}
            affected = connection.execute(text(statement), params).rowcount
        except DBAPIError as exc:
            sqlstate = exc.orig.sqlstate
            assert sqlstate == "42501", (
                "Non-ACL errors are not audit-protection evidence"
            )
            denied = True
        finally:
            transaction.rollback()
    after = sql("SELECT * FROM audit.audit_log ORDER BY id")
    assert after == rows
    recovery = life.draft()
    recovered = sql("SELECT * FROM audit.audit_log ORDER BY id")
    assert len(recovered) == len(rows) + 1
    assert [row for row in recovered if row["id"] == target[0]["id"]] == target
    assert any(row["entity_id"] == UUID(recovery["id"]) for row in recovered)
    record_property(
        "audit_witness",
        json.dumps(
            {
                "field": field,
                "role": identity,
                "healthy_audited_write": True,
                "healthy_audited_recovery": True,
                "read_write_transaction": True,
                "denied": denied,
                "sqlstate": sqlstate,
                "affected_before_explicit_rollback": affected,
                "row_set_unchanged_after_explicit_rollback": after == rows,
                "before_digest": hashlib.sha256(
                    json.dumps(rows, default=str, sort_keys=True).encode()
                ).hexdigest(),
                "grants_provenance": "Current app principal effective table DML copied to non-superuser; no test-only REVOKE. Not deployed-role ACL proof.",
            },
            sort_keys=True,
        ),
    )
    assert denied, f"Audit {field} was allowed by the non-superuser app-role witness"
