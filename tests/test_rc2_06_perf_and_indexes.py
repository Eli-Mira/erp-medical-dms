from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event, text

from test_invoice_api import invoice_env  # noqa: F401


@pytest.fixture
def env(invoice_env):
    # unpack fixture for readability
    client, db, ids, payload, headers = invoice_env
    return client, db, ids, payload, headers


def test_collections_list_constant_query_count_and_pagination(env):
    client, db, ids, payload, headers = env

    # create invoice
    resp = client.post(
        "/invoices", json=payload, headers=headers("owner")
    )
    assert resp.status_code == 201
    inv_id = resp.json()["id"]

    # mark invoice as posted
    db.execute(
        text(
            "UPDATE sales.sales_invoice "
            "SET posting_status='Posted', posted_at=now(), posted_by=:uid "
            "WHERE id=:inv"
        ),
        {"uid": ids["owner"], "inv": inv_id},
    )
    db.commit()

    # insert 5 payment receipts
    for i in range(5):
        db.execute(
            text(
                "INSERT INTO finance.payment_receipt (invoice_id, branch_id, customer_id, "
                "receipt_no, receipt_date, amount, method, status, created_by) "
                "VALUES (:invoice_id, :branch_id, :customer_id, :receipt_no, :receipt_date, "
                ":amount, :payment_method, :status, :created_by)"
            ),
            {
                "invoice_id": inv_id,
                "branch_id": ids["branch"],
                "customer_id": ids["customer"],
                "receipt_no": f"RCP-RC206-{i}",
                "receipt_date": date(2026, 11, 10 + i),
                "amount": Decimal("10.00"),
                "payment_method": "cash",
                "status": "Active",
                "created_by": ids["owner"],
            },
        )
    db.commit()

    # count queries for collections list
    queries = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    owner_headers = headers("owner")
    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        resp = client.get("/collections", headers=owner_headers)
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 5
    assert len(queries) <= 5

    # pagination limit/offset
    resp = client.get(
        "/collections?limit=2&offset=1", headers=headers("owner")
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # invalid limit
    resp = client.get("/collections?limit=0", headers=headers("owner"))
    assert resp.status_code == 422


def test_ar_aging_sql_and_entries_pagination(env):
    client, db, ids, payload, headers = env

    # insert 6 AR entries
    entries = [
        # current (due after as_of)
        {
            "due_date": date(2026, 11, 25),
            "debit": Decimal("10.00"),
        },
        # 1-30 days past due
        {
            "due_date": date(2026, 11, 11),
            "debit": Decimal("20.00"),
        },
        # 31-60 days past due
        {
            "due_date": date(2026, 10, 10),
            "debit": Decimal("30.00"),
        },
        # 61-90 days past due
        {
            "due_date": date(2026, 9, 10),
            "debit": Decimal("40.00"),
        },
        # over 90 days past due
        {
            "due_date": date(2026, 7, 1),
            "debit": Decimal("50.00"),
        },
        # undated
        {
            "due_date": None,
            "debit": Decimal("60.00"),
        },
    ]

    for entry in entries:
        db.execute(
            text(
                "INSERT INTO finance.ar_entry (customer_id, entry_type, entry_date, due_date, "
                "debit, credit, created_by) "
                "VALUES (:customer_id, :entry_type, :entry_date, :due_date, "
                ":debit, 0, :created_by)"
            ),
            {
                "customer_id": ids["customer"],
                "entry_type": "adjustment",
                "entry_date": date(2026, 10, 1),
                "due_date": entry["due_date"],
                "debit": entry["debit"],
                "created_by": ids["owner"],
            },
        )
    db.commit()

    # aging endpoint
    resp = client.get(
        "/ar/aging?as_of=2026-11-21", headers=headers("owner")
    )
    assert resp.status_code == 200
    aging_data = resp.json()
    # find row for the test customer
    cust_row = next(
        (row for row in aging_data["customers"] if str(row.get("customer_id")) == str(ids["customer"])), None
    )
    assert cust_row is not None
    # bucket fields expected by the API (names may vary; using generic keys)
    # Assuming the API returns keys: current, d1_30, d31_60, d61_90, over_90, undated, total
    assert cust_row.get("current") == "10.00"
    assert cust_row.get("d1_30") == "20.00"
    assert cust_row.get("d31_60") == "30.00"
    assert cust_row.get("d61_90") == "40.00"
    assert cust_row.get("over_90") == "50.00"
    assert cust_row.get("undated") == "60.00"
    assert cust_row.get("total") == "210.00"

    # entries pagination
    resp = client.get(
        "/ar/entries?limit=2&offset=1", headers=headers("owner")
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # invalid limit
    resp = client.get(
        "/ar/entries?limit=501", headers=headers("owner")
    )
    assert resp.status_code == 422
