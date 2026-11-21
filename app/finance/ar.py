"""Customer receivables ledger (finance.ar) + user->warehouse access scope.

balance = Σ(debit) - Σ(credit) per customer, matching the Excel العملاء rule.
The `invoice` entry_type is produced only by record_sale (the posting flow);
the API schema restricts client-supplied types to opening/payment/credit_note/
adjustment, so a client cannot fabricate an invoice AR entry.
"""

from sqlalchemy import text


def record_entry(
    db,
    *,
    customer_id,
    entry_type,
    debit=0,
    credit=0,
    on_date,
    due_date=None,
    reason_id=None,
    note=None,
    actor_id,
    invoice_id=None,
    receipt_id=None,
    reverses_entry_id=None,
):
    return db.execute(
        text("""
        INSERT INTO finance.ar_entry
            (customer_id, invoice_id, entry_type, entry_date, due_date,
             debit, credit, reason_id, note, created_by, receipt_id, reverses_entry_id)
        VALUES (:c, :inv, :et, :d, :due, :debit, :credit, :r, :note, :actor, :receipt, :reverses)
        RETURNING id
    """),
        {
            "c": customer_id,
            "inv": invoice_id,
            "et": entry_type,
            "d": on_date,
            "due": due_date,
            "debit": debit,
            "credit": credit,
            "r": reason_id,
            "note": note,
            "actor": actor_id,
            "receipt": receipt_id,
            "reverses": reverses_entry_id,
        },
    ).scalar_one()


def record_sale(
    db, *, customer_id, invoice_id, amount, on_date, due_date=None, actor_id
):
    """One debit entry per posted invoice (amount = grand_total)."""
    return record_entry(
        db,
        customer_id=customer_id,
        entry_type="invoice",
        debit=amount,
        credit=0,
        on_date=on_date,
        due_date=due_date,
        note=None,
        actor_id=actor_id,
        invoice_id=invoice_id,
    )


def customer_balance(db, customer_id):
    """Σ(debit) - Σ(credit). Matches Excel الرصيد = مدين - دائن."""
    return db.execute(
        text(
            "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance "
            "FROM finance.ar_entry WHERE customer_id = :c"
        ),
        {"c": str(customer_id)},
    ).scalar()


def balances(db, *, branches=None, customer_id=None, territory_id=None):
    """Balances for one customer or every visible customer, exact strings.

    branches=None means unrestricted (owner/finance/read_only_auditor); a set
    restricts to customers in those branches. territory_id is an opt-in filter.
    """
    if customer_id is not None:
        return [{"customer_id": str(customer_id),
                 "balance": str(customer_balance(db, customer_id))}]
    where, params = [], {}
    if branches is not None:
        where.append("c.branch_id = ANY(CAST(:branches AS uuid[]))")
        params["branches"] = [str(b) for b in branches]
    if territory_id is not None:
        where.append("c.territory_id = :territory_id")
        params["territory_id"] = str(territory_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.execute(text(
        "SELECT c.id AS customer_id, COALESCE(SUM(e.debit), 0) - COALESCE(SUM(e.credit), 0) AS balance "
        "FROM master_data.master_customer c "
        "LEFT JOIN finance.ar_entry e ON e.customer_id = c.id " + where_sql +
        " GROUP BY c.id ORDER BY c.id"), params).mappings()
    return [{"customer_id": str(r["customer_id"]), "balance": str(r["balance"])} for r in rows]


def list_entries(db, customer_id=None, entry_type=None, date_from=None, date_to=None, branches=None, limit=None, offset=0):
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
    if branches is not None:
        if not branches:
            return []
        clauses.append(
            "EXISTS (SELECT 1 FROM master_data.master_customer c WHERE c.id = e.customer_id AND c.branch_id = ANY(CAST(:branches AS uuid[])))"
        )
        params["branches"] = [str(b) for b in branches]
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    limit_offset = ""
    if limit is not None:
        limit_offset = " LIMIT :limit OFFSET :offset"
        params["limit"] = int(limit)
        params["offset"] = int(offset)
    rows = db.execute(
        text(
            "SELECT * FROM finance.ar_entry e" + where + " ORDER BY entry_date DESC, id" + limit_offset
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def warehouses_for_user(db, user_id):
    """Warehouses a user may touch via branch assignment.

    Owner is not special-cased here; callers check is_owner first. Returns all
    warehouse ids in any branch the user is assigned to via platform.user_branch.
    """
    rows = db.execute(
        text("""
        SELECT DISTINCT w.id AS warehouse_id
        FROM platform.user_branch ub
        JOIN master_data.master_warehouse w ON w.branch_id = ub.branch_id
        WHERE ub.user_id = :u
    """),
        {"u": str(user_id)},
    ).fetchall()
    return [r[0] for r in rows]
