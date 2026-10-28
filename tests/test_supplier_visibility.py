"""Owner maintenance visibility, exercised through real PostgreSQL and HTTP."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db import engine


@pytest.fixture(autouse=True)
def disposable_supplier_database():
    assert os.environ.get("APP_ENV") == "test", "Use scripts/verify_invoice_cycle.py"
    assert engine.url.database.startswith("dms_cycle_test_")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT current_database()")) == engine.url.database
        )


def _seed(db):
    prefix = "VIS-" + uuid4().hex[:12]
    active, inactive = uuid4(), uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_supplier(id,code,name_ar,is_active) "
            "VALUES (:a,:ac,'مورد نشط',true),(:i,:ic,'مورد غير نشط',false)"
        ),
        {"a": active, "ac": prefix + "-A", "i": inactive, "ic": prefix + "-I"},
    )
    db.commit()
    return prefix, active, inactive


def _snapshot(db, active, inactive):
    rows = db.execute(
        text(
            "SELECT id,code,name_ar,name_en,contact_phone,address,is_active "
            "FROM master_data.master_supplier WHERE id IN (:a,:i) ORDER BY id"
        ),
        {"a": active, "i": inactive},
    ).all()
    return rows, db.scalar(text("SELECT COUNT(*) FROM audit.audit_log"))


def test_owner_opt_in_includes_inactive_without_writes(posting_env):
    client, db, _, auth, *_ = posting_env
    prefix, active, inactive = _seed(db)
    before = _snapshot(db, active, inactive)
    default = client.get("/master/suppliers", params={"q": prefix}, headers=auth)
    assert default.status_code == 200
    assert {row["id"] for row in default.json()} == {str(active)}
    response = client.get(
        "/master/suppliers",
        params={"q": prefix, "include_inactive": "true"},
        headers=auth,
    )
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()}
    assert set(rows) == {str(active), str(inactive)}
    assert rows[str(active)]["is_active"] is True
    assert rows[str(inactive)]["is_active"] is False
    assert _snapshot(db, active, inactive) == before


@pytest.mark.parametrize(
    "role,owner",
    [
        ("finance", False),
        ("read_only_auditor", False),
        ("finance", True),
        ("owner", False),
    ],
)
def test_maintenance_opt_in_requires_role_and_owner_flag(posting_env, role, owner):
    client, db, ids, auth, *_ = posting_env
    db.execute(
        text("UPDATE platform.platform_user SET role=:r,is_owner=:o WHERE id=:id"),
        {"r": role, "o": owner, "id": ids["owner"]},
    )
    db.commit()
    response = client.get("/master/suppliers?include_inactive=true", headers=auth)
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["finance", "read_only_auditor"])
def test_default_reader_still_gets_only_active(posting_env, role):
    client, db, ids, auth, *_ = posting_env
    prefix, active, inactive = _seed(db)
    db.execute(
        text("UPDATE platform.platform_user SET role=:r,is_owner=false WHERE id=:id"),
        {"r": role, "id": ids["owner"]},
    )
    db.commit()
    before = _snapshot(db, active, inactive)
    response = client.get("/master/suppliers", params={"q": prefix}, headers=auth)
    assert response.status_code == 200
    assert {row["id"] for row in response.json()} == {str(active)}
    assert _snapshot(db, active, inactive) == before
