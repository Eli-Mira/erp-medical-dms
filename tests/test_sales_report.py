"""GET /invoices/report — posted-only sales performance aggregates (PRD BR-06, D28).

Territory/representative/product roll-ups over Posted invoices only; drafts
never enter financial reports (PRD acceptance). Scoping mirrors the approved
GET /invoices grants exactly. Posting goes through
app.sales.service.post_invoice_atomic directly because the HTTP posting
endpoint stays gated OFF (409) by design.

Real PostgreSQL via scripts/verify_invoice_cycle.py; reuses invoice_env from
test_invoice_api (owner + medical_rep users, two territories/customers).
"""

from uuid import uuid4

from sqlalchemy import text

from app.sales.service import post_invoice_atomic, reverse_invoice_atomic

pytest_plugins = ["test_invoice_api"]


def _opening_stock(db, ids, quantity=50):
    """Batch-keyed opening stock so posting can decrement it."""
    db.execute(
        text(
            "INSERT INTO inventory.stock_balance(warehouse_id,product_id,batch_id,quantity) "
            "VALUES (:w,:p,:b,:q)"
        ),
        {"w": ids["warehouse"], "p": ids["product"], "b": ids["batch"], "q": quantity},
    )
    db.commit()


def _post(db, invoice, actor):
    posted = post_invoice_atomic(db, invoice["id"], actor)
    assert posted is not None and posted["posting_status"] == "Posted"
    db.commit()


def test_report_requires_authentication(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    response = client.get("/invoices/report")
    assert response.status_code == 401, response.text


def test_report_denies_role_outside_sales_scope(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    db.execute(
        text("UPDATE platform.platform_user SET role='warehouse_staff' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    response = client.get("/invoices/report", headers=headers("other"))
    assert response.status_code == 403, response.text


def test_owner_report_aggregates_posted_sales(invoice_env):
    client, db, ids, payload, headers = invoice_env
    _opening_stock(db, ids)
    first = client.post("/invoices", json=payload, headers=headers("owner")).json()
    second = client.post(
        "/invoices",
        json={
            **payload,
            "invoice_no": f"R-{uuid4().hex[:16]}",
            "customer_id": str(ids["other_customer"]),
        },
        headers=headers("owner"),
    ).json()
    _post(db, first, ids["owner"])
    _post(db, second, ids["owner"])

    body = client.get("/invoices/report", headers=headers("owner"))
    assert body.status_code == 200, body.text
    report = body.json()
    # One invoice per territory: 2 x (net 200.00 + VAT 28.00 = grand 228.00).
    assert report["totals"] == {
        "invoice_count": 2,
        "total_before_discount": "456.00",
        "total_discount": "0.00",
        "total_net": "400.00",
        "vat_amount": "56.00",
        "grand_total": "456.00",
    }
    territories = {row["territory_id"]: row for row in report["by_territory"]}
    assert set(territories) == {str(ids["territory"]), str(ids["other_territory"])}
    for row in territories.values():
        assert row["invoice_count"] == 1
        assert row["total_net"] == "200.00"
        assert row["vat_amount"] == "28.00"
        assert row["grand_total"] == "228.00"
    assert [(row["user_id"], row["invoice_count"]) for row in report["by_rep"]] == [
        (str(ids["owner"]), 2)
    ]
    assert report["by_rep"][0]["grand_total"] == "456.00"
    assert len(report["by_product"]) == 1
    product = report["by_product"][0]
    assert product["product_id"] == str(ids["product"])
    assert product["quantity"] == "4.000"
    assert product["line_total"] == "456.00"
    assert product["vat_amount"] == "56.00"


def test_report_excludes_drafts_and_reversed_invoices(invoice_env):
    client, db, ids, payload, headers = invoice_env
    _opening_stock(db, ids)
    invoice = client.post("/invoices", json=payload, headers=headers("owner")).json()
    # Drafts never appear in the financial report.
    draft_only = client.get("/invoices/report", headers=headers("owner")).json()
    assert draft_only["totals"]["invoice_count"] == 0
    assert draft_only["totals"]["grand_total"] == "0.00"
    assert draft_only["by_territory"] == []
    assert draft_only["by_rep"] == []
    assert draft_only["by_product"] == []

    _post(db, invoice, ids["owner"])
    posted = client.get("/invoices/report", headers=headers("owner")).json()
    assert posted["totals"]["invoice_count"] == 1

    reverse_invoice_atomic(db, invoice["id"], ids["owner"], ids["reason"])
    db.commit()
    reversed_view = client.get("/invoices/report", headers=headers("owner")).json()
    assert reversed_view["totals"]["invoice_count"] == 0
    assert reversed_view["totals"]["grand_total"] == "0.00"
    assert reversed_view["by_product"] == []


def test_auditor_report_stays_posted_only(invoice_env):
    client, db, ids, payload, headers = invoice_env
    client.post("/invoices", json=payload, headers=headers("owner"))
    db.execute(
        text("UPDATE platform.platform_user SET role='read_only_auditor' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    body = client.get("/invoices/report", headers=headers("other"))
    assert body.status_code == 200, body.text
    # Posting stays OFF; the auditor report never scavenges drafts.
    assert body.json()["totals"]["invoice_count"] == 0


def test_rep_report_scopes_to_own_created_invoices(invoice_env):
    client, db, ids, payload, headers = invoice_env
    _opening_stock(db, ids)
    own = client.post("/invoices", json=payload, headers=headers("other")).json()
    foreign = client.post(
        "/invoices",
        json={**payload, "invoice_no": f"R-{uuid4().hex[:16]}"},
        headers=headers("owner"),
    ).json()
    _post(db, own, ids["other"])
    _post(db, foreign, ids["owner"])

    body = client.get("/invoices/report", headers=headers("other"))
    assert body.status_code == 200, body.text
    report = body.json()
    # Same territory, but the owner-authored invoice is never the rep's sale.
    assert report["totals"]["invoice_count"] == 1
    assert report["totals"]["grand_total"] == "228.00"
    assert [(row["user_id"], row["invoice_count"]) for row in report["by_rep"]] == [
        (str(ids["other"]), 1)
    ]
    territories = [row["territory_id"] for row in report["by_territory"]]
    assert territories == [str(ids["territory"])]


def test_report_without_territory_grants_is_empty(invoice_env):
    client, db, ids, payload, headers = invoice_env
    _opening_stock(db, ids)
    invoice = client.post("/invoices", json=payload, headers=headers("owner")).json()
    _post(db, invoice, ids["owner"])
    db.execute(
        text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.execute(
        text("DELETE FROM platform.user_territory WHERE user_id=:uid"),
        {"uid": ids["other"]},
    )
    db.commit()
    body = client.get("/invoices/report", headers=headers("other"))
    assert body.status_code == 200, body.text
    report = body.json()
    assert report["totals"]["invoice_count"] == 0
    assert report["by_territory"] == [] and report["by_product"] == []


def test_report_date_range_filtering(invoice_env):
    client, db, ids, payload, headers = invoice_env
    _opening_stock(db, ids)
    invoice = client.post("/invoices", json=payload, headers=headers("owner")).json()
    _post(db, invoice, ids["owner"])
    future = client.get(
        "/invoices/report?date_from=2999-01-01", headers=headers("owner")
    ).json()
    assert future["totals"]["invoice_count"] == 0
    wide = client.get(
        "/invoices/report?date_to=2999-12-31", headers=headers("owner")
    ).json()
    assert wide["totals"]["invoice_count"] == 1
    assert wide["totals"]["grand_total"] == "228.00"
