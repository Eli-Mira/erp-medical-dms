"""Approved single phone/address fields; actual disposable PostgreSQL HTTP writes."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_customer_creation import (
    create_customer,
    customer_snapshot,
)
from test_customer_creation import (
    customer_creation_env as customer_creation_env,  # noqa: PLC0414 - pytest fixture re-export
)


@pytest.fixture
def contact_env(customer_creation_env):
    # Keep committed test contacts out of later directory/browser baselines.
    client, engine, ids, auth, payload = customer_creation_env
    with engine.connect() as db:
        assert not db.scalar(
            text(
                "SELECT EXISTS(SELECT 1 FROM master_data.master_customer WHERE branch_id=:branch AND territory_id=:territory)"
            ),
            ids,
        )
    try:
        yield client, engine, ids, auth, payload
    finally:
        with engine.begin() as db:
            db.execute(
                text(
                    "DELETE FROM master_data.master_customer WHERE branch_id=:branch AND territory_id=:territory"
                ),
                ids,
            )
        # Immutable actor-bound audit rows remain until the runner drops its UUID DB.


def test_contact_patch_persists_and_audits_without_touching_identity(
    contact_env,
):
    client, engine, ids, auth, _payload = contact_env
    customer = create_customer(contact_env)
    before = customer_snapshot(engine, customer["id"])
    change = {
        "contact_phone": "  010 1234-5678 / 02 1234 5678  ",
        "address": "  ١٢ شارع النيل\nالدور الثاني، الجيزة  ",
    }
    response = client.patch(
        "/master/customers/" + customer["id"], headers=auth, json=change
    )
    assert response.status_code == 200, response.text
    expected = {
        "contact_phone": change["contact_phone"].strip(),
        "address": change["address"].strip(),
    }
    body = response.json()
    assert {key: body[key] for key in expected} == expected
    assert {key: body[key] for key in customer if key not in expected} == {
        key: customer[key] for key in customer if key not in expected
    }
    after = customer_snapshot(engine, customer["id"])
    assert {key: after["customer"][key] for key in expected} == expected
    assert {
        key: value for key, value in after["customer"].items() if key not in expected
    } == {
        key: value for key, value in before["customer"].items() if key not in expected
    }
    assert len(after["audits"]) == len(before["audits"]) + 1
    event = next(event for event in after["audits"] if event["action"] == "updated")
    assert event["entity_id"] == UUID(customer["id"])
    assert event["actor_user_id"] == ids["owner"]
    assert event["old_values"] == customer and event["new_values"] == body
    assert event["created_at"].tzinfo is not None
    assert (
        client.get("/master/customers/" + customer["id"], headers=auth).json() == body
    )
    assert (
        next(
            row
            for row in client.get("/master/customers", headers=auth).json()
            if row["id"] == customer["id"]
        )
        == body
    )


def test_create_accepts_optional_contacts(contact_env):
    client, engine, _ids, auth, payload = contact_env
    contacts = {"contact_phone": "02 (2345) 6789", "address": "Cairo - 12 شارع التحرير"}
    response = client.post(
        "/master/customers", headers=auth, json={**payload, **contacts}
    )
    assert response.status_code == 201, response.text
    assert {key: response.json()[key] for key in contacts} == contacts
    assert {
        key: customer_snapshot(engine, response.json()["id"])["customer"][key]
        for key in contacts
    } == contacts


@pytest.mark.parametrize("field", ["contact_phone", "address"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_contact_clear_and_noop_are_consistent(contact_env, field, value):
    client, engine, _ids, auth, _payload = contact_env
    customer = create_customer(contact_env)
    url = "/master/customers/" + customer["id"]
    assert (
        client.patch(
            url,
            headers=auth,
            json={"contact_phone": "010 1234 5678", "address": "عنوان اختباري"},
        ).status_code
        == 200
    )
    before = customer_snapshot(engine, customer["id"])
    response = client.patch(url, headers=auth, json={field: value})
    assert response.status_code == 200 and response.json()[field] is None
    after = customer_snapshot(engine, customer["id"])
    assert after["customer"][field] is None
    assert {k: v for k, v in after["customer"].items() if k != field} == {
        k: v for k, v in before["customer"].items() if k != field
    }
    assert len(after["audits"]) == len(before["audits"]) + 1
    assert client.patch(url, headers=auth, json={field: value}).status_code == 200
    assert customer_snapshot(engine, customer["id"]) == after


@pytest.mark.parametrize("method", ["patch", "post"])
@pytest.mark.parametrize(
    "bad",
    [
        {"contact_phone": "x" * 31},
        {"contact_phone": 123},
        {"contact_phone": True},
        {"contact_phone": ["01012345678"]},
        {"address": {"city": "Cairo"}},
        {"contact_phone": "010\x00bad"},
        {"address": "bad\x00address"},
        {"phone_numbers": ["01012345678"]},
        {"actor_user_id": str(UUID(int=1))},
    ],
)
def test_invalid_contacts_and_unknown_fields_do_not_write(contact_env, method, bad):
    client, engine, _ids, auth, payload = contact_env
    customer = create_customer(contact_env)
    before = customer_snapshot(engine, customer["id"])
    with engine.connect() as db:
        count = db.scalar(text("SELECT count(*) FROM master_data.master_customer"))
    response = (
        client.patch("/master/customers/" + customer["id"], headers=auth, json=bad)
        if method == "patch"
        else client.post(
            "/master/customers",
            headers=auth,
            json={**payload, "code": uuid4().hex[:20], **bad},
        )
    )
    assert response.status_code == 422, response.text
    assert customer_snapshot(engine, customer["id"]) == before
    with engine.connect() as db:
        assert (
            db.scalar(text("SELECT count(*) FROM master_data.master_customer")) == count
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
def test_contact_patch_requires_active_owner_and_owner_flag(
    contact_env, role, owner, active, status
):
    client, engine, ids, auth, _payload = contact_env
    customer = create_customer(contact_env)
    before = customer_snapshot(engine, customer["id"])
    with engine.begin() as db:
        db.execute(
            text(
                "UPDATE platform.platform_user SET role=:role,is_owner=:owner,is_active=:active WHERE id=:id"
            ),
            {"id": ids["owner"], "role": role, "owner": owner, "active": active},
        )
    response = client.patch(
        "/master/customers/" + customer["id"],
        headers=auth,
        json={"contact_phone": "01012345678"},
    )
    assert response.status_code == status
    assert customer_snapshot(engine, customer["id"]) == before


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer " + str(UUID(int=1))}]
)
def test_contact_patch_requires_real_session(contact_env, headers):
    client, engine, _ids, _auth, _payload = contact_env
    customer = create_customer(contact_env)
    before = customer_snapshot(engine, customer["id"])
    assert client.patch(
        "/master/customers/" + customer["id"],
        headers=headers,
        json={"address": "Not allowed"},
    ).status_code in {401, 403}
    assert customer_snapshot(engine, customer["id"]) == before


@pytest.mark.parametrize("fault", ["audit_before", "audit_after", "commit"])
def test_contact_and_audit_rollback_together(contact_env, monkeypatch, fault):
    from app.master import router as master_router

    client, engine, _ids, auth, _payload = contact_env
    customer = create_customer(contact_env)
    before = customer_snapshot(engine, customer["id"])
    real_audit = master_router.log_audit

    def fail_audit(*args, **kwargs):
        if fault == "audit_after":
            real_audit(*args, **kwargs)
        raise RuntimeError("synthetic contact failure")

    def fail_commit(_self):
        raise RuntimeError("synthetic contact failure")

    with monkeypatch.context() as patcher:
        patcher.setattr(
            Session, "commit", fail_commit
        ) if fault == "commit" else patcher.setattr(
            master_router, "log_audit", fail_audit
        )
        with pytest.raises(RuntimeError, match="synthetic contact failure"):
            client.patch(
                "/master/customers/" + customer["id"],
                headers=auth,
                json={"contact_phone": "01012345678", "address": "Synthetic address"},
            )
    assert customer_snapshot(engine, customer["id"]) == before


@pytest.mark.parametrize("is_active", [True, False])
def test_contact_noops_empty_patch_and_inactive_rules(contact_env, is_active):
    client, engine, _ids, auth, _payload = contact_env
    customer = create_customer(contact_env)
    url = "/master/customers/" + customer["id"]
    if not is_active:
        assert client.delete(url, headers=auth).status_code == 204
    body = {"contact_phone": "٠١٠ ١٢٣٤ ٥٦٧٨", "address": "١٢ شارع التحرير"}
    response = client.patch(url, headers=auth, json=body)
    assert response.status_code == 200 and response.json()["is_active"] is is_active
    before = customer_snapshot(engine, customer["id"])
    assert client.patch(url, headers=auth, json=body).json() == response.json()
    assert client.patch(url, headers=auth, json={}).status_code == 422
    assert customer_snapshot(engine, customer["id"]) == before
    assert (
        customer["id"]
        in {r["id"] for r in client.get("/master/customers", headers=auth).json()}
    ) is is_active


@pytest.mark.parametrize(
    "forbidden", ["id", "code", "branch_id", "territory_id", "is_active"]
)
def test_contact_patch_cannot_reassign_customer(contact_env, forbidden):
    client, engine, _ids, auth, _payload = contact_env
    customer = create_customer(contact_env)
    before = customer_snapshot(engine, customer["id"])
    bad = {
        forbidden: False if forbidden == "is_active" else str(uuid4()),
        "address": "Should not persist",
    }
    assert (
        client.patch(
            "/master/customers/" + customer["id"], headers=auth, json=bad
        ).status_code
        == 422
    )
    assert customer_snapshot(engine, customer["id"]) == before


def test_missing_customer_patch_does_not_audit(contact_env):
    client, engine, _ids, auth, _payload = contact_env
    cid = uuid4()
    assert (
        client.patch(
            "/master/customers/" + str(cid), headers=auth, json={"address": "Synthetic"}
        ).status_code
        == 404
    )
    with engine.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit.audit_log WHERE entity_id=:id"),
                {"id": cid},
            )
            == 0
        )


def test_contacts_are_not_unique_and_queries_remain_parameterized(contact_env, caplog):
    client, engine, _ids, auth, payload = contact_env
    contacts = {
        "contact_phone": "010');--",
        "address": "<script>alert('synthetic')</script> - شارع اختباري",
    }
    ids = []
    for _ in range(2):
        response = client.post(
            "/master/customers",
            headers=auth,
            json={**payload, "code": uuid4().hex[:20], **contacts},
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
        assert {
            k: customer_snapshot(engine, response.json()["id"])["customer"][k]
            for k in contacts
        } == contacts
    assert ids[0] != ids[1]
    assert all(
        contacts["address"] not in record.getMessage()
        and contacts["contact_phone"] not in record.getMessage()
        for record in caplog.records
    )


def test_contact_reads_do_not_bypass_territory_permissions(contact_env):
    client, engine, ids, auth, _payload = contact_env
    customer = create_customer(contact_env)
    url = "/master/customers/" + customer["id"]
    contacts = {"contact_phone": "010 1234 5678", "address": "عنوان مصرح به"}
    assert client.patch(url, headers=auth, json=contacts).status_code == 200
    with engine.begin() as db:
        db.execute(
            text(
                "UPDATE platform.platform_user SET role='medical_rep',is_owner=false WHERE id=:id"
            ),
            {"id": ids["owner"]},
        )
    assert client.get(url, headers=auth).status_code == 404
    assert client.get("/master/customers", headers=auth).json() == []
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:owner,:territory)"
            ),
            ids,
        )
    assert {k: client.get(url, headers=auth).json()[k] for k in contacts} == contacts


def test_migration_refuses_to_discard_populated_contacts(contact_env):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    client, engine, _ids, auth, _payload = contact_env
    customer = create_customer(contact_env)
    assert (
        client.patch(
            "/master/customers/" + customer["id"],
            headers=auth,
            json={"address": "Do not lose this"},
        ).status_code
        == 200
    )
    before = customer_snapshot(engine, customer["id"])
    spec = importlib.util.spec_from_file_location(
        "customer_contacts_migration",
        Path("alembic/versions/0016_customer_contacts.py"),
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with (
        engine.begin() as db,
        Operations.context(MigrationContext.configure(db)),
        pytest.raises(RuntimeError, match="contact data must be preserved"),
    ):
        migration.downgrade()
    assert customer_snapshot(engine, customer["id"]) == before


def test_contact_downgrade_excludes_concurrent_contact_writes(contact_env, monkeypatch):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.exc import OperationalError

    _client, engine, _ids, _auth, _payload = contact_env
    customer = create_customer(contact_env)
    spec = importlib.util.spec_from_file_location(
        "customer_contacts_lock_migration",
        Path("alembic/versions/0016_customer_contacts.py"),
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    observed = []
    with engine.connect() as db:
        transaction = db.begin()

        class CheckedBind:
            def execute(self, statement):
                result = db.execute(statement)
                if str(statement).startswith("SELECT EXISTS"):
                    blocked = False
                    try:
                        with engine.begin() as concurrent:
                            concurrent.execute(text("SET LOCAL lock_timeout = '100ms'"))
                            concurrent.execute(
                                text(
                                    "UPDATE master_data.master_customer SET contact_phone='SYNTHETIC-RACE' WHERE id=:id"
                                ),
                                {"id": customer["id"]},
                            )
                    except OperationalError as error:
                        assert error.orig.sqlstate == "55P03"
                        blocked = True
                    observed.append(blocked)
                    assert blocked, (
                        "A contact write committed between downgrade's data check and column removal"
                    )
                return result

        try:
            with Operations.context(MigrationContext.configure(db)):
                monkeypatch.setattr(migration.op, "get_bind", lambda: CheckedBind())
                try:
                    migration.downgrade()
                except RuntimeError as error:
                    assert (
                        str(error)
                        == "Cannot downgrade: customer contact data must be preserved"
                    )
        finally:
            transaction.rollback()
    assert observed == [True]
    assert (
        customer_snapshot(engine, customer["id"])["customer"]["contact_phone"] is None
    )
