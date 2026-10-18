"""Atomic invoice posting and reversal: stock + AR in one transaction.

Kept as unit-testable functions. HTTP endpoints intentionally stay disabled (409)
until these transactions are verified and Eli signs off on enabling production.
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


def reverse_invoice_atomic(db, invoice_id, actor_id, reason_id):
    """Reverse a Posted invoice atomically (append-only compensating entries):

    1. stock: record 'return' movements (+qty) for each line;
    2. AR: create a 'credit_note' credit entry equal to grand_total;
    3. flip invoice to Voided with void metadata.

    All in the caller's transaction. Prevents reversal if Active receipts exist.
    """
    invoice = _lock_invoice(db, invoice_id)
    if invoice is None:
        return None
    if invoice["posting_status"] != "Posted":
        raise ValueError("Only a Posted invoice can be reversed")
    # Active receipts check
    active = db.execute(text(
        "SELECT COALESCE(SUM(amount), 0) FROM finance.payment_receipt "
        "WHERE invoice_id=:i AND status='Active'"),
        {"i": invoice_id}).scalar()
    if active and active > 0:
        raise ValueError("Active receipts exist; void them first")

    lines = _lines(db, invoice_id)
    for line in lines:
        inventory.record_movement(
            db, actor_id=actor_id, warehouse_id=invoice["warehouse_id"],
            product_id=line["product_id"], batch_id=line["batch_id"],
            movement_type="return", quantity=abs(line["quantity"]),
            unit_cost=line["unit_price"], source_type="invoice_reversal", source_id=invoice_id)
    finance.record_entry(
        db, customer_id=invoice["customer_id"], invoice_id=invoice_id,
        entry_type="credit_note", debit=0, credit=invoice["grand_total"],
        on_date=invoice["invoice_date"], reason_id=reason_id,
        note="Invoice reversal", actor_id=actor_id)
    db.execute(text("""
        UPDATE sales.sales_invoice
           SET posting_status='Voided', voided_at=now(), voided_by=:actor,
               void_reason_id=:reason, updated_by=:actor, updated_at=now(),
               version=version+1
         WHERE id=:id
    """), {"actor": actor_id, "reason": reason_id, "id": invoice_id})
    updated = _lock_invoice(db, invoice_id)
    return dict(updated)
