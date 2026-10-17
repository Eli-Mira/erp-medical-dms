"""Atomic invoice posting: stock decrement + AR debit in one transaction.

Kept as a unit-testable function. The HTTP endpoint (app.sales.router.post_invoice)
intentionally stays disabled (409) until this transaction is verified and
Eli signs off on enabling production posting.
"""
from sqlalchemy import text

from app.finance import ar as finance
from app.inventory import service as inventory


def _lock_invoice(db, invoice_id):
    row = db.execute(text(
        "SELECT * FROM sales.sales_invoice WHERE id=:id FOR UPDATE"), {"id": invoice_id}).mappings().one_or_none()
    if row is None:
        return None
    return dict(row)


def _lines(db, invoice_id):
    rows = db.execute(text(
        "SELECT * FROM sales.sales_invoice_line WHERE invoice_id=:id ORDER BY line_no"),
        {"id": invoice_id}).mappings()
    return [dict(r) for r in rows]


def post_invoice_atomic(db, invoice_id, actor_id):
    """Post a draft invoice atomically:

    1. decrement stock for each line (inventory.stock_movement, type 'sale');
    2. create one receivables debit entry (finance.ar_entry, type 'invoice');
    3. flip the invoice to Posted.

    All three happen in the caller's transaction. Insufficient stock rolls
    back everything (balance never went negative, no AR entry written, invoice
    stays Draft). The DB posting gates (ck_invoice_posting_status /
    ck_invoice_posted_at) backstop a partial Posted row.
    """
    invoice = _lock_invoice(db, invoice_id)
    if invoice is None:
        return None
    if invoice["posting_status"] != "Draft":
        raise ValueError("Only a draft can be posted")
    if any(line["quantity"] <= 0 for line in _lines(db, invoice_id)):
        raise ValueError("Invoice has non-positive line quantity")

    lines = _lines(db, invoice_id)
    for line in lines:
        inventory.record_movement(
            db, actor_id=actor_id, warehouse_id=invoice["warehouse_id"],
            product_id=line["product_id"], batch_id=line["batch_id"],
            movement_type="sale", quantity=-abs(line["quantity"]),
            unit_cost=line["unit_price"], source_type="invoice", source_id=invoice_id)
    finance.record_sale(
        db, customer_id=invoice["customer_id"], invoice_id=invoice_id,
        amount=invoice["grand_total"], on_date=invoice["invoice_date"],
        actor_id=actor_id)
    db.execute(text("""
        UPDATE sales.sales_invoice
           SET posting_status='Posted', posted_at=now(), posted_by=:actor,
               version=version+1
         WHERE id=:id
    """), {"actor": actor_id, "id": invoice_id})
    updated = _lock_invoice(db, invoice_id)
    return dict(updated)
