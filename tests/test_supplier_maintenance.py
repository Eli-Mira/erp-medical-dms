"""First supplier-maintenance tracer; synthetic PostgreSQL only."""

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.db import engine


@pytest.fixture(autouse=True)
def disposable_supplier_database():
    assert os.environ.get("APP_ENV") == "test", "Use scripts/verify_invoice_cycle.py"
    assert engine.url.database.startswith("dms_cycle_test_")


def test_owner_creates_and_retrieves_supplier_with_actor_audit(posting_env):
    client, db, ids, auth, *_ = posting_env
    payload = {"code": "S-" + uuid4().hex[:20], "name_ar": "Synthetic supplier"}
    response = client.post("/master/suppliers", json=payload, headers=auth)
    assert response.status_code == 201, response.text
    created = response.json()
    supplier_id = UUID(created["id"])
    assert created["code"] == payload["code"]
    assert created["name_ar"] == payload["name_ar"]
    assert created["is_active"] is True
    fetched = client.get(f"/master/suppliers/{supplier_id}", headers=auth)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == created
    audit = (
        db.execute(
            text(
                "SELECT actor_user_id, action, new_values FROM audit.audit_log "
                "WHERE entity_type='master_supplier' AND entity_id=:id"
            ),
            {"id": supplier_id},
        )
        .mappings()
        .one()
    )
    assert audit["actor_user_id"] == ids["owner"]
    assert audit["action"] == "created"
    assert audit["new_values"]["code"] == payload["code"]


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_supplier_write_rolls_back_when_audit_fails(posting_env, monkeypatch, method):
    from app.master import router as master_router

    client, db, _ids, auth, *_ = posting_env
    supplier_id = uuid4()
    code = "ROLLBACK-" + uuid4().hex[:15]
    db.execute(
        text(
            "INSERT INTO master_data.master_supplier(id,code,name_ar) "
            "VALUES (:id,:code,'Original synthetic supplier')"
        ),
        {"id": supplier_id, "code": code},
    )
    db.commit()

    def reject_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(master_router, "log_audit", reject_audit)
    path = "/master/suppliers"
    kwargs = {"headers": auth}
    if method == "post":
        kwargs["json"] = {"code": code + "NEW", "name_ar": "New synthetic supplier"}
    else:
        path += f"/{supplier_id}"
        if method == "patch":
            kwargs["json"] = {"name_ar": "Changed synthetic supplier"}
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        getattr(client, method)(path, **kwargs)
    original = (
        db.execute(
            text(
                "SELECT name_ar,is_active FROM master_data.master_supplier WHERE id=:id"
            ),
            {"id": supplier_id},
        )
        .mappings()
        .one()
    )
    assert original["name_ar"] == "Original synthetic supplier"
    assert original["is_active"] is True
    assert (
        db.execute(
            text("SELECT count(*) FROM master_data.master_supplier WHERE code=:code"),
            {"code": code + "NEW"},
        ).scalar_one()
        == 0
    )
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM audit.audit_log "
                "WHERE entity_type='master_supplier' AND entity_id=:id"
            ),
            {"id": supplier_id},
        ).scalar_one()
        == 0
    )
