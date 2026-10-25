"""Persisted customer lifecycle; only the approved disposable PostgreSQL runner."""

import os
import re
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture
def customer_creation_env():
    explicit_url = os.environ.get("DATABASE_URL")
    assert explicit_url, "Use scripts/verify_invoice_cycle.py; no default database"
    target = make_url(explicit_url)
    assert os.environ.get("APP_ENV") == "test"
    assert os.environ.get("POSTING_ENABLED") == "false"
    assert target.get_backend_name() == "postgresql"
    assert target.host in {"localhost", "127.0.0.1", "::1"}
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", target.database or "")

    from app.config import POSTING_ENABLED
    from app.db import engine, get_db
    from app.main import app

    assert POSTING_ENABLED is False and engine.url == target
    assert get_db not in app.dependency_overrides
    ids = {key: uuid4() for key in ("owner", "branch", "territory", "session")}
    with Session(engine) as db:
        assert (
            db.execute(text("SELECT current_database()")).scalar_one()
            == target.database
        )
        db.execute(
            text(
                "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
                "VALUES (:owner,:username,'unused','owner',true)"
            ),
            {**ids, "username": "lifecycle_" + ids["owner"].hex},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_branch(id,code,name_ar) "
                "VALUES (:branch,:code,'فرع اختباري')"
            ),
            {**ids, "code": ids["branch"].hex[:20]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_territory(id,code,name_ar) "
                "VALUES (:territory,:code,'منطقة اختبارية')"
            ),
            {**ids, "code": ids["territory"].hex[:20]},
        )
        db.execute(
            text(
                "INSERT INTO platform.platform_session(id,user_id,expires_at) "
                "VALUES (:session,:owner,now() + interval '1 hour')"
            ),
            ids,
        )
        db.commit()
    payload = {
        "code": "C-" + uuid4().hex[:24],
        "name_ar": "عميل اختباري",
        "name_en": "Synthetic customer",
        "branch_id": str(ids["branch"]),
        "territory_id": str(ids["territory"]),
    }
    with TestClient(app) as client:
        yield (
            client,
            engine,
            ids,
            {"Authorization": f"Bearer {ids['session']}"},
            payload,
        )


def customer_snapshot(engine, customer_id):
    """Fresh connection: observe committed rows, not a request/savepoint session."""
    with engine.connect() as db:
        customer = dict(
            db.execute(
                text("SELECT * FROM master_data.master_customer WHERE id=:id"),
                {"id": customer_id},
            )
            .mappings()
            .one()
        )
        audits = [
            dict(row)
            for row in db.execute(
                text(
                    "SELECT * FROM audit.audit_log WHERE entity_type='master_customer' "
                    "AND entity_id=:id ORDER BY id"
                ),
                {"id": customer_id},
            ).mappings()
        ]
    return {"customer": customer, "audits": audits}


def test_create_persists_active_customer_and_atomic_audit(customer_creation_env):
    client, engine, ids, auth, payload = customer_creation_env
    response = client.post("/master/customers", json=payload, headers=auth)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_active"] is True
    assert {key: body[key] for key in payload} == payload
    snapshot = customer_snapshot(engine, UUID(body["id"]))
    customer, audits = snapshot["customer"], snapshot["audits"]
    assert customer["code"] == payload["code"] and customer["is_active"] is True
    assert customer["branch_id"] == ids["branch"]
    assert customer["territory_id"] == ids["territory"]
    assert len(audits) == 1
    assert audits[0]["actor_user_id"] == ids["owner"]
    assert audits[0]["action"] == "created" and audits[0]["old_values"] is None
    assert audits[0]["new_values"] == body


@pytest.mark.parametrize("operation", ["create", "deactivate", "activate"])
def test_concurrent_duplicates_and_lifecycle_noops(customer_creation_env, operation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, engine, _ids, auth, payload = customer_creation_env
    body = None if operation == "create" else create_customer(customer_creation_env)
    if operation == "activate":
        assert (
            client.delete(f"/master/customers/{body['id']}", headers=auth).status_code
            == 204
        )
    barrier = Barrier(2)

    def request():
        barrier.wait(timeout=10)
        if operation == "create":
            return client.post("/master/customers", json=payload, headers=auth)
        if operation == "deactivate":
            return client.delete(f"/master/customers/{body['id']}", headers=auth)
        return client.patch(f"/master/customers/{body['id']}/activate", headers=auth)

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(lambda _: request(), range(2)))
    expected = (
        [201, 409]
        if operation == "create"
        else [204, 204]
        if operation == "deactivate"
        else [200, 200]
    )
    assert sorted(r.status_code for r in responses) == expected
    if body is None:
        body = next(r.json() for r in responses if r.status_code == 201)
    events = customer_snapshot(engine, body["id"])["audits"]
    action = {
        "create": "created",
        "deactivate": "deactivated",
        "activate": "activated",
    }[operation]
    assert sum(event["action"] == action for event in events) == 1


def test_inactive_customer_blocks_new_sales_but_preserves_history(
    customer_creation_env,
    request,
):
    client, engine, ids, auth, _payload = customer_creation_env
    customer = create_customer(customer_creation_env)
    warehouse, product, ar_id = uuid4(), uuid4(), uuid4()

    def remove_owned_stock():
        # Legacy inventory fixtures require no committed stock between tests.
        with engine.begin() as cleanup:
            cleanup.execute(
                text(
                    "DELETE FROM inventory.stock_balance WHERE warehouse_id=:w AND product_id=:p"
                ),
                {"w": warehouse, "p": product},
            )

    request.addfinalizer(remove_owned_stock)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:b,:code,'مخزن اختباري')"
            ),
            {"id": warehouse, "b": ids["branch"], "code": warehouse.hex[:20]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'صنف اختباري',114,14)"
            ),
            {"id": product, "sku": product.hex},
        )
        db.execute(
            text(
                "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) VALUES (:w,:p,10)"
            ),
            {"w": warehouse, "p": product},
        )
        db.execute(
            text(
                "INSERT INTO finance.ar_entry(id,customer_id,entry_type,entry_date,debit,credit,created_by) VALUES (:id,:c,'opening',CURRENT_DATE,77.33,0,:u)"
            ),
            {"id": ar_id, "c": customer["id"], "u": ids["owner"]},
        )
    payload = {
        "invoice_no": "H-" + uuid4().hex[:20],
        "branch_id": str(ids["branch"]),
        "warehouse_id": str(warehouse),
        "customer_id": customer["id"],
        "invoice_date": "2026-10-25",
        "lines": [{"product_id": str(product), "quantity": "1", "discount_pct": "0"}],
    }
    draft = client.post("/invoices", json=payload, headers=auth)
    assert draft.status_code == 201, draft.text
    invoice_id = draft.json()["id"]

    def history():
        with engine.connect() as db:
            return {
                "invoice": dict(
                    db.execute(
                        text("SELECT * FROM sales.sales_invoice WHERE id=:id"),
                        {"id": invoice_id},
                    )
                    .mappings()
                    .one()
                ),
                "lines": [
                    dict(r)
                    for r in db.execute(
                        text(
                            "SELECT * FROM sales.sales_invoice_line WHERE invoice_id=:id ORDER BY id"
                        ),
                        {"id": invoice_id},
                    ).mappings()
                ],
                "ar": dict(
                    db.execute(
                        text("SELECT * FROM finance.ar_entry WHERE id=:id"),
                        {"id": ar_id},
                    )
                    .mappings()
                    .one()
                ),
                "stock": dict(
                    db.execute(
                        text(
                            "SELECT * FROM inventory.stock_balance WHERE warehouse_id=:w AND product_id=:p"
                        ),
                        {"w": warehouse, "p": product},
                    )
                    .mappings()
                    .one()
                ),
            }

    before = history()
    assert (
        client.delete(f"/master/customers/{customer['id']}", headers=auth).status_code
        == 204
    )
    refused = client.post(
        "/invoices",
        json={**payload, "invoice_no": "NEW-" + uuid4().hex[:20]},
        headers=auth,
    )
    assert refused.status_code == 422, refused.text
    assert history() == before
    assert client.get(f"/invoices/{invoice_id}", headers=auth).status_code == 200
    assert client.post(f"/invoices/{invoice_id}/post", headers=auth).status_code == 409
    assert (
        client.patch(
            f"/master/customers/{customer['id']}/activate", headers=auth
        ).status_code
        == 200
    )
    assert history() == before
    allowed = client.post(
        "/invoices",
        json={**payload, "invoice_no": "RE-" + uuid4().hex[:20]},
        headers=auth,
    )
    assert allowed.status_code == 201, allowed.text
    assert history() == before


@pytest.mark.parametrize(
    "names",
    [
        {"name_ar": "عميل اختباري"},
        {"name_en": "Synthetic customer"},
        {"name_ar": "عميل اختباري", "name_en": "Synthetic customer"},
    ],
)
def test_unchanged_customer_names_do_not_duplicate_audit(customer_creation_env, names):
    client, engine, _ids, auth, _payload = customer_creation_env
    body = create_customer(customer_creation_env)
    before = customer_snapshot(engine, body["id"])
    response = client.patch(f"/master/customers/{body['id']}", json=names, headers=auth)
    assert response.status_code == 200 and response.json() == body
    assert customer_snapshot(engine, body["id"]) == before


def create_customer(env):
    client, _engine, _ids, auth, payload = env
    response = client.post("/master/customers", json=payload, headers=auth)
    assert response.status_code == 201, response.text
    return response.json()


def test_lifecycle_read_visibility_idempotency_and_history(customer_creation_env):
    client, engine, ids, auth, payload = customer_creation_env
    body = create_customer(customer_creation_env)
    cid = body["id"]
    assert client.get(f"/master/customers/{cid}", headers=auth).json() == body
    assert (
        client.patch(f"/master/customers/{cid}/activate", headers=auth).json() == body
    )
    assert len(customer_snapshot(engine, cid)["audits"]) == 1
    for _ in range(2):
        response = client.delete(f"/master/customers/{cid}", headers=auth)
        assert response.status_code == 204, response.text
    inactive = customer_snapshot(engine, cid)
    assert inactive["customer"]["is_active"] is False
    assert inactive["customer"]["branch_id"] == ids["branch"]
    assert len(inactive["audits"]) == 2
    event = next(a for a in inactive["audits"] if a["action"] == "deactivated")
    assert event["actor_user_id"] == ids["owner"]
    assert event["old_values"] == body
    assert event["new_values"] == {**body, "is_active": False}
    assert (
        client.get(f"/master/customers/{cid}", headers=auth).json()["is_active"]
        is False
    )
    assert cid not in {
        r["id"] for r in client.get("/master/customers", headers=auth).json()
    }
    visible = client.get("/master/customers?include_inactive=true", headers=auth)
    assert visible.status_code == 200
    assert next(r for r in visible.json() if r["id"] == cid)["is_active"] is False
    for _ in range(2):
        active = client.patch(f"/master/customers/{cid}/activate", headers=auth)
        assert active.status_code == 200, active.text
        assert active.json() == body
    final = customer_snapshot(engine, cid)
    assert len(final["audits"]) == 3
    event = next(a for a in final["audits"] if a["action"] == "activated")
    assert event["old_values"]["is_active"] is False
    assert event["new_values"] == body and event["actor_user_id"] == ids["owner"]
    assert cid in {
        r["id"] for r in client.get("/master/customers", headers=auth).json()
    }
    duplicate = client.post("/master/customers", json=payload, headers=auth)
    assert duplicate.status_code == 409
    assert customer_snapshot(engine, cid) == final


@pytest.mark.parametrize("field", ["branch_id", "territory_id"])
def test_invalid_reference_is_not_reported_as_duplicate(customer_creation_env, field):
    client, engine, _ids, auth, payload = customer_creation_env
    payload[field] = str(uuid4())
    response = client.post("/master/customers", json=payload, headers=auth)
    assert response.status_code == 422, response.text
    with engine.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM master_data.master_customer WHERE code=:code"
                ),
                payload,
            )
            == 0
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit.audit_log WHERE new_values->>'code'=:code"
                ),
                payload,
            )
            == 0
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("code", ""),
        ("code", "  "),
        ("code", "x" * 31),
        ("name_ar", "  "),
        ("name_ar", None),
        ("name_ar", "x" * 201),
        ("name_en", "x" * 201),
        ("branch_id", None),
        ("territory_id", None),
        ("branch_id", "invalid"),
        ("territory_id", "invalid"),
        ("actor_user_id", "forged"),
        ("is_active", False),
        ("id", str(UUID(int=1))),
    ],
)
def test_create_rejects_invalid_values_without_writes(
    customer_creation_env, field, value
):
    client, engine, _ids, auth, payload = customer_creation_env
    payload[field] = value
    with engine.connect() as db:
        before = db.scalar(text("SELECT count(*) FROM master_data.master_customer"))
    response = client.post("/master/customers", json=payload, headers=auth)
    assert response.status_code == 422, response.text
    with engine.connect() as db:
        assert (
            db.scalar(text("SELECT count(*) FROM master_data.master_customer"))
            == before
        )


@pytest.mark.parametrize(
    "field", [None, "code", "name_ar", "branch_id", "territory_id"]
)
def test_create_rejects_missing_required_fields(customer_creation_env, field):
    client, _engine, _ids, auth, payload = customer_creation_env
    if field is None:
        payload = {}
    else:
        payload.pop(field)
    assert (
        client.post("/master/customers", json=payload, headers=auth).status_code == 422
    )


@pytest.mark.parametrize(
    "role,owner,active,status",
    [
        ("finance", False, True, 403),
        ("sales_manager", False, True, 403),
        ("district_manager", False, True, 403),
        ("medical_rep", False, True, 403),
        ("warehouse_staff", False, True, 403),
        ("read_only_auditor", False, True, 403),
        ("admin", False, True, 403),
        ("owner", False, True, 403),
        ("finance", True, True, 403),
        ("owner", True, False, 401),
    ],
)
def test_mutations_require_active_owner_and_flag(
    customer_creation_env, role, owner, active, status
):
    client, engine, ids, auth, payload = customer_creation_env
    body = create_customer(customer_creation_env)
    before = customer_snapshot(engine, body["id"])
    with engine.begin() as db:
        db.execute(
            text(
                "UPDATE platform.platform_user SET role=:role,is_owner=:owner,is_active=:active WHERE id=:id"
            ),
            {"id": ids["owner"], "role": role, "owner": owner, "active": active},
        )
    responses = [
        client.post("/master/customers", json=payload, headers=auth),
        client.delete(f"/master/customers/{body['id']}", headers=auth),
        client.patch(f"/master/customers/{body['id']}/activate", headers=auth),
        client.patch(
            f"/master/customers/{body['id']}", json={"name_ar": "ممنوع"}, headers=auth
        ),
    ]
    assert [r.status_code for r in responses] == [status] * 4
    assert customer_snapshot(engine, body["id"]) == before


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer " + str(UUID(int=1))}]
)
def test_mutations_require_valid_session(customer_creation_env, headers):
    client, engine, _ids, _auth, payload = customer_creation_env
    body = create_customer(customer_creation_env)
    before = customer_snapshot(engine, body["id"])
    for response in [
        client.post("/master/customers", json=payload, headers=headers),
        client.delete(f"/master/customers/{body['id']}", headers=headers),
        client.patch(f"/master/customers/{body['id']}/activate", headers=headers),
    ]:
        assert response.status_code in {401, 403}
    assert customer_snapshot(engine, body["id"]) == before


def test_customer_and_territory_reads_preserve_grants(customer_creation_env):
    client, engine, ids, auth, _payload = customer_creation_env
    body = create_customer(customer_creation_env)
    other = uuid4()
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,'غير مسموح')"
            ),
            {"id": other, "code": other.hex[:20]},
        )
        db.execute(
            text(
                "UPDATE platform.platform_user SET role='medical_rep',is_owner=false WHERE id=:id"
            ),
            {"id": ids["owner"]},
        )
    assert client.get("/master/customers", headers=auth).json() == []
    assert (
        client.get(f"/master/customers/{body['id']}", headers=auth).status_code == 404
    )
    assert client.get("/master/territories", headers=auth).json() == []
    assert (
        client.get("/master/customers?include_inactive=true", headers=auth).status_code
        == 403
    )
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:owner,:territory)"
            ),
            ids,
        )
    assert client.get(f"/master/customers/{body['id']}", headers=auth).json() == body
    assert client.get("/master/territories", headers=auth).json() == [
        {
            "id": str(ids["territory"]),
            "code": ids["territory"].hex[:20],
            "name_ar": "منطقة اختبارية",
            "name_en": None,
        }
    ]
    with engine.begin() as db:
        db.execute(
            text("UPDATE master_data.master_customer SET is_active=false WHERE id=:id"),
            {"id": body["id"]},
        )
    assert (
        client.get(f"/master/customers/{body['id']}", headers=auth).status_code == 404
    )


@pytest.mark.parametrize(
    "method,suffix", [("get", ""), ("delete", ""), ("patch", "/activate")]
)
def test_missing_customer_is_404_without_audit(customer_creation_env, method, suffix):
    client, engine, _ids, auth, _payload = customer_creation_env
    missing = uuid4()
    response = getattr(client, method)(
        f"/master/customers/{missing}{suffix}", headers=auth
    )
    assert response.status_code == 404, response.text
    with engine.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit.audit_log WHERE entity_id=:id"),
                {"id": missing},
            )
            == 0
        )


@pytest.mark.parametrize("operation", ["create", "deactivate", "activate"])
@pytest.mark.parametrize("fault", ["audit_before", "audit_after", "commit"])
def test_failed_writes_roll_back_persisted_customer_and_audit(
    customer_creation_env, monkeypatch, operation, fault
):
    from app.master import router as master_router

    client, engine, _ids, auth, payload = customer_creation_env
    body = create_customer(customer_creation_env)
    if operation == "activate":
        assert (
            client.delete(f"/master/customers/{body['id']}", headers=auth).status_code
            == 204
        )
    before = customer_snapshot(engine, body["id"])
    real_audit = master_router.log_audit

    def fail_audit(*args, **kwargs):
        if fault == "audit_after":
            real_audit(*args, **kwargs)
        raise RuntimeError("synthetic lifecycle failure")

    def fail_commit(_self):
        raise RuntimeError("synthetic lifecycle failure")

    with monkeypatch.context() as patcher:
        if fault == "commit":
            patcher.setattr(Session, "commit", fail_commit)
        else:
            patcher.setattr(master_router, "log_audit", fail_audit)
        with pytest.raises(RuntimeError, match="synthetic lifecycle failure"):
            if operation == "create":
                client.post(
                    "/master/customers",
                    json={**payload, "code": "R-" + payload["code"]},
                    headers=auth,
                )
            elif operation == "deactivate":
                client.delete(f"/master/customers/{body['id']}", headers=auth)
            else:
                client.patch(f"/master/customers/{body['id']}/activate", headers=auth)
    assert customer_snapshot(engine, body["id"]) == before
    with engine.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM master_data.master_customer WHERE code=:code"
                ),
                {"code": "R-" + payload["code"]},
            )
            == 0
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit.audit_log WHERE new_values->>'code'=:code"
                ),
                {"code": "R-" + payload["code"]},
            )
            == 0
        )
