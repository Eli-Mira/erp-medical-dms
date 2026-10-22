"""QA acceptance tests for POST /master/suppliers (201) and GET /master/suppliers/{uuid} (200).

First creation cycle with read verification; handles auth denial, input validation,
duplicate code conflict, and actor-bound audit logging.
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db import engine


@pytest.fixture(autouse=True)
def disposable_supplier_database():
    assert os.environ.get("APP_ENV") == "test", "Use scripts/verify_invoice_cycle.py"
    assert engine.url.database.startswith("dms_cycle_test_")


def test_owner_can_create_supplier_201(posting_env):
    """Owner POST /master/suppliers returns 201 with trimmed code/name."""
    client, _db, _ids, auth, *_ = posting_env
    payload = {
        "code": "  TEST-SUP-001  ",
        "name_ar": "  اختبار المورد  ",
        "name_en": "Test Supplier",
        "contact_phone": "0123456789",
        "address": "123 Test St, Cairo",
    }
    resp = client.post("/master/suppliers", json=payload, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "TEST-SUP-001"
    assert data["name_ar"] == "اختبار المورد"
    assert data["is_active"] is True


def test_owner_can_read_supplier_200(posting_env):
    """GET /master/suppliers/{uuid} returns SupplierOut or 404."""
    client, _db, _ids, auth, *_ = posting_env
    # Create supplier first
    create_resp = client.post(
        "/master/suppliers",
        json={"code": "READ-SUP", "name_ar": "قراءة"},
        headers=auth,
    )
    sup_id = create_resp.json()["id"]
    # Read it back
    resp = client.get(f"/master/suppliers/{sup_id}", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sup_id
    assert data["code"] == "READ-SUP"


def test_supplier_row_and_audit_created(posting_env):
    """POST creates DB row and audit action=created entity_type=master_supplier."""
    client, db, ids, auth, *_ = posting_env
    payload = {"code": "AUDIT-TEST", "name_ar": "توثيق"}
    resp = client.post("/master/suppliers", json=payload, headers=auth)
    assert resp.status_code == 201
    sup_id = resp.json()["id"]
    # Verify DB row exists with actor_id in audit
    row = (
        db.execute(
            text("SELECT * FROM master_data.master_supplier WHERE id=:id"),
            {"id": sup_id},
        )
        .mappings()
        .one()
    )
    assert row is not None
    assert row["code"] == "AUDIT-TEST"
    audit = (
        db.execute(
            text(
                "SELECT * FROM audit.audit_log WHERE entity_type=:et AND entity_id=:eid"
            ),
            {"et": "master_supplier", "eid": sup_id},
        )
        .mappings()
        .one()
    )
    assert audit is not None
    assert audit["action"] == "created"
    assert audit["actor_user_id"] == ids["owner"]


def test_duplicate_code_returns_409_no_extra_row(posting_env):
    """POST with existing code returns 409, no new row or audit created."""
    client, db, _ids, auth, *_ = posting_env
    payload = {"code": "DUP-CODE", "name_ar": "First"}
    resp1 = client.post("/master/suppliers", json=payload, headers=auth)
    assert resp1.status_code == 201
    first_id = resp1.json()["id"]
    # Count rows before duplicate attempt
    rows_before = db.execute(
        text("SELECT COUNT(*) FROM master_data.master_supplier WHERE code=:c"),
        {"c": "DUP-CODE"},
    ).scalar_one()
    audits_before = db.execute(
        text(
            "SELECT COUNT(*) FROM audit.audit_log WHERE entity_type=:et AND entity_id=:eid"
        ),
        {"et": "master_supplier", "eid": first_id},
    ).scalar_one()
    # Attempt duplicate
    resp2 = client.post(
        "/master/suppliers",
        json={"code": "DUP-CODE", "name_ar": "Second"},
        headers=auth,
    )
    assert resp2.status_code == 409
    # Verify no new row or audit
    assert (
        db.execute(
            text("SELECT COUNT(*) FROM master_data.master_supplier WHERE code=:c"),
            {"c": "DUP-CODE"},
        ).scalar_one()
        == rows_before
    )
    assert (
        db.execute(
            text("SELECT COUNT(*) FROM audit.audit_log WHERE entity_type=:et"),
            {"et": "master_supplier"},
        ).scalar_one()
        == audits_before
    )


def test_invalid_required_code_422(posting_env):
    """POST without code or blank code returns 422."""
    client, _db, _ids, auth, *_ = posting_env
    # Missing code
    resp = client.post("/master/suppliers", json={"name_ar": "Test"}, headers=auth)
    assert resp.status_code == 422
    # Blank code
    resp = client.post(
        "/master/suppliers", json={"code": " ", "name_ar": "Test"}, headers=auth
    )
    assert resp.status_code == 422


def test_invalid_required_name_ar_422(posting_env):
    """POST without name_ar or blank name_ar returns 422."""
    client, _db, _ids, auth, *_ = posting_env
    # Missing name_ar
    resp = client.post("/master/suppliers", json={"code": "TESTCODE"}, headers=auth)
    assert resp.status_code == 422
    # Blank name_ar
    resp = client.post(
        "/master/suppliers", json={"code": "TESTCODE", "name_ar": ""}, headers=auth
    )
    assert resp.status_code == 422


def test_wrong_type_code_422(posting_env):
    """POST with non-string code returns 422."""
    client, _db, _ids, auth, *_ = posting_env
    resp = client.post(
        "/master/suppliers", json={"code": 12345, "name_ar": "Test"}, headers=auth
    )
    assert resp.status_code == 422


def test_unknown_field_422(posting_env):
    """POST with unknown field returns 422."""
    client, _db, _ids, auth, *_ = posting_env
    resp = client.post(
        "/master/suppliers",
        json={"code": "TEST", "name_ar": "Test", "unknown_field": "value"},
        headers=auth,
    )
    assert resp.status_code == 422


def test_code_length_exceeds_30_422(posting_env):
    """POST with code > 30 chars returns 422."""
    client, _db, _ids, auth, *_ = posting_env
    resp = client.post(
        "/master/suppliers", json={"code": "A" * 31, "name_ar": "Test"}, headers=auth
    )
    assert resp.status_code == 422


def test_name_ar_exceeds_200_422(posting_env):
    """POST with name_ar > 200 chars returns 422."""
    client, _db, _ids, auth, *_ = posting_env
    resp = client.post(
        "/master/suppliers", json={"code": "TEST", "name_ar": "أ" * 201}, headers=auth
    )
    assert resp.status_code == 422


def test_name_en_exceeds_200_422(posting_env):
    """POST with name_en > 200 chars returns 422."""
    client, _db, _ids, auth, *_ = posting_env
    resp = client.post(
        "/master/suppliers",
        json={"code": "TEST", "name_ar": "Test", "name_en": "E" * 201},
        headers=auth,
    )
    assert resp.status_code == 422


def test_contact_phone_exceeds_30_422(posting_env):
    """POST with contact_phone > 30 chars returns 422."""
    client, _db, _ids, auth, *_ = posting_env
    resp = client.post(
        "/master/suppliers",
        json={"code": "TEST", "name_ar": "Test", "contact_phone": "0" * 31},
        headers=auth,
    )
    assert resp.status_code == 422


def test_unauthenticated_create_denied_401(posting_env):
    """POST without auth token returns 401."""
    client, _db, _ids, *_ = posting_env
    resp = client.post("/master/suppliers", json={"code": "TEST", "name_ar": "Test"})
    assert resp.status_code == 401


def test_non_owner_user_denied_403(posting_env):
    """POST by non-owner (finance) returns 403."""
    client, db, _ids, *_ = posting_env
    finance = uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role) "
            "VALUES (:id,:u,'unused','finance')"
        ),
        {"id": finance, "u": finance.hex},
    )
    db.commit()
    resp = client.post(
        "/master/suppliers",
        json={"code": "TEST", "name_ar": "Test"},
        headers=_login_as(db, finance),
    )
    assert resp.status_code == 403


def test_owner_flag_without_owner_role_denied_403(posting_env):
    """POST by user with is_owner=False but role=owner returns 403."""
    client, db, _ids, *_ = posting_env
    fake_owner = uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
            "VALUES (:id,'fake_owner','unused','owner',false)"
        ),
        {"id": fake_owner},
    )
    db.commit()
    auth = _login_as(db, fake_owner)
    resp = client.post(
        "/master/suppliers", json={"code": "TEST", "name_ar": "Test"}, headers=auth
    )
    assert resp.status_code == 403


def test_inactive_supplier_still_readable(posting_env):
    """GET returns inactive suppliers (soft delete visibility)."""
    client, db, _ids, auth, *_ = posting_env
    # Create and deactivate
    create_resp = client.post(
        "/master/suppliers", json={"code": "INACT", "name_ar": "غير مفعل"}, headers=auth
    )
    sup_id = create_resp.json()["id"]
    db.execute(
        text("UPDATE master_data.master_supplier SET is_active=false WHERE id=:id"),
        {"id": sup_id},
    )
    db.commit()
    # Read back
    resp = client.get(f"/master/suppliers/{sup_id}", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


# Helper from test_master_data_b.py pattern
def _login_as(db, user_id):
    sid = uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_session(id,user_id,expires_at) "
            "VALUES (:sid,:uid,now() + interval '1 hour')"
        ),
        {"sid": sid, "uid": user_id},
    )
    db.commit()
    return {"Authorization": f"Bearer {sid}"}
