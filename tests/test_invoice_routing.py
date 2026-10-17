"""Sales source-warehouse routing: cross-branch sourcing via inventory.branch_warehouse.

Real PostgreSQL, TestClient. Exercises the decoupled FK (0009) and the new
_warehouse_scope + route checks in app/sales/router.py::_prepare.
"""

from uuid import uuid4

from sqlalchemy import text

pytest_plugins = ["test_invoice_api"]  # reuse the real-Postgres invoice_env fixture


def _setup_branches(db, ids):
    """Create Dakahlia/Sharqia/Gharbia branches, shared warehouses and routes."""
    for name in ("dakahlia", "sharpia", "gharbia", "route_customer", "route_territory"):
        ids[name] = uuid4()
    ids["dakahlia_warehouse"] = uuid4()
    ids["gharbia_warehouse"] = uuid4()
    for name in ("dakahlia", "sharpia", "gharbia"):
        db.execute(
            text(
                "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:c,:n)"
            ),
            {"id": ids[name], "c": ids[name].hex[:20], "n": name},
        )
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:b,:c,'Dakahlia shared')"
        ),
        {
            "id": ids["dakahlia_warehouse"],
            "b": ids["dakahlia"],
            "c": ids["dakahlia_warehouse"].hex[:30],
        },
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:b,:c,'Gharbia shared')"
        ),
        {
            "id": ids["gharbia_warehouse"],
            "b": ids["gharbia"],
            "c": ids["gharbia_warehouse"].hex[:30],
        },
    )
    # Fulfillment routes: Sharqia may source from Dakahlia; Gharbia from Gharbia only.
    db.execute(
        text(
            "INSERT INTO inventory.branch_warehouse(branch_id,warehouse_id) VALUES (:b,:w)"
        ),
        {"b": ids["sharpia"], "w": ids["dakahlia_warehouse"]},
    )
    db.execute(
        text(
            "INSERT INTO inventory.branch_warehouse(branch_id,warehouse_id) VALUES (:b,:w)"
        ),
        {"b": ids["gharbia"], "w": ids["gharbia_warehouse"]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:t,:c,'Route territory')"
        ),
        {"t": ids["route_territory"], "c": ids["route_territory"].hex[:20]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:c,'Route customer',:b,:t)"
        ),
        {
            "id": ids["route_customer"],
            "c": ids["route_customer"].hex[:30],
            "b": ids["sharpia"],
            "t": ids["route_territory"],
        },
    )
    db.commit()


def _sharqia_caller(
    db, ids, *, grant_sharqia=True, grant_dakahlia=False, grant_gharbia=False
):
    """sales_manager caller on the route territory; grants the needed branches."""
    db.execute(
        text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.execute(
        text(
            "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t) ON CONFLICT DO NOTHING"
        ),
        {"u": ids["other"], "t": ids["route_territory"]},
    )
    if grant_sharqia:
        db.execute(
            text(
                "INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b) ON CONFLICT DO NOTHING"
            ),
            {"u": ids["other"], "b": ids["sharpia"]},
        )
    if grant_dakahlia:
        db.execute(
            text(
                "INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b) ON CONFLICT DO NOTHING"
            ),
            {"u": ids["other"], "b": ids["dakahlia"]},
        )
    if grant_gharbia:
        db.execute(
            text(
                "INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b) ON CONFLICT DO NOTHING"
            ),
            {"u": ids["other"], "b": ids["gharbia"]},
        )
    db.commit()


def _sharqia_payload(ids):
    return {
        "invoice_no": f"S-{uuid4().hex[:20]}",
        "branch_id": str(ids["sharpia"]),
        "warehouse_id": str(ids["dakahlia_warehouse"]),
        "customer_id": str(ids["route_customer"]),
        "invoice_date": "2026-10-17",
        "lines": [
            {"product_id": str(ids["product"]), "quantity": "1", "discount_pct": "0"}
        ],
    }


def test_shared_dakahlia_source_allowed_for_routed_sharqia_branch(invoice_env):
    client, db, ids, payload, headers = invoice_env
    _setup_branches(db, ids)
    # Caller assigned to both sharqia (invoice branch) and dakahlia (source warehouse).
    _sharqia_caller(db, ids, grant_sharqia=True, grant_dakahlia=True)
    response = client.post(
        "/invoices", json=_sharqia_payload(ids), headers=headers("other")
    )
    assert response.status_code == 201, response.text
    assert response.json()["warehouse_id"] == str(ids["dakahlia_warehouse"])


def test_unrouted_shared_warehouse_rejected_for_incompatible_branch(invoice_env):
    client, db, ids, payload, headers = invoice_env
    _setup_branches(db, ids)
    # Caller has explicit access to both sharqia and gharbia warehouses, but
    # sharqia has no route to gharbia's own warehouse — hits the 'not served' gate.
    _sharqia_caller(
        db, ids, grant_sharqia=True, grant_dakahlia=False, grant_gharbia=True
    )
    p = _sharqia_payload(ids)
    p["warehouse_id"] = str(ids["gharbia_warehouse"])
    response = client.post("/invoices", json=p, headers=headers("other"))
    assert response.status_code == 422, response.text
    assert "not served" in response.json()["detail"].lower()


def test_warehouse_not_assigned_to_caller_is_hidden(invoice_env):
    client, db, ids, payload, headers = invoice_env
    _setup_branches(db, ids)
    # Route exists but the caller has no user_branch grant for the owning branch.
    _sharqia_caller(db, ids, grant_sharqia=True, grant_dakahlia=False)
    response = client.post(
        "/invoices", json=_sharqia_payload(ids), headers=headers("other")
    )
    assert response.status_code == 404, response.text


def test_own_branch_warehouse_still_allowed(invoice_env):
    """Regression: same-branch sourcing still 201 (existing invoice_env data)."""
    client, db, ids, payload, headers = invoice_env
    response = client.post("/invoices", json=payload, headers=headers())
    assert response.status_code == 201, response.text
    assert response.json()["warehouse_id"] == str(ids["warehouse"])
