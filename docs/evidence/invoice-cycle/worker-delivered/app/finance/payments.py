"""Payment receipt service: create, void, and list receipts linked to invoices.

Receipts are append-only. Voiding appends an AR counter-entry (adjustment debit)
and flips the receipt status to Voided. All writes happen in the caller's
transaction.
"""
from decimal import Decimal
from sqlalchemy import text

from app.finance import ar as finance_ar


def _lock_invoice(db, invoice_id):
    row = db.execute(
        text(
            "SELECT * FROM sales.sales_invoice WHERE id=:id FOR UPDATE"
        ),
        {"id": invoice_id},
    ).mappings().one_or_none()
    if row is None:
        return None
    return dict(row)


def _lock_receipt(db, receipt_id):
    row = db.execute(
        text(
            "SELECT * FROM finance.payment_receipt WHERE id=:id FOR UPDATE"
        ),
        {"id": receipt_id},
    ).mappings().one_or_none()
    if row is None:
        return None
    return dict(row)


def _sum_active_receipts(db, invoice_id):
    """Sum of Active receipt amounts for an invoice."""
    return db.execute(
        text(
            "SELECT COALESCE(SUM(amount), 0) FROM finance.payment_receipt "
            "WHERE invoice_id=:i AND status='Active'"
        ),
        {"i": invoice_id},
    ).scalar()


def create_receipt(db, *, invoice_id, branch_id, customer_id, receipt_no,
                   receipt_date, amount, method, note, actor_id):
    """Insert a receipt and its AR payment credit entry. Returns receipt_id."""
    # Receipt row
    receipt_id = db.execute(
        text(
            """
            INSERT INTO finance.payment_receipt
                (invoice_id, branch_id, customer_id, receipt_no, receipt_date,
                 amount, method, note, created_by, updated_by)
            VALUES (:inv, :b, :c, :no, :d, :amt, :m, :note, :actor, :actor)
            RETURNING id
            """
        ),
        {
            "inv": invoice_id, "b": branch_id, "c": customer_id,
            "no": receipt_no, "d": receipt_date, "amt": amount,
            "m": method, "note": note, "actor": actor_id
        },
    ).scalar_one()

    # AR payment credit entry (reduces customer balance)
    finance_ar.record_entry(
        db,
        customer_id=customer_id,
        entry_type="payment",
        debit=0,
        credit=amount,
        on_date=receipt_date,
        note=f"Receipt {receipt_no}",
        actor_id=actor_id,
        invoice_id=invoice_id,
    )

    return receipt_id


def fetch_receipt(db, receipt_id, *, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    row = db.execute(
        text("SELECT * FROM finance.payment_receipt WHERE id=:id" + suffix),
        {"id": receipt_id},
    ).mappings().one_or_none()
    return dict(row) if row else None


def list_receipts(db, invoice_id=None, customer_id=None, branch_id=None,
                  status=None, date_from=None, date_to=None):
    clauses, params = [], {}
    for col, val in (("invoice_id", invoice_id), ("customer_id", customer_id),
                     ("branch_id", branch_id), ("status", status)):
        if val is not None:
            clauses.append(f"{col} = :{col}")
            params[col] = val
    if date_from is not None:
        clauses.append("receipt_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        clauses.append("receipt_date < :date_to")
        params["date_to"] = date_to
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(
        text(
            "SELECT * FROM finance.payment_receipt" + where +
            " ORDER BY receipt_date DESC, id"
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def void_receipt(db, receipt_id, actor_id, reason_id):
    """Void a receipt: append AR adjustment debit, flip status to Voided."""
    receipt = _lock_receipt(db, receipt_id)
    if receipt is None:
        return None
    if receipt["status"] != "Active":
        raise ValueError("Only Active receipts can be voided")

    # AR adjustment debit (increases customer balance back)
    finance_ar.record_entry(
        db,
        customer_id=receipt["customer_id"],
        entry_type="adjustment",
        debit=receipt["amount"],
        credit=0,
        on_date=receipt["receipt_date"],
        reason_id=reason_id,
        note=f"Void receipt {receipt['receipt_no']}",
        actor_id=actor_id,
        invoice_id=receipt["invoice_id"],
    )

    db.execute(
        text(
            """
            UPDATE finance.payment_receipt
            SET status='Voided', voided_at=now(), voided_by=:actor,
                void_reason_id=:reason, updated_by=:actor, updated_at=now(),
                version=version+1
            WHERE id=:id
            """
        ),
        {"actor": actor_id, "reason": reason_id, "id": receipt_id},
    )

    return _lock_receipt(db, receipt_id)