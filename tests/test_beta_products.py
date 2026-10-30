"""CORE.02 candidate tests; integration requires a fresh migrated task-owned DB.

Parent must explicitly bind app configuration and BETA_PRODUCTS_TEST_DATABASE_URL
before imports. Only PostgreSQL database names starting dms_cycle_test_ are allowed.
Records are synthetic and remain until the parent destroys that disposable DB.
"""

import os
import re
from decimal import Decimal
from uuid import UUID, uuid4

import app.master.router as master
import pytest
from app.master.schemas import ProductIn, ProductPatch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def payload(**changes):
    return {
        "sku": "B" + uuid4().hex,
        "name_ar": "صنف اختبار",
        "base_price": "1234567890.12",
        "vat_rate": "7.25",
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"sku": " "},
        {"sku": "x" * 51},
        {"name_ar": " "},
        {"name_ar": "x" * 201},
        {"name_en": "x" * 201},
        {"sku": "a\x00b"},
        {"name_ar": "a\x00b"},
        {"base_price": None},
        {"base_price": "-0.01"},
        {"base_price": "10000000000.00"},
        {"base_price": "0.001"},
        {"base_price": "NaN"},
        {"base_price": "Infinity"},
        {"base_price": True},
        {"base_price": 1.25},
        {"vat_rate": "100.01"},
        {"vat_rate": "-0.01"},
        {"vat_rate": "1.001"},
        {"vat_rate": "NaN"},
        {"vat_rate": False},
    ],
)
def test_invalid_create(changes):
    with pytest.raises(ValidationError):
        ProductIn.model_validate(payload(**changes))


@pytest.mark.parametrize("field", ["base_price", "vat_rate"])
def test_explicit_financial_input_required(field):
    data = payload()
    del data[field]
    with pytest.raises(ValidationError):
        ProductIn.model_validate(data)


def test_schema_capacity_and_exact_decimal():
    row = ProductIn.model_validate(
        payload(sku="x" * 50, base_price="9999999999.99", vat_rate="100.00")
    )
    assert row.base_price == Decimal("9999999999.99")
    assert row.vat_rate == Decimal("100.00")
    assert row.model_dump(mode="json")["base_price"] == "9999999999.99"
    assert (
        ProductIn.model_validate(payload(base_price="0", vat_rate="0")).base_price == 0
    )


@pytest.mark.parametrize(
    "field",
    ["id", "is_active", "created_by", "actor", "total", "verified_cost", "unit_cost"],
)
def test_forged_create_fields(field):
    with pytest.raises(ValidationError):
        ProductIn.model_validate(payload(**{field: "1"}))


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"name_ar": None},
        {"name_ar": " "},
        {"sku": "new"},
        {"base_price": "1.00"},
        {"vat_rate": "1.00"},
        {"is_active": True},
        {"name_en": "a\x00b"},
        {"created_by": str(uuid4())},
    ],
)
def test_invalid_patch(data):
    with pytest.raises(ValidationError):
        ProductPatch.model_validate(data)


@pytest.fixture
def product_api():
    raw = os.environ.get("BETA_PRODUCTS_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Explicit disposable PostgreSQL URL required")
    url = make_url(raw)
    assert url.get_backend_name() == "postgresql"
    assert url.database and bool(
        re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", url.database)
    )
    engine = create_engine(url)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        owner = (
            db.execute(
                text(
                    "SELECT id, role, is_owner, is_active FROM platform.platform_user "
                    "WHERE role='owner' AND is_owner AND is_active LIMIT 1"
                )
            )
            .mappings()
            .first()
        )
    assert owner is not None, (
        "Seed a synthetic active confirmed owner in this disposable DB"
    )
    actor = dict(owner)
    app = FastAPI()
    app.include_router(master.router)

    def get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[master.get_db] = get_db
    app.dependency_overrides[master.get_current_user] = lambda: actor
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, sessions, actor
    finally:
        engine.dispose()


def create(client, **changes):
    response = client.post("/master/products", json=payload(**changes))
    assert response.status_code == 201, response.text
    return response.json()


def persisted(sessions, product_id):
    with sessions() as db:
        return dict(
            db.execute(
                text(
                    "SELECT id, sku, name_ar, name_en, base_price, vat_rate, is_active "
                    "FROM master_data.master_product WHERE id=:id"
                ),
                {"id": UUID(product_id)},
            )
            .mappings()
            .one()
        )


def audits(sessions, product_id):
    with sessions() as db:
        return [
            dict(row)
            for row in db.execute(
                text(
                    "SELECT actor_user_id, action, old_values, new_values FROM audit.audit_log "
                    "WHERE entity_type='master_product' AND entity_id=:id ORDER BY created_at, id"
                ),
                {"id": UUID(product_id)},
            ).mappings()
        ]


def test_create_reload_edit_duplicate_activity_and_audit(product_api):
    client, sessions, actor = product_api
    row = create(client, sku="B" + uuid4().hex + "x" * 17)
    assert len(row["sku"]) == 50
    assert persisted(sessions, row["id"])["base_price"] == Decimal("1234567890.12")
    assert persisted(sessions, row["id"])["vat_rate"] == Decimal("7.25")
    assert client.get("/master/products/" + row["id"]).json() == row
    initial_audit = audits(sessions, row["id"])
    assert len(initial_audit) == 1
    assert initial_audit[0]["actor_user_id"] == actor["id"]
    assert initial_audit[0]["action"] == "created"
    assert initial_audit[0]["old_values"] is None
    assert initial_audit[0]["new_values"] == row
    assert (
        client.post("/master/products", json=payload(sku=row["sku"])).status_code == 409
    )
    target = "/master/products/" + row["id"]
    edited = client.patch(target, json={"name_ar": "اسم معدل", "name_en": "Updated"})
    assert edited.status_code == 200
    assert edited.json()["base_price"] == row["base_price"]
    assert edited.json()["vat_rate"] == row["vat_rate"]
    assert persisted(sessions, row["id"])["name_ar"] == "اسم معدل"
    edit_audit = next(
        a for a in audits(sessions, row["id"]) if a["action"] == "updated"
    )
    assert edit_audit["old_values"] == row
    assert edit_audit["new_values"] == edited.json()
    count = len(audits(sessions, row["id"]))
    assert client.patch(target, json={"name_ar": "اسم معدل"}).status_code == 200
    assert len(audits(sessions, row["id"])) == count
    assert client.delete(target).status_code == 204
    assert client.delete(target).status_code == 204
    assert not persisted(sessions, row["id"])["is_active"]
    assert client.get("/master/products", params={"q": row["sku"]}).json() == []
    maintenance = client.get("/master/products-maintenance", params={"q": row["sku"]})
    assert maintenance.status_code == 200
    assert maintenance.json()[0]["id"] == row["id"]
    assert not maintenance.json()[0]["is_active"]
    assert client.patch(target + "/activate").json()["is_active"]
    assert client.patch(target + "/activate").status_code == 200
    assert persisted(sessions, row["id"])["is_active"]
    catalog = client.get("/master/products", params={"q": row["sku"]}).json()
    assert len(catalog) == 1
    assert set(catalog[0]) == {
        "id",
        "sku",
        "name_ar",
        "name_en",
        "base_price",
        "vat_rate",
    }
    records = audits(sessions, row["id"])
    assert len(records) == 4
    assert all(a["actor_user_id"] == actor["id"] for a in records)
    for action, old_active, new_active in [
        ("deactivated", True, False),
        ("activated", False, True),
    ]:
        event = next(a for a in records if a["action"] == action)
        assert event["old_values"]["is_active"] is old_active
        assert event["new_values"]["is_active"] is new_active
        assert (
            event["old_values"]["base_price"]
            == event["new_values"]["base_price"]
            == row["base_price"]
        )
        assert (
            event["old_values"]["vat_rate"]
            == event["new_values"]["vat_rate"]
            == row["vat_rate"]
        )


@pytest.mark.parametrize(
    "role",
    [
        "admin",
        "finance",
        "sales_manager",
        "district_manager",
        "medical_rep",
        "warehouse_staff",
        "read_only_auditor",
    ],
)
def test_denied_roles_even_with_owner_flag(product_api, role):
    client, _sessions, actor = product_api
    actor.update(role=role, is_owner=True)
    target = "/master/products/" + str(uuid4())
    for method, path, body in [
        ("GET", "/master/products-maintenance", None),
        ("GET", target, None),
        ("POST", "/master/products", payload()),
        ("PATCH", target, {"name_ar": "صنف"}),
        ("DELETE", target, None),
        ("PATCH", target + "/activate", None),
    ]:
        assert client.request(method, path, json=body).status_code == 403


@pytest.mark.parametrize("flags", [{"is_active": False}, {"is_owner": False}])
def test_disabled_or_unconfirmed_owner(product_api, flags):
    client, _sessions, actor = product_api
    actor.update(flags)
    target = "/master/products/" + str(uuid4())
    for method, path, body in [
        ("GET", "/master/products-maintenance", None),
        ("GET", target, None),
        ("POST", "/master/products", payload()),
        ("PATCH", target, {"name_ar": "صنف"}),
        ("DELETE", target, None),
        ("PATCH", target + "/activate", None),
    ]:
        assert client.request(method, path, json=body).status_code == 403


@pytest.mark.parametrize(
    "changes",
    [
        {"is_active": True},
        {"created_by": str(uuid4())},
        {"base_price": "0.001"},
        {"vat_rate": "100.01"},
    ],
)
def test_http_invalid_create_has_no_effect(product_api, changes):
    client, sessions, _actor = product_api
    data = payload(**changes)
    assert client.post("/master/products", json=data).status_code == 422
    with sessions() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM master_data.master_product WHERE sku=:sku"),
                {"sku": data["sku"]},
            ).scalar_one()
            == 0
        )


def test_http_patch_financial_forgery_and_missing_rows(product_api):
    client, _sessions, _actor = product_api
    assert client.get("/master/products/not-a-uuid").status_code == 422
    target = "/master/products/" + str(uuid4())
    for field in [
        "base_price",
        "vat_rate",
        "sku",
        "is_active",
        "created_by",
        "verified_cost",
    ]:
        assert (
            client.patch(target, json={"name_ar": "صنف", field: "1"}).status_code == 422
        )
    assert client.get(target).status_code == 404
    assert client.patch(target, json={"name_ar": "صنف"}).status_code == 404
    assert client.delete(target).status_code == 404
    assert client.patch(target + "/activate").status_code == 404


def test_late_audit_failure_rolls_back_all_mutations(product_api, monkeypatch):
    client, sessions, _actor = product_api
    active = create(client)
    inactive = create(client)
    assert client.delete("/master/products/" + inactive["id"]).status_code == 204
    before_counts = {
        r["id"]: len(audits(sessions, r["id"])) for r in [active, inactive]
    }
    original_audit = master.log_audit

    def fail_after_write(*args, **kwargs):
        original_audit(*args, **kwargs)
        raise RuntimeError("Injected failure after audit write")

    monkeypatch.setattr(master, "log_audit", fail_after_write)
    data = payload()
    assert client.post("/master/products", json=data).status_code == 500
    target = "/master/products/" + active["id"]
    assert client.patch(target, json={"name_ar": "must rollback"}).status_code == 500
    assert client.delete(target).status_code == 500
    assert (
        client.patch("/master/products/" + inactive["id"] + "/activate").status_code
        == 500
    )
    assert persisted(sessions, active["id"])["name_ar"] == active["name_ar"]
    assert persisted(sessions, active["id"])["is_active"]
    assert not persisted(sessions, inactive["id"])["is_active"]
    for row in [active, inactive]:
        assert len(audits(sessions, row["id"])) == before_counts[row["id"]]
    with sessions() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM master_data.master_product WHERE sku=:sku"),
                {"sku": data["sku"]},
            ).scalar_one()
            == 0
        )
        assert (
            db.execute(
                text(
                    "SELECT count(*) FROM audit.audit_log WHERE entity_type='master_product' "
                    "AND new_values->>'sku'=:sku"
                ),
                {"sku": data["sku"]},
            ).scalar_one()
            == 0
        )
