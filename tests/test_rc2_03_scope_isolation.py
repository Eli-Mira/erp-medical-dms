import pytest
from uuid import uuid4
from sqlalchemy import text
from test_invoice_api import invoice_env  # noqa: F401


def _mk_auth(db, role, *, territory_id=None, branch_id=None):
    uid, sid = uuid4(), uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) VALUES (:id,:u,'unused',:r,false)"
        ),
        {"id": uid, "u": f"rc2_{role}_{uid.hex[:8]}", "r": role},
    )
    if territory_id is not None:
        db.execute(
            text("INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t)"),
            {"u": uid, "t": territory_id},
        )
    if branch_id is not None:
        db.execute(
            text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
            {"u": uid, "b": branch_id},
        )
    db.execute(
        text(
            "INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:s,:u,now() + interval '1 hour')"
        ),
        {"s": sid, "u": uid},
    )
    db.commit()
    return {"Authorization": f"Bearer {sid}"}


def test_p3c_01_sales_manager_visits_scoped(invoice_env):
    client, db, ids, payload, headers = invoice_env
    for cid in (ids["customer"], ids["other_customer"]):
        resp = client.post(
            "/visits",
            json={
                "customer_id": str(cid),
                "visit_date": "2026-10-01",
                "lines": [
                    {
                        "product_id": str(ids["product"]),
                        "quantity_prev": "0",
                        "quantity_delivered": "10",
                        "quantity_returned": "0",
                        "quantity_current": "10",
                    }
                ],
            },
            headers=headers("owner"),
        )
        assert resp.status_code == 201
    sm = _mk_auth(db, "sales_manager", territory_id=ids["territory"])
    visits = client.get("/visits", headers=sm).json()["items"]
    assert {v["customer_id"] for v in visits} == {str(ids["customer"])}
    held = client.get("/visits/held-stock", headers=sm).json()["items"]
    assert {h["customer_id"] for h in held} == {str(ids["customer"])}


def test_p3c_02_targets_scoped(invoice_env):
    client, db, ids, payload, headers = invoice_env
    for tid in (ids["territory"], ids["other_territory"]):
        resp = client.post(
            "/targets",
            json={
                "territory_id": str(tid),
                "period_month": "2026-10-01",
                "target_quantity": "100",
            },
            headers=headers("owner"),
        )
        assert resp.status_code == 201
    sm = _mk_auth(db, "sales_manager", territory_id=ids["territory"])
    dm = _mk_auth(db, "district_manager", territory_id=ids["territory"])
    for auth in (sm, dm):
        data = client.get("/targets", headers=auth).json()
        assert {t["territory_id"] for t in data} == {str(ids["territory"])}
    resp = client.post(
        "/targets",
        json={
            "territory_id": str(ids["other_territory"]),
            "period_month": "2026-10-01",
            "target_quantity": "50",
        },
        headers=sm,
    )
    assert resp.status_code == 403
    resp = client.post(
        "/targets",
        json={
            "territory_id": str(ids["territory"]),
            "period_month": "2026-11-01",
            "target_quantity": "50",
        },
        headers=sm,
    )
    assert resp.status_code == 201


def test_p3c_03_warehouse_staff_returns_branch_scoped(invoice_env):
    client, db, ids, payload, headers = invoice_env
    other_branch = uuid4()
    foreign_cust = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:c,'Other')"
        ),
        {"id": other_branch, "c": other_branch.hex[:16]},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:c,'Foreign',:b,:t)"
        ),
        {
            "id": foreign_cust,
            "c": foreign_cust.hex[:16],
            "b": other_branch,
            "t": ids["other_territory"],
        },
    )
    db.commit()
    ws = _mk_auth(db, "warehouse_staff", branch_id=ids["branch"])
    base = {
        "warehouse_id": str(ids["warehouse"]),
        "product_id": str(ids["product"]),
        "quantity": "5",
        "return_date": "2026-10-01",
        "reason": "damaged",
    }
    resp = client.post(
        "/returns", json={**base, "customer_id": str(foreign_cust)}, headers=ws
    )
    assert resp.status_code == 404
    for cid in (ids["customer"], foreign_cust):
        resp = client.post(
            "/returns", json={**base, "customer_id": str(cid)}, headers=headers("owner")
        )
        assert resp.status_code == 201
    returns = client.get("/returns", headers=ws).json()
    assert {r["customer_id"] for r in returns} == {str(ids["customer"])}


def test_auditor_put_invoice_403_pre_lock(invoice_env):
    client, db, ids, payload, headers = invoice_env
    r = client.post("/invoices", json=payload, headers=headers("owner"))
    assert r.status_code == 201
    inv_id = r.json()["id"]
    aud = _mk_auth(db, "read_only_auditor", territory_id=ids["territory"])
    upd = {**payload, "version": 1}
    assert client.put(f"/invoices/{inv_id}", json=upd, headers=aud).status_code == 403
    db.execute(
        text(
            "UPDATE sales.sales_invoice SET posting_status='Posted', posted_at=now(), posted_by=:u WHERE id=:id"
        ),
        {"u": ids["owner"], "id": inv_id},
    )
    db.commit()
    assert client.put(f"/invoices/{inv_id}", json=upd, headers=aud).status_code == 403
