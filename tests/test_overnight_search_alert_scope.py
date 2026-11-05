"""R40 authorization: actual HTTP sessions, real grants and synthetic PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from test_invoice_api import invoice_env as invoice_env  # noqa: PLC0414
from test_lane1_r22_territory_http import (
    require_owned_verifier_database as require_owned_verifier_database,  # noqa: PLC0414
)


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "finance",
        "sales_manager",
        "district_manager",
        "medical_rep",
        "read_only_auditor",
    ],
)
def test_search_business_roles_keep_master_territory_scope(invoice_env, role):
    client, db, ids, _payload, headers = invoice_env
    actor = "owner" if role == "owner" else "other"
    if actor == "other":
        db.execute(
            text("UPDATE platform.platform_user SET role=:r WHERE id=:u"),
            {"r": role, "u": ids[actor]},
        )
        db.commit()
    auth = headers(actor)
    own = client.get("/search", params={"q": ids["customer"].hex[:30]}, headers=auth)
    foreign = client.get(
        "/search", params={"q": ids["other_customer"].hex[:30]}, headers=auth
    )
    assert own.status_code == foreign.status_code == 200
    assert [row["id"] for row in own.json()["customers"]] == [str(ids["customer"])]
    assert [row["id"] for row in foreign.json()["customers"]] == (
        [str(ids["other_customer"])] if role == "owner" else []
    )
    assert all(
        set(row) == {"id", "code", "name_ar", "name_en"}
        for row in own.json()["customers"]
    )


@pytest.mark.parametrize("role", ["admin", "private_account", "owner"])
def test_search_rejects_platform_private_and_false_owner_labels(invoice_env, role):
    client, db, ids, _payload, headers = invoice_env
    db.execute(
        text("UPDATE platform.platform_user SET role=:r,is_owner=false WHERE id=:u"),
        {"r": role, "u": ids["other"]},
    )
    db.commit()
    response = client.get("/search?q=Test", headers=headers("other"))
    assert response.status_code == 403, response.text
    assert set(response.json()) == {"detail"}


def test_warehouse_search_returns_products_without_customer_records(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    # An explicit territory grant must not confer a different role's customer view.
    db.execute(
        text("UPDATE platform.platform_user SET role='warehouse_staff' WHERE id=:u"),
        {"u": ids["other"]},
    )
    db.commit()
    response = client.get("/search?q=Test", headers=headers("other"))
    assert response.status_code == 200, response.text
    assert response.json()["customers"] == []
    assert {row["id"] for row in response.json()["products"]} == {
        str(ids["product"]),
        str(ids["exempt"]),
    }


def test_search_rechecks_revoked_territory_on_existing_session(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    auth = headers("other")
    params = {"q": ids["customer"].hex[:30]}
    assert client.get("/search", params=params, headers=auth).json()["customers"]
    db.execute(
        text(
            "DELETE FROM platform.user_territory WHERE user_id=:u AND territory_id=:t"
        ),
        {"u": ids["other"], "t": ids["territory"]},
    )
    db.commit()
    response = client.get("/search", params=params, headers=auth)
    assert response.status_code == 200
    assert response.json()["customers"] == []


@pytest.mark.parametrize(
    "role", ["admin", "medical_rep", "warehouse_staff", "private_account", "owner"]
)
def test_management_alerts_refuse_non_management_and_false_owner_labels(
    invoice_env, role
):
    client, db, ids, _payload, headers = invoice_env
    db.execute(
        text("UPDATE platform.platform_user SET role=:r,is_owner=false WHERE id=:u"),
        {"r": role, "u": ids["other"]},
    )
    db.commit()
    response = client.get(
        "/reports/management-summary?as_of=2026-10-15", headers=headers("other")
    )
    assert response.status_code == 403, response.text
    assert set(response.json()) == {"detail"}


@pytest.mark.parametrize("role", ["sales_manager", "district_manager"])
def test_management_alerts_use_branch_grants_not_territory_or_routes(invoice_env, role):
    client, db, ids, _payload, headers = invoice_env
    branch, warehouse = uuid4(), uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:c,'Other alert branch')"
        ),
        {"id": branch, "c": branch.hex[:20]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:b,:c,'Other alert warehouse')"
        ),
        {"id": warehouse, "b": branch, "c": warehouse.hex[:30]},
    )
    for target in [ids["warehouse"], warehouse]:
        db.execute(
            text(
                "INSERT INTO inventory.stock_balance(warehouse_id,product_id,batch_id,quantity) VALUES (:w,:p,NULL,12.125)"
            ),
            {"w": target, "p": ids["product"]},
        )
    db.execute(
        text("UPDATE platform.platform_user SET role=:r WHERE id=:u"),
        {"r": role, "u": ids["other"]},
    )
    db.commit()
    auth = headers("other")
    before = client.get("/reports/management-summary?as_of=2026-10-15", headers=auth)
    assert before.status_code == 200, before.text
    # No posted sales exist for these fresh products: independent stock SQL is the witness.
    expected = db.execute(
        text(
            "SELECT count(*) FROM inventory.stock_balance s JOIN master_data.master_warehouse w ON w.id=s.warehouse_id JOIN platform.user_branch ub ON ub.branch_id=w.branch_id WHERE ub.user_id=:u AND w.is_active AND s.product_id=:p AND s.quantity>0"
        ),
        {"u": ids["other"], "p": ids["product"]},
    ).scalar_one()
    assert expected == 1
    assert before.json()["inventory_alerts"]["no_sales_history_count"] == expected
    db.execute(
        text("DELETE FROM platform.user_branch WHERE user_id=:u AND branch_id=:b"),
        {"u": ids["other"], "b": ids["branch"]},
    )
    db.commit()
    after = client.get("/reports/management-summary?as_of=2026-10-15", headers=auth)
    assert after.status_code == 200, after.text
    assert after.json()["inventory_alerts"]["no_sales_history_count"] == 0
    assert after.json()["inventory_alerts"]["overstock_count"] == 0
    owner = client.get(
        "/reports/management-summary?as_of=2026-10-15", headers=headers("owner")
    )
    assert owner.status_code == 200
    assert owner.json()["inventory_alerts"]["no_sales_history_count"] >= 2
