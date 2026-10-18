"""Master-data lookup API that feeds the invoice screen.

Scope must mirror invoice creation, so these tests reuse the posting seed
(owner + branch/territory/customer/warehouse/product) and assert the lookups
only expose references the write path would accept.

Runs only on the disposable ``dms_cycle_test_*`` database (conftest guard).
"""
from uuid import uuid4

from sqlalchemy import text

MASTER_PATHS = (
    "/master/branches",
    "/master/warehouses",
    "/master/customers",
    "/master/products",
)


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


def test_master_reads_require_a_session(posting_env):
    client, *_ = posting_env
    for path in MASTER_PATHS:
        assert client.get(path).status_code in (401, 403), path


def test_owner_sees_seeded_references(posting_env):
    client, _db, ids, auth, _invoice, _payload = posting_env

    branches = client.get("/master/branches", headers=auth).json()
    assert str(ids["branch"]) in {row["id"] for row in branches}

    customers = client.get("/master/customers", headers=auth).json()
    seeded = next(c for c in customers if c["id"] == str(ids["customer"]))
    assert seeded["branch_id"] == str(ids["branch"])
    assert seeded["territory_id"] == str(ids["territory"])
    assert all(c["territory_id"] for c in customers)

    products = client.get("/master/products", headers=auth).json()
    assert str(ids["product"]) in {row["id"] for row in products}

    warehouses = client.get("/master/warehouses", headers=auth).json()
    assert str(ids["warehouse"]) in {row["id"] for row in warehouses}


def test_warehouse_branch_filter_keeps_owned_and_routed(posting_env):
    client, db, ids, auth, _invoice, _payload = posting_env
    other_branch, owned_elsewhere, routed = uuid4(), uuid4(), uuid4()
    db.execute(
        text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:c,'Other branch')"),
        {"id": other_branch, "c": other_branch.hex[:20]},
    )
    for wid, name in ((owned_elsewhere, "Elsewhere"), (routed, "Routed")):
        db.execute(
            text(
                "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) "
                "VALUES (:id,:b,:c,:n)"
            ),
            {"id": wid, "b": other_branch, "c": wid.hex[:20], "n": name},
        )
    db.execute(
        text("INSERT INTO inventory.branch_warehouse(branch_id,warehouse_id) VALUES (:b,:w)"),
        {"b": ids["branch"], "w": routed},
    )
    db.commit()

    rows = client.get(f"/master/warehouses?branch_id={ids['branch']}", headers=auth).json()
    visible = {row["id"] for row in rows}
    assert str(ids["warehouse"]) in visible  # owns the branch
    assert str(routed) in visible            # routed to the branch
    assert str(owned_elsewhere) not in visible


def test_rep_sees_only_granted_territories(posting_env):
    client, db, ids, _owner_auth, _invoice, _payload = posting_env
    other_territory, other_customer, rep = uuid4(), uuid4(), uuid4()
    db.execute(
        text("INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:c,'Other territory')"),
        {"id": other_territory, "c": other_territory.hex[:20]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
            "VALUES (:id,:c,'Other customer',:b,:t)"
        ),
        {"id": other_customer, "c": other_customer.hex[:30], "b": ids["branch"], "t": other_territory},
    )
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
            "VALUES (:id,:u,'unused','medical_rep',false)"
        ),
        {"id": rep, "u": f"rep_{rep.hex}"},
    )
    db.execute(
        text("INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t)"),
        {"u": rep, "t": ids["territory"]},
    )
    db.commit()

    auth = _login_as(db, rep)
    visible = {row["id"] for row in client.get("/master/customers", headers=auth).json()}
    assert str(ids["customer"]) in visible
    assert str(other_customer) not in visible


def test_lookup_references_build_a_server_priced_draft(posting_env):
    client, _db, ids, auth, _invoice, _payload = posting_env
    customer = next(
        c for c in client.get("/master/customers", headers=auth).json()
        if c["id"] == str(ids["customer"])
    )
    product = next(
        p for p in client.get("/master/products", headers=auth).json()
        if p["id"] == str(ids["product"])
    )
    warehouse = next(
        w for w in client.get(
            f"/master/warehouses?branch_id={customer['branch_id']}", headers=auth
        ).json()
        if w["id"] == str(ids["warehouse"])
    )

    assert product["base_price"] == "114.00"
    assert product["vat_rate"] == "14.00"

    payload = {
        "invoice_no": f"UI-{uuid4().hex[:20]}",
        "branch_id": customer["branch_id"],
        "warehouse_id": warehouse["id"],
        "customer_id": customer["id"],
        "invoice_date": _payload["invoice_date"],
        "lines": [{"product_id": product["id"], "quantity": "3", "discount_pct": "10"}],
    }
    response = client.post("/invoices", json=payload, headers=auth)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["posting_status"] == "Draft"
    # 3 x 114 with 10% -> 102.60/unit, 307.80 incl-VAT at 14%
    assert body["lines"][0]["unit_price"] == "114.00"
    assert body["lines"][0]["net_price"] == "102.60"
    assert body["lines"][0]["line_total"] == "307.80"
    assert body["total_before_discount"] == "342.00"
    assert body["total_discount"] == "34.20"
    assert body["total_net"] == "270.00"
    assert body["vat_amount"] == "37.80"
    assert body["grand_total"] == "307.80"


def test_posting_gate_stays_closed_for_the_ui(posting_env):
    client, _db, _ids, auth, invoice, _payload = posting_env
    response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    assert response.status_code == 409
    assert "disabled" in response.json()["detail"].lower()
    detail = client.get(f"/invoices/{invoice['id']}", headers=auth).json()
    assert detail["posting_status"] == "Draft"


def test_roles_outside_the_read_set_are_denied(posting_env):
    client, db, _ids, _owner_auth, _invoice, _payload = posting_env
    warehouse_staff, fake_owner = uuid4(), uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
            "VALUES (:id,:u,'unused','warehouse_staff',false)"
        ),
        {"id": warehouse_staff, "u": f"ws_{warehouse_staff.hex}"},
    )
    # role='owner' but is_owner=false must not be treated as a global owner.
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
            "VALUES (:id,:u,'unused','owner',false)"
        ),
        {"id": fake_owner, "u": f"fo_{fake_owner.hex}"},
    )
    db.commit()
    for user_id in (warehouse_staff, fake_owner):
        auth = _login_as(db, user_id)
        for path in MASTER_PATHS:
            assert client.get(path, headers=auth).status_code == 403, (user_id, path)


def test_customers_without_a_branch_are_hidden(posting_env):
    client, db, ids, auth, _invoice, _payload = posting_env
    orphan = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
            "VALUES (:id,:c,'No branch',NULL,:t)"
        ),
        {"id": orphan, "c": orphan.hex[:30], "t": ids["territory"]},
    )
    db.commit()
    visible = {c["id"] for c in client.get("/master/customers", headers=auth).json()}
    assert str(orphan) not in visible


def test_read_only_auditor_can_read_but_not_create(posting_env):
    client, db, _ids, _owner_auth, _invoice, payload = posting_env
    auditor = uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
            "VALUES (:id,:u,'unused','read_only_auditor',false)"
        ),
        {"id": auditor, "u": f"ro_{auditor.hex}"},
    )
    db.commit()
    auth = _login_as(db, auditor)
    assert client.get("/master/customers", headers=auth).status_code == 200
    fresh = dict(payload, invoice_no=f"RO-{uuid4().hex[:20]}")
    assert client.post("/invoices", json=fresh, headers=auth).status_code == 403
