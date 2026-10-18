"""GET /inventory/batches: FEFO-ordered batch/expiry snapshots with scoping."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

pytest_plugins = ["test_inventory_api"]


def _expiry(days):
    return datetime.now(UTC).astimezone().date() + timedelta(days=days)


def test_owner_batches_fefo_order_and_zero_balance(stock_env):
    client, db, ids, headers, _mov = stock_env
    ids["later_batch"], ids["no_stock_batch"] = uuid4(), uuid4()
    db.execute(
        text("INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date)"
             " VALUES (:id,:p,:w,'LATER',:expiry)"),
        {"id": ids["later_batch"], "p": ids["product"], "w": ids["warehouse"],
         "expiry": _expiry(700)},
    )
    db.execute(
        text("INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date)"
             " VALUES (:id,:p,:w,'NOSTOCK',:expiry)"),
        {"id": ids["no_stock_batch"], "p": ids["product"], "w": ids["warehouse"],
         "expiry": _expiry(30)},
    )
    db.commit()
    # Stock exists only for one batch; the other stays visible with 0 on hand.
    assert client.post("/inventory/movements", json=_mov(batch_id=str(ids["batch"])),
                       headers=headers("owner")).status_code == 201
    body = client.get(f"/inventory/batches?product_id={ids['product']}", headers=headers("owner"))
    assert body.status_code == 200, body.text
    rows = body.json()
    assert [r["batch_no"] for r in rows] == ["NOSTOCK", "TEST", "LATER"]
    by_no = {r["batch_no"]: r for r in rows}
    assert Decimal(by_no["NOSTOCK"]["quantity"]) == 0
    assert Decimal(by_no["TEST"]["quantity"]) == 10
    assert all(r["manufacture_date"] is None for r in rows)


def test_owner_batches_filter_by_warehouse(stock_env):
    client, db, ids, headers, _mov = stock_env
    ids["other_batch"] = uuid4()
    db.execute(
        text("INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date)"
             " VALUES (:id,:p,:w,'ELSEWHERE',:expiry)"),
        {"id": ids["other_batch"], "p": ids["product"], "w": ids["other_warehouse"],
         "expiry": _expiry(100)},
    )
    db.commit()
    rows = client.get(f"/inventory/batches?warehouse_id={ids['warehouse']}",
                      headers=headers("owner")).json()
    assert [r["batch_no"] for r in rows] == ["TEST"]


def test_branch_scoped_caller_sees_only_granted_branch_batches(stock_env):
    client, db, ids, headers, _mov = stock_env
    ids["staff"] = uuid4()
    db.execute(
        text("INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner)"
             " VALUES (:id,:u,'unused','sales_manager',false)"),
        {"id": ids["staff"], "u": f"batch_scoped_{ids['staff'].hex}"},
    )
    # warehouse_staff user is global; use the sales_manager with an explicit grant.
    db.execute(
        text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
        {"u": ids["staff"], "b": ids["branch"]},
    )
    db.commit()
    ids["other_branch_warehouse"] = uuid4()
    ids["other_branch"] = uuid4()
    db.execute(
        text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'Other branch')"),
        {"id": ids["other_branch"], "code": ids["other_branch"].hex[:20]},
    )
    db.execute(
        text("INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar)"
             " VALUES (:id,:b,:code,'Other-branch warehouse')"),
        {"id": ids["other_branch_warehouse"], "b": ids["other_branch"],
         "code": ids["other_branch_warehouse"].hex[:20]},
    )
    ids["foreign_batch"] = uuid4()
    db.execute(
        text("INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date)"
             " VALUES (:id,:p,:w,'FOREIGN',:expiry)"),
        {"id": ids["foreign_batch"], "p": ids["product"], "w": ids["other_branch_warehouse"],
         "expiry": _expiry(10)},
    )
    db.commit()
    scoped_names = [r["batch_no"] for r in client.get(
        "/inventory/batches", headers=headers("staff")).json()]
    assert "FOREIGN" not in scoped_names
    assert "TEST" in scoped_names


def test_caller_without_branch_grants_is_denied(stock_env):
    """A non-global role with no user_branch grants gets 403, not an empty list."""
    client, db, ids, headers, _mov = stock_env
    ids["norole"] = uuid4()
    db.execute(
        text("INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner)"
             " VALUES (:id,:u,'unused','district_manager',false)"),
        {"id": ids["norole"], "u": f"batch_denied_{ids['norole'].hex}"},
    )
    db.commit()
    assert client.get("/inventory/batches", headers=headers("norole")).status_code == 403
