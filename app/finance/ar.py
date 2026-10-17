"""Customer receivables ledger (finance.ar) + user->warehouse access scope.

balance = Σ(debit) - Σ(credit) per customer, matching the Excel العملاء rule.
The `invoice` entry_type is produced only by record_sale (the posting flow);
the API schema restricts client-supplied types to opening/payment/credit_note/
adjustment, so a client cannot fabricate an invoice AR entry.
"""
from sqlalchemy import text


def record_entry(db, *, customer_id, entry_type, debit=0, credit=0, on_date,
                 due_date=None, reason_id=None, note=None, actor_id, invoice_id=None):
    row = db.execute(text("""
        INSERT INTO finance.ar_entry
            (customer_id, invoice_id, entry_type, entry_date, due_date,
             debit, credit, reason_id, note, created_by)
        VALUES (:c, :inv, :et, :d, :due, :debit, :credit, :r, :note, :actor)
        RETURNING id
    """), {"c": str(customer_id), "inv": str(invoice_id) if invoice_id else None,
           "et": entry_type, "d": on_date, "due": due_date, "debit": debit, "credit": credit,
           "r": str(reason_id) if reason_id else None, "note": note, "actor": str(actor_id)}).scalar_one()
    return row


def record_sale(db, *, customer_id, invoice_id, amount, on_date, due_date=None, actor_id):
    """One debit entry per posted invoice (amount = grand_total)."""
    return record_entry(db, customer_id=customer_id, entry_type="invoice", debit=amount,
                        credit=0, on_date=on_date, due_date=due_date, note=None, actor_id=actor_id,
                        invoice_id=invoice_id)


def customer_balance(db, customer_id):
    """Σ(debit) - Σ(credit). Matches Excel الرصيد = مدين - دائن."""
    return db.execute(text(
        "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance "
        "FROM finance.ar_entry WHERE customer_id = :c"), {"c": str(customer_id)}).scalar()


def list_entries(db, customer_id=None, entry_type=None, date_from=None, date_to=None):
    """Column names are fixed literals; values are bound parameters."""
    clauses, params = [], {}
    for column, value in (("customer_id", customer_id), ("entry_type", entry_type)):
        if value is not None:
            clauses.append(f"{column} = :{column}")
            params[column] = str(value) if column == "customer_id" else value
    if date_from is not None:
        clauses.append("entry_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        clauses.append("entry_date < :date_to")
        params["date_to"] = date_to
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(text(
        "SELECT * FROM finance.ar_entry" + where + " ORDER BY entry_date DESC, id"), params).mappings()
    return [dict(row) for row in rows]


def warehouses_for_user(db, user_id):
    """Warehouses a user may touch via branch assignment.

    Owner is not special-cased here; callers check is_owner first. Returns all
    warehouse ids in any branch the user is assigned to via platform.user_branch.
    """
    rows = db.execute(text("""
        SELECT DISTINCT w.id AS warehouse_id
        FROM platform.user_branch ub
        JOIN master_data.master_warehouse w ON w.branch_id = ub.branch_id
        WHERE ub.user_id = :u
    """), {"u": str(user_id)}).fetchall()
    return [r[0] for r in rows]
