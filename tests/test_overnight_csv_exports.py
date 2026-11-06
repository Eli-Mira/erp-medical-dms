"""CSV exports for AR balances/entries/aging/statements and collections."""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_overnight_ar_reports import ar_report_env as ar_report_env  # noqa: PLC0414


def _rows(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith("attachment;")
    # UTF-8 BOM is required so Arabic headers render correctly in Excel.
    assert response.content.startswith(b"\xef\xbb\xbf"), "missing UTF-8 BOM"
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_exports_require_authentication(ar_report_env):
    client = ar_report_env[0]
    paths = [
        "/ar/balances/export",
        "/ar/entries/export",
        "/ar/aging/export",
        f"/ar/statements/{uuid4()}/export",
        "/collections/export",
    ]
    for path in paths:
        assert client.get(path).status_code == 401, path


def test_balances_csv_export(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="100.00", entry_date=date(2026, 1, 1))
    seed(entry_type="opening", debit="5.00", customer="other_customer",
         entry_date=date(2026, 1, 1))
    rows = _rows(client.get("/ar/balances/export", headers=headers()))
    assert rows[0] == ["customer_id", "balance"]
    mine = {row[0]: row[1] for row in rows[1:]
            if row[0] in (str(ids["customer"]), str(ids["other_customer"]))}
    assert mine == {
        str(ids["customer"]): "100.00",
        str(ids["other_customer"]): "5.00",
    }


def test_balances_csv_export_branch_scoped(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="10.00", entry_date=date(2026, 1, 1))
    seed(entry_type="opening", debit="99.00", customer="other_customer",
         entry_date=date(2026, 1, 1))
    db.execute(text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
               {"id": ids["other"]})
    db.execute(text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
               {"u": ids["other"], "b": ids["branch"]})
    db.commit()
    rows = _rows(client.get("/ar/balances/export", headers=headers("other")))
    assert {row[0] for row in rows[1:]} == {
        str(ids["customer"]), str(ids["territory_customer"])}


def test_entries_csv_export_filters_and_exact_money(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="100.01", entry_date=date(2026, 1, 1))
    seed(entry_type="payment", credit="0.03", entry_date=date(2026, 1, 2))
    rows = _rows(client.get(
        f"/ar/entries/export?customer_id={ids['customer']}"
        "&date_from=2026-01-01&date_to=2026-02-01", headers=headers()))
    assert rows[0] == ["id", "customer_id", "invoice_id", "entry_type", "entry_date",
                       "due_date", "debit", "credit", "reason_id", "note", "created_by",
                       "created_at", "receipt_id", "reverses_entry_id"]
    assert len(rows) == 3
    # /ar/entries is newest-first; the export preserves that order
    assert rows[1][3] == "payment"
    assert rows[1][7] == "0.03"
    assert rows[2][3] == "opening"
    assert rows[2][6] == "100.01"


def test_aging_csv_export(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="1.00", entry_date=as_of, due_date=as_of)
    seed(entry_type="opening", debit="5.00", entry_date=as_of,
         due_date=as_of - timedelta(days=1))
    seed(entry_type="opening", debit="9.00", entry_date=as_of, due_date=None)
    rows = _rows(client.get(f"/ar/aging/export?as_of={as_of.isoformat()}",
                            headers=headers()))
    assert rows[0] == ["customer_id", "current", "d1_30", "d31_60", "d61_90",
                       "over_90", "undated", "total"]
    row = next(r for r in rows[1:] if r[0] == str(ids["customer"]))
    assert row == [str(ids["customer"]), "1.00", "5.00", "0", "0",
                   "0", "9.00", "15.00"]


def test_statement_csv_export(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="100.00", entry_date=date(2026, 1, 1))
    seed(entry_type="payment", credit="40.00", entry_date=date(2026, 1, 15))
    rows = _rows(client.get(
        f"/ar/statements/{ids['customer']}/export"
        "?date_from=2026-01-01&date_to=2026-02-01", headers=headers()))
    assert rows[0] == ["entry_date", "entry_type", "invoice_id", "receipt_id",
                       "due_date", "debit", "credit", "balance", "note"]
    assert rows[1] == ["2026-01-01", "opening", "", "", "", "100.00", "0.00",
                       "100.00", ""]
    assert rows[2] == ["2026-01-15", "payment", "", "", "", "0.00", "40.00",
                       "60.00", ""]


def test_statement_csv_agrees_with_statement_totals(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="100.00", entry_date=date(2026, 1, 1))
    seed(entry_type="payment", credit="40.00", entry_date=date(2026, 1, 15))
    seed(entry_type="opening", debit="7.50", entry_date=date(2026, 1, 20))
    query = "?date_from=2026-01-01&date_to=2026-02-01"
    statement = client.get(f"/ar/statements/{ids['customer']}{query}",
                           headers=headers()).json()
    rows = _rows(client.get(f"/ar/statements/{ids['customer']}/export{query}",
                            headers=headers()))
    body = rows[1:]
    assert len(body) == len(statement["lines"]) == 3
    assert Decimal(body[-1][7]) == Decimal(statement["closing_balance"])
    assert sum(Decimal(row[5]) for row in body) == Decimal(statement["total_debit"])
    assert sum(Decimal(row[6]) for row in body) == Decimal(statement["total_credit"])


def test_aging_csv_agrees_with_aging_totals(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="10.00", entry_date=as_of,
         due_date=as_of - timedelta(days=45))
    seed(entry_type="payment", credit="4.00", entry_date=as_of,
         due_date=as_of - timedelta(days=45))
    query = f"?as_of={as_of.isoformat()}"
    payload = client.get(f"/ar/aging{query}", headers=headers()).json()
    rows = _rows(client.get(f"/ar/aging/export{query}", headers=headers()))
    row = next(r for r in rows[1:] if r[0] == str(ids["customer"]))
    expected = next(c for c in payload["customers"]
                    if c["customer_id"] == str(ids["customer"]))
    assert row[1:] == [expected[name] for name in
                       ("current", "d1_30", "d31_60", "d61_90", "over_90",
                        "undated", "total")]


def test_aging_csv_export_territory_scope(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="10.00", entry_date=as_of, due_date=as_of)
    seed(entry_type="opening", debit="20.00", customer="other_customer",
         entry_date=as_of, due_date=as_of)
    seed(entry_type="opening", debit="99.00", customer="territory_customer",
         entry_date=as_of, due_date=as_of)
    rows = _rows(client.get(
        f"/ar/aging/export?as_of={as_of.isoformat()}&territory_id={ids['territory']}",
        headers=headers()))
    assert {r[0] for r in rows[1:]} == {
        str(ids["customer"]), str(ids["other_customer"])}


def test_exports_neutralise_formula_injection(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="10.00", entry_date=date(2026, 1, 1),
         note='=HYPERLINK("http://evil.example")')
    rows = _rows(client.get(f"/ar/entries/export?customer_id={ids['customer']}",
                            headers=headers()))
    note_index = rows[0].index("note")
    assert rows[1][note_index] == "'=HYPERLINK(\"http://evil.example\")"


def test_exports_keep_negative_numbers_numeric(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="payment", credit="50.00", entry_date=date(2026, 1, 1))
    rows = _rows(client.get("/ar/balances/export", headers=headers()))
    row = next(r for r in rows[1:] if r[0] == str(ids["customer"]))
    assert row[1] == "-50.00"


def test_statement_csv_export_unknown_customer_404(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    response = client.get(f"/ar/statements/{uuid4()}/export", headers=headers())
    assert response.status_code == 404


def test_collections_csv_export(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    invoice_id = uuid4()
    receipt_id = uuid4()
    warehouse_id = uuid4()
    db.execute(text(
        "INSERT INTO master_data.master_warehouse (id, branch_id, code, name_ar) "
        "VALUES (:id,:b,:code,'Store')"),
        {"id": warehouse_id, "b": ids["branch"], "code": f"WH-{warehouse_id.hex[:12]}"})
    db.execute(text(
        "INSERT INTO sales.sales_invoice (id, invoice_no, branch_id, customer_id,"
        " warehouse_id, territory_id, invoice_date, posting_status, version, created_by,"
        " posted_at, posted_by)"
        " VALUES (:id,:no,:b,:c,:w,:t,:d,'Posted',1,:actor,now(),:actor)"),
        {"id": invoice_id, "no": f"INV-{invoice_id.hex[:12]}", "b": ids["branch"],
         "c": ids["customer"], "w": warehouse_id, "t": ids["territory"],
         "d": date(2026, 1, 1), "actor": ids["owner"]})
    db.execute(text(
        "INSERT INTO finance.payment_receipt (id, invoice_id, branch_id, customer_id,"
        " receipt_no, receipt_date, amount, method, created_by)"
        " VALUES (:id,:inv,:b,:c,:no,:d,25.50,'cash',:actor)"),
        {"id": receipt_id, "inv": invoice_id, "b": ids["branch"], "c": ids["customer"],
         "no": f"RCP-{receipt_id.hex[:12]}", "d": date(2026, 1, 5), "actor": ids["owner"]})
    db.commit()
    rows = _rows(client.get("/collections/export", headers=headers()))
    assert rows[0] == ["id", "invoice_id", "branch_id", "customer_id", "receipt_no",
                       "receipt_date", "amount", "method", "note", "status", "voided_at",
                       "voided_by", "void_reason_id", "version", "created_by",
                       "created_at", "updated_by", "updated_at"]
    row = next(r for r in rows[1:] if r[0] == str(receipt_id))
    assert row[5] == "2026-01-05"
    assert row[6] == "25.50"
    assert row[7] == "cash"
    assert row[9] == "Active"


@pytest.mark.parametrize("role", ["warehouse_staff", "admin"])
def test_exports_denied_for_non_read_roles(ar_report_env, role):
    client, db, ids, headers, seed = ar_report_env
    db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"),
               {"r": role, "id": ids["other"]})
    db.commit()
    auth = headers("other")
    assert client.get("/ar/balances/export", headers=auth).status_code == 403
    assert client.get("/ar/entries/export", headers=auth).status_code == 403
    assert client.get("/ar/aging/export", headers=auth).status_code == 403
    assert client.get("/collections/export", headers=auth).status_code == 403
