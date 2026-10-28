"""Reason codes: read by all, write by owner/admin."""

pytest_plugins = ["test_invoice_api"]


def test_reason_codes_create_and_list(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    created = client.post("/reason-codes", headers=headers("owner"), json={
        "code": "DAMAGED", "category": "return", "name_ar": "تالف",
    })
    assert created.status_code == 201, created.text
    listed = client.get("/reason-codes", headers=headers("owner")).json()
    assert any(r["code"] == "DAMAGED" for r in listed)
    filtered = client.get("/reason-codes?category=return", headers=headers("owner")).json()
    assert all(r["category"] == "return" for r in filtered)

def test_reason_codes_write_gated(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    assert client.post("/reason-codes", headers=headers("other"), json={
        "code": "X", "category": "return"}).status_code == 403
    assert client.get("/reason-codes").status_code == 401

def test_reason_code_duplicate_rejected(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    client.post("/reason-codes", headers=headers("owner"), json={"code": "DUP", "category": "adjustment"})
    assert client.post("/reason-codes", headers=headers("owner"), json={"code": "DUP", "category": "adjustment"}).status_code == 409
