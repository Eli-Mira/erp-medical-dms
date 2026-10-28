"""GET /invoices list/search slice: scoping mirrors single-fetch grants exactly.

Real PostgreSQL via scripts/verify_invoice_cycle.py; reuses invoice_env from
test_invoice_api (owner + medical_rep users, two territories/customers).
"""

from uuid import uuid4

from sqlalchemy import text

pytest_plugins = ["test_invoice_api"]


def test_owner_lists_invoices_with_total(invoice_env):
    client, _db, ids, payload, headers = invoice_env
    first = client.post("/invoices", json=payload, headers=headers("owner")).json()
    second = client.post(
        "/invoices",
        json={
            **payload,
            "invoice_no": f"L-{uuid4().hex[:16]}",
            "customer_id": str(ids["other_customer"]),
        },
        headers=headers("owner"),
    ).json()
    body = client.get("/invoices?limit=200", headers=headers("owner"))
    assert body.status_code == 200, body.text
    data = body.json()
    got = [item["id"] for item in data["items"]]
    assert first["id"] in got and second["id"] in got
    assert data["total"] >= len(got)


def test_owner_filters_by_customer_status_and_date(invoice_env):
    client, _db, ids, payload, headers = invoice_env
    target = client.post("/invoices", json=payload, headers=headers("owner")).json()
    client.post(
        "/invoices",
        json={
            **payload,
            "invoice_no": f"L-{uuid4().hex[:16]}",
            "customer_id": str(ids["other_customer"]),
        },
        headers=headers("owner"),
    )
    filtered = client.get(
        f"/invoices?customer_id={ids['customer']}", headers=headers("owner")
    ).json()
    assert [item["id"] for item in filtered["items"]] == [target["id"]]
    drafts = client.get("/invoices?status=Draft", headers=headers("owner")).json()
    assert drafts["total"] >= 2
    assert all(item["posting_status"] == "Draft" for item in drafts["items"])
    empty = client.get("/invoices?date_from=2999-01-01", headers=headers("owner")).json()
    assert empty["items"] == [] and empty["total"] == 0


def test_pagination_limit_keeps_total(invoice_env):
    client, _db, _ids, payload, headers = invoice_env
    client.post("/invoices", json=payload, headers=headers("owner"))
    client.post(
        "/invoices",
        json={**payload, "invoice_no": f"L-{uuid4().hex[:16]}"},
        headers=headers("owner"),
    )
    page = client.get("/invoices?limit=1", headers=headers("owner")).json()
    assert len(page["items"]) == 1
    assert page["total"] >= 2
    assert page["items"][0]["lines"] == []


def test_rep_sees_only_own_created_in_own_territory(invoice_env):
    client, _db, _ids, payload, headers = invoice_env
    own = client.post("/invoices", json=payload, headers=headers("other")).json()
    foreign_author = client.post(
        "/invoices",
        json={**payload, "invoice_no": f"L-{uuid4().hex[:16]}"},
        headers=headers("owner"),
    ).json()
    body = client.get("/invoices?limit=200", headers=headers("other")).json()
    got = [item["id"] for item in body["items"]]
    assert own["id"] in got
    # Same territory as the rep, but created by the owner: never listed.
    assert foreign_author["id"] not in got


def test_auditor_sees_only_posted_and_none_exist_without_posting(invoice_env):
    client, db, ids, payload, headers = invoice_env
    client.post("/invoices", json=payload, headers=headers("owner"))
    db.execute(
        text("UPDATE platform.platform_user SET role='read_only_auditor' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    body = client.get("/invoices?limit=200", headers=headers("other"))
    assert body.status_code == 200
    assert body.json()["items"] == []
    # The 409 gate keeps posting off; auditor listing never scavenges drafts.
    assert body.json()["total"] == 0


def test_auditor_posted_only_scoping_on_mixed_data(invoice_env):
    client, db, ids, payload, headers = invoice_env
    client.post("/invoices", json=payload, headers=headers("owner"))
    db.execute(
        text("UPDATE platform.platform_user SET role='read_only_auditor' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    # Drafts must be invisible; posting stays OFF so the list stays empty.
    body = client.get("/invoices?status=Posted", headers=headers("other"))
    assert body.status_code == 200
    assert body.json()["items"] == []
