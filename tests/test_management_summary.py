"""GET /reports/management-summary — PostgreSQL-driven management figures.

Replaces manual Excel consolidation for the daily numbers the owner already
tracks: posted sales (today/month-to-date), collections, outstanding
receivables and the current overstock alert count from the approved cover
report. Figures come only from existing ledgers; drafts and reversed invoices
never appear. Scoping mirrors the approved invoice grants: owner/finance/
read_only_auditor global; sales_manager/district_manager restricted to their
user_territory grants; medical reps and warehouse staff have no management
report role (403).
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.sales.service import post_invoice_atomic, reverse_invoice_atomic

pytest_plugins = ["test_invoice_api"]


def _today():
    return datetime.now(UTC).astimezone().date()


@pytest.fixture
def summary_env(invoice_env):
    """invoice_env plus opening stock and a helper to post seeded invoices."""
    client, db, ids, payload, headers = invoice_env
    db.execute(
        text(
            "INSERT INTO inventory.stock_balance(warehouse_id,product_id,batch_id,quantity) "
            "VALUES (:w,:p,:b,50)"
        ),
        {"w": ids["warehouse"], "p": ids["product"], "b": ids["batch"]},
    )
    db.commit()

    def post(invoice, actor, invoice_date=None):
        if invoice_date is not None:
            db.execute(
                text("UPDATE sales.sales_invoice SET invoice_date=:d WHERE id=:i"),
                {"d": invoice_date, "i": invoice["id"]},
            )
            db.commit()
        posted = post_invoice_atomic(db, invoice["id"], actor)
        assert posted["posting_status"] == "Posted"
        db.commit()
        return posted

    return client, db, ids, payload, headers, post


def _summary(client, headers, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get(
        "/reports/management-summary" + (f"?{qs}" if qs else ""), headers=headers
    )


def test_summary_requires_authentication(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    assert client.get("/reports/management-summary").status_code == 401


def test_summary_denies_non_management_roles(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    for role in ("medical_rep", "warehouse_staff"):
        db.execute(
            text("UPDATE platform.platform_user SET role=:r WHERE id=:id"),
            {"r": role, "id": ids["other"]},
        )
        db.commit()
        response = _summary(client, headers("other"))
        assert response.status_code == 403, (role, response.text)


def test_owner_summary_counts_only_posted_sales(summary_env):
    client, _db, ids, payload, headers, post = summary_env
    today = _today()
    posted_invoice = client.post(
        "/invoices", json=payload, headers=headers("owner")
    ).json()
    # A second invoice stays Draft: drafts never enter financial figures.
    client.post(
        "/invoices",
        json={
            **payload,
            "invoice_no": f"M-{uuid4().hex[:16]}",
            "customer_id": str(ids["other_customer"]),
        },
        headers=headers("owner"),
    )
    post(posted_invoice, ids["owner"])

    body = _summary(client, headers("owner"))
    assert body.status_code == 200, body.text
    data = body.json()
    assert data["as_of"] == today.isoformat()
    assert data["sales"]["invoices_mtd"] == 1
    assert data["sales"]["grand_total_mtd"] == "228.00"
    assert data["sales"]["net_mtd"] == "200.00"
    assert data["sales"]["vat_mtd"] == "28.00"
    assert data["sales"]["net_today"] == "200.00"
    assert data["sales"]["vat_today"] == "28.00"
    assert data["sales"]["invoices_today"] == 1
    assert data["sales"]["grand_total_today"] == "228.00"


def test_summary_splits_today_and_mtd_and_excludes_reversed(summary_env):
    client, db, ids, payload, headers, post = summary_env
    reporting_as_of = date(2026, 10, 15)
    early_date = reporting_as_of - timedelta(days=5)
    recent_date = reporting_as_of

    early = client.post("/invoices", json=payload, headers=headers("owner")).json()
    recent = client.post(
        "/invoices",
        json={**payload, "invoice_no": f"M-{uuid4().hex[:16]}"},
        headers=headers("owner"),
    ).json()
    post(early, ids["owner"], invoice_date=early_date)
    post(recent, ids["owner"], invoice_date=recent_date)

    data = _summary(client, headers("owner"), as_of=reporting_as_of).json()
    assert data["sales"]["invoices_today"] == 1
    assert data["sales"]["grand_total_today"] == "228.00"
    assert data["sales"]["invoices_mtd"] == 2
    assert data["sales"]["grand_total_mtd"] == "456.00"

    # Reversing today's invoice removes it entirely from the summary.
    reverse_invoice_atomic(db, recent["id"], ids["owner"], ids["reason"])
    db.commit()
    data = _summary(client, headers("owner"), as_of=reporting_as_of).json()
    assert data["sales"]["invoices_today"] == 0
    assert data["sales"]["grand_total_mtd"] == "228.00"


def test_summary_first_of_month_bounds_mtd_to_current_month(summary_env):
    client, _db, ids, payload, headers, post = summary_env
    reporting_as_of = date(2026, 11, 1)
    prior_date = reporting_as_of - timedelta(days=1)
    today_date = reporting_as_of

    prior = client.post("/invoices", json=payload, headers=headers("owner")).json()
    today = client.post(
        "/invoices",
        json={**payload, "invoice_no": f"M-{uuid4().hex[:16]}"},
        headers=headers("owner"),
    ).json()
    post(prior, ids["owner"], invoice_date=prior_date)
    post(today, ids["owner"], invoice_date=today_date)

    data = _summary(client, headers("owner"), as_of=reporting_as_of).json()
    # prior invoice is in previous month, so excluded from MTD
    assert data["sales"]["invoices_today"] == 1
    assert data["sales"]["invoices_mtd"] == 1
    assert data["sales"]["grand_total_mtd"] == "228.00"


def test_summary_counts_active_collections_and_outstanding_ar(summary_env):
    client, db, ids, payload, headers, post = summary_env
    today = _today()
    from app.finance.payments import create_receipt

    invoice = client.post("/invoices", json=payload, headers=headers("owner")).json()
    post(invoice, ids["owner"])
    create_receipt(
        db,
        invoice_id=invoice["id"],
        branch_id=ids["branch"],
        customer_id=ids["customer"],
        receipt_no=f"RC-{uuid4().hex[:10]}",
        receipt_date=today,
        amount=Decimal("100.00"),
        method="cash",
        note=None,
        actor_id=ids["owner"],
    )
    db.commit()
    data = _summary(client, headers("owner")).json()
    assert data["collections"]["receipts_today"] == 1
    assert data["collections"]["amount_today"] == "100.00"
    assert data["collections"]["amount_mtd"] == "100.00"
    # Outstanding AR = 228.00 sale − 100.00 receipt.
    assert data["receivables"]["outstanding_total"] == "128.00"
    assert data["receivables"]["customers_with_balance"] == 1
    # Receivables are point-in-time: a caller looking at yesterday sees none
    # of today's postings or receipts.
    data = _summary(client, headers("owner"), as_of=today - timedelta(days=1)).json()
    assert data["receivables"]["outstanding_total"] == "0.00"
    assert data["receivables"]["customers_with_balance"] == 0


def test_summary_includes_overstock_alert_counts(summary_env):
    client, _db, _ids, _payload, _headers, _post = summary_env
    # Cover report over real ledgers: seeded stock exists with no posted sales
    # in the window for this product — the alert section reports honest counts.
    data = _summary(client, _headers("owner")).json()
    alerts = data["inventory_alerts"]
    assert alerts["window_days"] == 30
    assert alerts["threshold_days"] == 180
    assert alerts["overstock_count"] == 0
    assert alerts["no_sales_history_count"] >= 1


def test_sales_manager_scoped_to_granted_territories(summary_env):
    client, db, ids, payload, headers, post = summary_env
    own = client.post(
        "/invoices",
        json={
            **payload,
            "invoice_no": f"M-{uuid4().hex[:16]}",
            "customer_id": str(ids["other_customer"]),  # other_territory
        },
        headers=headers("owner"),
    ).json()
    post(own, ids["owner"])
    db.execute(
        text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
        {"id": ids["other"]},
    )
    db.commit()
    # ids["other"] holds only user_territory -> territory (not other_territory).
    data = _summary(client, headers("other")).json()
    assert data["sales"]["invoices_mtd"] == 0
    assert data["sales"]["grand_total_mtd"] == "0.00"
    assert data["receivables"]["outstanding_total"] == "0.00"
