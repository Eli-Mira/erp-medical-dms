"""Independent I1 ledger oracles, executed only by the disposable verifier."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from test_invoice_api import invoice_env as invoice_env  # noqa: PLC0414
from test_management_summary import summary_env as summary_env  # noqa: PLC0414


def test_fully_settled_customer_is_not_counted_as_outstanding(summary_env):
    from app.finance.payments import create_receipt

    client, db, ids, payload, headers, post = summary_env
    auth = headers()
    invoice = client.post("/invoices", json=payload, headers=auth).json()
    posted = post(invoice, ids["owner"])
    day = posted["invoice_date"]
    create_receipt(
        db,
        invoice_id=invoice["id"],
        branch_id=ids["branch"],
        customer_id=ids["customer"],
        receipt_no="I1-" + uuid4().hex[:16],
        receipt_date=day + timedelta(days=1),
        amount=Decimal("228.00"),
        method="cash",
        note=None,
        actor_id=ids["owner"],
    )
    db.commit()
    # Narrow the oracle and API to this explicitly granted territory.
    db.execute(
        text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:u"),
        {"u": ids["other"]},
    )
    db.commit()
    scoped = headers("other")
    for as_of in (day, day + timedelta(days=1)):
        expected = (
            db.execute(
                text(
                    "SELECT COALESCE(SUM(balance),0.00) AS outstanding, count(*) FILTER (WHERE balance <> 0) AS customers "
                    "FROM (SELECT a.customer_id,SUM(a.debit-a.credit) AS balance "
                    "FROM finance.ar_entry a JOIN master_data.master_customer c ON c.id=a.customer_id "
                    "WHERE c.territory_id=:t AND a.entry_date<=:d GROUP BY a.customer_id) balances"
                ),
                {"t": ids["territory"], "d": as_of},
            )
            .mappings()
            .one()
        )
        result = client.get(
            "/reports/management-summary", params={"as_of": str(as_of)}, headers=scoped
        )
        assert result.status_code == 200, result.text
        actual = result.json()["receivables"]
        assert Decimal(actual["outstanding_total"]) == expected["outstanding"]
        assert actual["customers_with_balance"] == expected["customers"]


@pytest.mark.parametrize("failure", ["response", "audit"])
def test_management_read_audit_is_atomic(invoice_env, monkeypatch, failure):
    from app.reports import router, service

    client, db, ids, _payload, headers = invoice_env
    auth = headers()
    query = text(
        "SELECT count(*) FROM audit.audit_log WHERE entity_type='management_summary' AND actor_user_id=:u"
    )
    before = db.scalar(query, {"u": ids["owner"]})
    if failure == "response":
        real = service.management_summary

        def invalid_response(*args):
            result = real(*args)
            result.pop("sales")
            return result

        monkeypatch.setattr(service, "management_summary", invalid_response)
        expected = ValidationError
    else:
        real = router.log_audit

        def failed_audit(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError("Synthetic I1 audit failure")

        monkeypatch.setattr(router, "log_audit", failed_audit)
        expected = RuntimeError
    with pytest.raises(expected):
        client.get("/reports/management-summary", headers=auth)
    assert db.scalar(query, {"u": ids["owner"]}) == before
