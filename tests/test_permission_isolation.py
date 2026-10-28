"""Permission/isolation smoke tests for new endpoints (Workstream C)."""

pytest_plugins = ["test_invoice_api"]

def test_new_endpoints_require_auth(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    for method, path in (
        ("GET", "/inventory/batches"),
        ("GET", "/inventory/cover"),
        ("GET", "/settings/inventory-policy"),
        ("GET", "/targets"),
        ("GET", "/audit"),
        ("GET", "/transfers"),
        ("GET", "/returns"),
        ("GET", "/marketing/spend"),
        ("GET", "/marketing/objectives"),
    ):
        r = client.request(method, path)
        assert r.status_code == 401, (method, path, r.status_code)

def test_medical_rep_cannot_manage_targets(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    assert client.post("/targets", headers=headers("other"),
                       json={"rep_id": str(ids["other"]), "period_month": "2026-10-01",
                             "target_quantity": "10"}).status_code == 403

def test_branch_scoped_user_cannot_see_other_warehouse_batches(invoice_env):
    client, db, ids, _payload, _headers = invoice_env
    # Create a sales_manager user scoped to ids["branch"] only.
    import uuid
    sm_id = uuid.uuid4()
    db.execute(__import__("sqlalchemy").text(
        "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) "
        "VALUES (:id,:u,'unused','sales_manager',false)"),
        {"id": sm_id, "u": f"sm_scoped_{sm_id.hex}"})
    db.execute(__import__("sqlalchemy").text(
        "INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
        {"u": sm_id, "b": ids["branch"]})
    # A batch in a different branch's warehouse.
    other_branch = uuid.uuid4()
    other_wh = uuid.uuid4()
    db.execute(__import__("sqlalchemy").text(
        "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:c,'Other')"),
        {"id": other_branch, "c": other_branch.hex[:20]})
    db.execute(__import__("sqlalchemy").text(
        "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:b,:c,'OtherWh')"),
        {"id": other_wh, "b": other_branch, "c": other_wh.hex[:20]})
    other_batch = uuid.uuid4()
    db.execute(__import__("sqlalchemy").text(
        "INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date) "
        "VALUES (:id,:p,:w,'OTHERBATCH',:e)"),
        {"id": other_batch, "p": ids["product"], "w": other_wh,
         "e": __import__("datetime").date(2027,1,1)})
    db.commit()
    # session for the scoped sales_manager
    sid = uuid.uuid4()
    db.execute(__import__("sqlalchemy").text(
        "INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:sid,:uid,now()+interval '1 hour')"),
        {"sid": sid, "uid": sm_id})
    db.commit()
    h = {"Authorization": f"Bearer {sid}"}
    resp = client.get("/inventory/batches", headers=h)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert isinstance(rows, list)
    assert all((r.get("batch_no") if isinstance(r, dict) else r) != "OTHERBATCH" for r in rows)