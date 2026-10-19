"""Private accounts (D40): owner-only, isolated schema."""

pytest_plugins = ["test_invoice_api"]


def test_owner_can_create_and_list_private_entry(invoice_env):
    client, db, _ids, _payload, _headers = invoice_env
    # make "other" an owner for this test? use demo-style: create owner user
    import uuid
    owner_id = uuid.uuid4()
    db.execute(__import__("sqlalchemy").text(
        "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) "
        "VALUES (:id,:u,'unused','owner',true)"),
        {"id": owner_id, "u": f"priv_owner_{owner_id.hex}"})
    db.commit()
    sid = uuid.uuid4()
    db.execute(__import__("sqlalchemy").text(
        "INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:sid,:uid,now()+interval '1 hour')"),
        {"sid": sid, "uid": owner_id})
    db.commit()
    h = {"Authorization": f"Bearer {sid}"}
    created = client.post("/private-accounts", headers=h, json={
        "account_label": "Partner A", "entry_date": "2026-10-01",
        "debit": "100.00", "credit": "0", "note": "test",
    })
    assert created.status_code == 201, created.text
    listed = client.get("/private-accounts", headers=h).json()
    assert len(listed) == 1 and listed[0]["account_label"] == "Partner A"

def test_non_owner_denied(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    assert client.get("/private-accounts", headers=headers("other")).status_code == 403
    assert client.post("/private-accounts", headers=headers("other"), json={
        "account_label": "X", "entry_date": "2026-10-01", "debit": "1", "credit": "0"}).status_code == 403

def test_unauthenticated_denied(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    assert client.get("/private-accounts").status_code == 401
    assert client.post("/private-accounts", json={}).status_code == 401
