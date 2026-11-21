import csv
import io
from sqlalchemy import text
from test_invoice_api import invoice_env  # noqa: F401


def _parse_csv(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"].startswith("attachment;")
    assert resp.content.startswith(b"\xef\xbb\xbf"), "missing UTF-8 BOM"
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))


def test_day1_exports_require_auth(invoice_env):
    client, *_ = invoice_env
    for endpoint in [
        "/invoices/export",
        "/invoices/report/export",
        "/inventory/stock/export",
    ]:
        resp = client.get(endpoint)
        assert resp.status_code == 401, f"{endpoint} should require auth"


def test_invoices_and_report_csv_exports_utf8_bom_and_formula_safe(invoice_env):
    client, db, ids, payload, headers = invoice_env
    inv_payload = {**payload, "notes": "=CMD|' /C calc'!A0"}
    resp = client.post("/invoices", json=inv_payload, headers=headers("owner"))
    assert resp.status_code == 201
    inv_id = resp.json()["id"]

    resp = client.get("/invoices/export", headers=headers("owner"))
    rows = _parse_csv(resp)
    assert rows[0][0] == "invoice_no"
    assert any(payload["invoice_no"] in row for row in rows)
    notes_col_idx = rows[0].index("notes")
    invoice_row = next(row for row in rows if payload["invoice_no"] in row)
    assert invoice_row[notes_col_idx].startswith("'=CMD"), "formula not neutralized"

    db.execute(
        text(
            "UPDATE sales.sales_invoice SET posting_status='Posted', posted_at=now(), posted_by=:u WHERE id=:id"
        ),
        {"u": ids["owner"], "id": inv_id},
    )
    db.commit()

    resp = client.get("/invoices/report/export", headers=headers("owner"))
    rows = _parse_csv(resp)
    assert rows[0] == [
        "section",
        "label",
        "code",
        "invoice_count",
        "quantity",
        "net_total",
        "vat_total",
        "grand_total",
    ]
    totals_row = next(row for row in rows if row[0] == "totals")
    assert totals_row[3] == "1"


def test_inventory_stock_csv_export_scoped_and_exact(invoice_env):
    client, db, ids, payload, headers = invoice_env
    movement = {
        "warehouse_id": str(ids["warehouse"]),
        "product_id": str(ids["product"]),
        "batch_id": str(ids["batch"]),
        "movement_type": "opening",
        "quantity": "12.500",
    }
    resp = client.post(
        "/inventory/movements", json=movement, headers=headers("owner")
    )
    assert resp.status_code == 201

    resp = client.get(
        f"/inventory/stock/export?warehouse_id={ids['warehouse']}",
        headers=headers("owner"),
    )
    rows = _parse_csv(resp)
    assert rows[0] == [
        "warehouse_id",
        "warehouse_name",
        "product_id",
        "product_name",
        "batch_id",
        "quantity",
        "updated_at",
    ]
    stock_row = next(
        row for row in rows if str(ids["product"]) in row and "12.500" in row
    )
    assert str(ids["product"]) in stock_row
    assert "12.500" in stock_row
