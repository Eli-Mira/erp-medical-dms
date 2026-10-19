"""Global search: customers + products by name/code, with master visibility rules."""

import pytest

pytest_plugins = ["test_invoice_api"]


def _code(ids, key):
    return ids[key].hex[:30]


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


def test_search_customer_visibility_matches_master_territory_rules(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    rep = headers("other")
    own = client.get(f"/search?q={_code(ids, 'customer')}", headers=rep).json()
    other = client.get(f"/search?q={_code(ids, 'other_customer')}", headers=rep).json()
    assert [c["code"] for c in own["customers"]] == [_code(ids, "customer")]
    assert other["customers"] == []
    # Products are a global catalogue, not territory-scoped.
    assert client.get("/search?q=Test", headers=rep).json()["products"]


def test_search_customers_without_territory_or_branch_are_excluded(invoice_env):
    client, db, _ids, _payload, headers = invoice_env
    from uuid import uuid4

    from sqlalchemy import text

    orphan = uuid4()
    db.execute(
        text("INSERT INTO master_data.master_customer(id,code,name_ar) "
             "VALUES (:id,:code,'Orphan customer')"),
        {"id": orphan, "code": "orphan-" + orphan.hex[:16]},
    )
    db.commit()
    body = client.get("/search?q=orphan", headers=headers("owner")).json()
    assert body["customers"] == []


def test_search_like_metacharacters_are_literal(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    assert client.get("/search?q=%25", headers=headers("owner")).json()["customers"] == []
    assert client.get("/search?q=_", headers=headers("owner")).json()["customers"] == []
