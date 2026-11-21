from test_invoice_api import invoice_env  # noqa: F401
import pytest

@pytest.mark.usefixtures("invoice_env")
def test_audit_limit_bounds(invoice_env):
    client, db, ids, payload, headers = invoice_env
    # limit=0
    resp = client.get("/audit?limit=0", headers=headers("owner"))
    assert resp.status_code == 422
    # limit=-5
    resp = client.get("/audit?limit=-5", headers=headers("owner"))
    assert resp.status_code == 422
    # limit=501
    resp = client.get("/audit?limit=501", headers=headers("owner"))
    assert resp.status_code == 422
    # limit=1
    resp = client.get("/audit?limit=1", headers=headers("owner"))
    assert resp.status_code == 200

def test_nul_byte_rejected_422_never_500(invoice_env):
    client, db, ids, payload, headers = invoice_env
    # query string NUL byte
    resp = client.get("/audit?action=login%00evil", headers=headers("owner"))
    assert resp.status_code == 422
    resp = client.get("/invoices?status=Draft%00", headers=headers("owner"))
    assert resp.status_code == 422
    # JSON body NUL byte in private accounts
    resp = client.post(
        "/private-accounts",
        json={"name": "bad" + chr(0) + "name"},
        headers=headers("owner"),
    )
    assert resp.status_code == 422
    # JSON body NUL byte in transfers
    resp = client.post(
        "/transfers",
        json={"note": "bad" + chr(0) + "note"},
        headers=headers("owner"),
    )
    assert resp.status_code == 422

@pytest.mark.parametrize(
    "payload",
    [
        {"source_warehouse_id": "not-a-uuid", "destination_warehouse_id": "00000000-0000-0000-0000-000000000001", "product_id": "00000000-0000-0000-0000-000000000002", "batch_id": "00000000-0000-0000-0000-000000000003", "quantity": 10},
        {"source_warehouse_id": "00000000-0000-0000-0000-000000000001", "destination_warehouse_id": "00000000-0000-0000-0000-000000000002", "product_id": "00000000-0000-0000-0000-000000000003", "batch_id": "00000000-0000-0000-0000-000000000004", "quantity": "NaN"},
        {"source_warehouse_id": "00000000-0000-0000-0000-000000000001", "destination_warehouse_id": "00000000-0000-0000-0000-000000000002", "product_id": "00000000-0000-0000-0000-000000000003", "batch_id": "00000000-0000-0000-0000-000000000004", "quantity": "Infinity"},
        {"source_warehouse_id": "00000000-0000-0000-0000-000000000001", "destination_warehouse_id": "00000000-0000-0000-0000-000000000002", "product_id": "00000000-0000-0000-0000-000000000003", "batch_id": "00000000-0000-0000-0000-000000000004", "quantity": -5},
        {"source_warehouse_id": "00000000-0000-0000-0000-000000000001", "destination_warehouse_id": "00000000-0000-0000-0000-000000000002", "product_id": "00000000-0000-0000-0000-000000000003", "batch_id": "00000000-0000-0000-0000-000000000004", "quantity": 0},
        {"source_warehouse_id": "00000000-0000-0000-0000-000000000001", "destination_warehouse_id": "00000000-0000-0000-0000-000000000002", "product_id": "00000000-0000-0000-0000-000000000003", "batch_id": "00000000-0000-0000-0000-000000000004", "quantity": 10, "forged_actor": "x"},
    ],
)
def test_transfers_hostile_payloads_return_422(invoice_env, payload):
    client, db, ids, _, headers = invoice_env
    resp = client.post("/transfers", json=payload, headers=headers("owner"))
    assert resp.status_code == 422

@pytest.mark.parametrize(
    "payload",
    [
        {"name": 123},
        {"name": "   "},
        {"name": "valid", "unexpected": "x"},
    ],
)
def test_private_accounts_hostile_payloads_return_422(invoice_env, payload):
    client, db, ids, _, headers = invoice_env
    resp = client.post("/private-accounts", json=payload, headers=headers("owner"))
    assert resp.status_code == 422
