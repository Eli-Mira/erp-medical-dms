"""Global search: customers + products by name/code."""

pytest_plugins = ["test_invoice_api"]


def test_search_returns_matching_customers_and_products(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    # product name contains "Test product"; customer code contains ids
    res = client.get("/search?q=Test", headers=headers("owner"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert "customers" in body and "products" in body
    assert any("Test" in (p.get("name_ar") or "") for p in body["products"])

def test_search_requires_auth(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    assert client.get("/search?q=x").status_code == 401

def test_search_empty_query_rejected(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    assert client.get("/search?q=", headers=headers("owner")).status_code == 422
