"""Real-PostgreSQL controls for explicit branch grants, not fulfillment routes."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

pytest_plugins = ["test_inventory_api"]


@pytest.mark.parametrize("role", ["sales_manager", "district_manager"])
def test_assigned_branch_resolves_real_warehouse_ids(stock_env, role):
    client, db, ids, headers, movement = stock_env
    auth = headers()
    assert (
        client.post("/inventory/movements", json=movement(), headers=auth).status_code
        == 201
    )
    db.execute(
        text("UPDATE platform.platform_user SET role=:role WHERE id=:id"),
        {"role": role, "id": ids["other"]},
    )
    db.execute(
        text("INSERT INTO platform.user_branch VALUES (:u,:b)"),
        {"u": ids["other"], "b": ids["branch"]},
    )
    db.commit()
    scoped = headers("other")
    for path in ("stock", "movements"):
        response = client.get(f"/inventory/{path}", headers=scoped)
        assert response.status_code == 200, response.text
        assert {row["warehouse_id"] for row in response.json()} == {
            str(ids["warehouse"])
        }
        response = client.get(
            f"/inventory/{path}?warehouse_id={ids['warehouse']}", headers=scoped
        )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1


@pytest.mark.parametrize("role", ["sales_manager", "district_manager"])
@pytest.mark.parametrize("kind", ["opening", "adjustment"])
def test_branch_read_grant_does_not_grant_manual_stock_writes(stock_env, role, kind):
    client, db, ids, headers, movement = stock_env
    db.execute(
        text("UPDATE platform.platform_user SET role=:r WHERE id=:u"),
        {"r": role, "u": ids["other"]},
    )
    db.execute(
        text("INSERT INTO platform.user_branch VALUES (:u,:b)"),
        {"u": ids["other"], "b": ids["branch"]},
    )
    db.commit()
    payload = movement(movement_type=kind)
    if kind == "adjustment":
        payload["reason_id"] = str(ids["reason"])
    response = client.post(
        "/inventory/movements", json=payload, headers=headers("other")
    )
    assert response.status_code == 403, response.text
    for table in ("stock_balance", "stock_movement"):
        assert (
            db.execute(text(f"SELECT count(*) FROM inventory.{table}")).scalar_one()
            == 0
        )


@pytest.mark.parametrize("role", ["sales_manager", "district_manager"])
def test_shared_warehouse_movements_do_not_leak_other_territories(stock_env, role):
    from app.sales.service import post_invoice_atomic

    client, db, ids, headers, movement = stock_env
    auth = headers()
    assert (
        client.post(
            "/inventory/movements", json=movement(quantity="20"), headers=auth
        ).status_code
        == 201
    )
    invoices = []
    territories = []
    # All three territories use one physical warehouse. Distinct territory ids
    # must survive in sales, not be inferred from that source warehouse.
    for name in ("Dakahlia", "Sharqia", "Gharbia"):
        territory, customer = uuid4(), uuid4()
        territories.append(territory)
        db.execute(
            text(
                "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:t,:c,:n)"
            ),
            {"t": territory, "c": territory.hex[:20], "n": name},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
                "VALUES (:c,:code,:n,:b,:t)"
            ),
            {
                "c": customer,
                "code": customer.hex[:30],
                "n": name,
                "b": ids["branch"],
                "t": territory,
            },
        )
        db.commit()
        response = client.post(
            "/invoices",
            headers=auth,
            json={
                "invoice_no": uuid4().hex[:20],
                "branch_id": str(ids["branch"]),
                "warehouse_id": str(ids["warehouse"]),
                "customer_id": str(customer),
                "invoice_date": date(2026, 1, 15).isoformat(),
                "lines": [
                    {
                        "product_id": str(ids["product"]),
                        "quantity": "1",
                        "discount_pct": "0",
                    }
                ],
            },
        )
        assert response.status_code == 201, response.text
        invoice = response.json()
        assert invoice["territory_id"] == str(territory)
        assert (
            client.post(f"/invoices/{invoice['id']}/post", headers=auth).status_code
            == 409
        )
        # Exercise existing transaction directly; never open the HTTP gate.
        post_invoice_atomic(db, UUID(invoice["id"]), ids["owner"])
        db.commit()
        invoices.append(invoice)
    db.execute(
        text("UPDATE platform.platform_user SET role=:r WHERE id=:u"),
        {"r": role, "u": ids["other"]},
    )
    db.execute(
        text("INSERT INTO platform.user_branch VALUES (:u,:b)"),
        {"u": ids["other"], "b": ids["branch"]},
    )
    db.execute(
        text("INSERT INTO platform.user_territory VALUES (:u,:t)"),
        {"u": ids["other"], "t": territories[0]},
    )
    db.commit()
    scoped = headers("other")
    for query in (
        "",
        f"?warehouse_id={ids['warehouse']}",
        "?movement_type=sale",
        f"?product_id={ids['product']}",
    ):
        response = client.get("/inventory/movements" + query, headers=scoped)
        assert response.status_code == 200, response.text
        sales = [row for row in response.json() if row["source_type"] == "invoice"]
        assert {row["source_id"] for row in sales} == {invoices[0]["id"]}
    for invoice in invoices[1:]:
        assert (
            client.get(f"/invoices/{invoice['id']}", headers=scoped).status_code == 404
        )
    # Removing territory authority removes sale-detail access, not branch stock.
    db.execute(
        text("DELETE FROM platform.user_territory WHERE user_id=:u"),
        {"u": ids["other"]},
    )
    db.commit()
    response = client.get("/inventory/movements?movement_type=sale", headers=scoped)
    assert response.status_code == 200 and response.json() == []
    assert client.get("/inventory/stock", headers=scoped).status_code == 200


@pytest.mark.parametrize("role", ["sales_manager", "district_manager"])
@pytest.mark.parametrize("home", ["Sharqia", "Gharbia"])
def test_fulfillment_routes_and_territory_do_not_grant_shared_stock(
    stock_env, role, home
):
    client, db, ids, headers, movement = stock_env
    branches = {"Dakahlia": ids["branch"], "Sharqia": uuid4(), "Gharbia": uuid4()}
    for name in ("Sharqia", "Gharbia"):
        db.execute(
            text(
                "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:c,:n)"
            ),
            {"id": branches[name], "c": branches[name].hex[:20], "n": name},
        )
    db.execute(
        text("UPDATE master_data.master_warehouse SET branch_id=:g WHERE id=:w"),
        {"g": branches["Gharbia"], "w": ids["other_warehouse"]},
    )
    # Compatibility only: D + S use D; G may use D or G. No access grants.
    for name, key in (
        ("Dakahlia", "warehouse"),
        ("Sharqia", "warehouse"),
        ("Gharbia", "warehouse"),
        ("Gharbia", "other_warehouse"),
    ):
        db.execute(
            text("INSERT INTO inventory.branch_warehouse VALUES (:b,:w)"),
            {"b": branches[name], "w": ids[key]},
        )
    territory = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:t,:c,:n)"
        ),
        {"t": territory, "c": territory.hex[:20], "n": home},
    )
    db.execute(
        text("INSERT INTO platform.user_territory VALUES (:u,:t)"),
        {"u": ids["other"], "t": territory},
    )
    db.execute(
        text("UPDATE platform.platform_user SET role=:r WHERE id=:u"),
        {"r": role, "u": ids["other"]},
    )
    db.execute(
        text("INSERT INTO platform.user_branch VALUES (:u,:b)"),
        {"u": ids["other"], "b": branches[home]},
    )
    db.commit()
    owner = headers()
    for key in ("warehouse", "other_warehouse"):
        assert (
            client.post(
                "/inventory/movements",
                json=movement(warehouse_id=str(ids[key])),
                headers=owner,
            ).status_code
            == 201
        )
    scoped = headers("other")
    for path in ("stock", "movements"):
        response = client.get(f"/inventory/{path}", headers=scoped)
        if home == "Sharqia":
            assert response.status_code == 403
        else:
            assert response.status_code == 200, response.text
            assert {r["warehouse_id"] for r in response.json()} == {
                str(ids["other_warehouse"])
            }
        assert client.get(
            f"/inventory/{path}?warehouse_id={ids['warehouse']}", headers=scoped
        ).status_code in (403, 404)
    assert (
        client.post("/inventory/movements", json=movement(), headers=scoped).status_code
        == 403
    )
    # Only an explicit D branch assignment can expose its stock pool.
    db.execute(
        text("INSERT INTO platform.user_branch VALUES (:u,:b)"),
        {"u": ids["other"], "b": branches["Dakahlia"]},
    )
    db.commit()
    expected = {str(ids["warehouse"])}
    if home == "Gharbia":
        expected.add(str(ids["other_warehouse"]))
    for path in ("stock", "movements"):
        response = client.get(f"/inventory/{path}", headers=scoped)
        assert response.status_code == 200, response.text
        assert {r["warehouse_id"] for r in response.json()} == expected


@pytest.mark.parametrize("role", ["sales_manager", "district_manager"])
def test_foreign_warehouse_cannot_be_queried_or_leak_through_filters(stock_env, role):
    client, db, ids, headers, movement = stock_env
    foreign = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:b,:c,'Foreign')"
        ),
        {"b": foreign, "c": foreign.hex[:20]},
    )
    db.execute(
        text("UPDATE master_data.master_warehouse SET branch_id=:b WHERE id=:w"),
        {"b": foreign, "w": ids["other_warehouse"]},
    )
    db.execute(
        text("UPDATE platform.platform_user SET role=:r WHERE id=:u"),
        {"r": role, "u": ids["other"]},
    )
    db.execute(
        text("INSERT INTO platform.user_branch VALUES (:u,:b)"),
        {"u": ids["other"], "b": ids["branch"]},
    )
    db.commit()
    auth = headers()
    for key in ("warehouse", "other_warehouse"):
        assert (
            client.post(
                "/inventory/movements",
                headers=auth,
                json=movement(warehouse_id=str(ids[key])),
            ).status_code
            == 201
        )
    scoped = headers("other")
    for path in ("stock", "movements"):
        for query in ("", f"?product_id={ids['product']}"):
            response = client.get(f"/inventory/{path}{query}", headers=scoped)
            assert response.status_code == 200, response.text
            assert {r["warehouse_id"] for r in response.json()} == {
                str(ids["warehouse"])
            }
        for w in (ids["other_warehouse"], uuid4()):
            response = client.get(f"/inventory/{path}?warehouse_id={w}", headers=scoped)
            assert response.status_code == 404, response.text
    # Existing sessions must lose access when the branch grant is removed.
    db.execute(
        text("DELETE FROM platform.user_branch WHERE user_id=:u"), {"u": ids["other"]}
    )
    db.commit()
    for path in ("stock", "movements"):
        assert client.get(f"/inventory/{path}", headers=scoped).status_code == 403


@pytest.mark.parametrize(
    "role", ["sales_manager", "district_manager", "medical_rep", "admin", "user"]
)
def test_branch_assignment_is_not_a_role_or_active_user_bypass(stock_env, role):
    client, db, ids, headers, movement = stock_env
    db.execute(
        text("UPDATE platform.platform_user SET role=:r WHERE id=:u"),
        {"r": role, "u": ids["other"]},
    )
    db.execute(
        text("INSERT INTO platform.user_branch VALUES (:u,:b)"),
        {"u": ids["other"], "b": ids["branch"]},
    )
    db.commit()
    scoped = headers("other")
    expected = 200 if role in {"sales_manager", "district_manager"} else 403
    for path in ("stock", "movements"):
        assert client.get(f"/inventory/{path}", headers=scoped).status_code == expected
    db.execute(
        text("UPDATE platform.platform_user SET is_active=false WHERE id=:u"),
        {"u": ids["other"]},
    )
    db.commit()
    for path in ("stock", "movements"):
        assert client.get(f"/inventory/{path}", headers=scoped).status_code == 401
    assert (
        client.post("/inventory/movements", json=movement(), headers=scoped).status_code
        == 401
    )


def test_branch_uuid_collision_cannot_grant_foreign_warehouse(stock_env):
    client, db, ids, headers, movement = stock_env
    foreign = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:b,:c,'Foreign')"
        ),
        {"b": foreign, "c": foreign.hex[:20]},
    )
    # Deliberate cross-table UUID collision; FK types do not confer authority.
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
            "VALUES (:w,:b,:c,'Foreign warehouse')"
        ),
        {"w": ids["branch"], "b": foreign, "c": foreign.hex[:20]},
    )
    db.execute(
        text("UPDATE platform.platform_user SET role='district_manager' WHERE id=:u"),
        {"u": ids["other"]},
    )
    db.execute(
        text("INSERT INTO platform.user_branch VALUES (:u,:b)"),
        {"u": ids["other"], "b": ids["branch"]},
    )
    db.commit()
    assert (
        client.post(
            "/inventory/movements",
            headers=headers(),
            json=movement(warehouse_id=str(ids["branch"])),
        ).status_code
        == 201
    )
    scoped = headers("other")
    for path in ("stock", "movements"):
        response = client.get(f"/inventory/{path}", headers=scoped)
        assert response.status_code == 200 and response.json() == []
        assert (
            client.get(
                f"/inventory/{path}?warehouse_id={ids['branch']}", headers=scoped
            ).status_code
            == 404
        )
