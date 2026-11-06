"""Read-only AR aging buckets by due date.

Each ledger entry contributes its signed amount (debit - credit) to the bucket
for its due_date; entries without a due_date go to 'undated'. This is a
ledger-due-date aging, not invoice-outstanding aging: the current posting flow
does not set ar_entry.due_date for invoices, so posted invoices appear under
'undated' until a due date is recorded.
"""

from decimal import Decimal

from sqlalchemy import text

BUCKETS = ("current", "d1_30", "d31_60", "d61_90", "over_90", "undated")


def bucket_for(due_date, as_of):
    if due_date is None:
        return "undated"
    if due_date >= as_of:
        return "current"
    overdue = (as_of - due_date).days
    if overdue <= 30:
        return "d1_30"
    if overdue <= 60:
        return "d31_60"
    if overdue <= 90:
        return "d61_90"
    return "over_90"


def aging(db, *, as_of, customer_id=None, branches=None, territory_id=None):
    clauses, params = [], {"as_of": as_of}
    if customer_id is not None:
        clauses.append("e.customer_id = :customer_id")
        params["customer_id"] = str(customer_id)
    if branches is not None:
        clauses.append("c.branch_id = ANY(CAST(:branches AS uuid[]))")
        params["branches"] = [str(b) for b in branches]
    if territory_id is not None:
        clauses.append("c.territory_id = :territory_id")
        params["territory_id"] = str(territory_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(
        text(
            "SELECT e.customer_id, e.due_date, e.debit, e.credit "
            "FROM finance.ar_entry e "
            "JOIN master_data.master_customer c ON c.id = e.customer_id"
            + where
        ),
        params,
    ).fetchall()
    per_customer = {}
    for customer, due_date, debit, credit in rows:
        buckets = per_customer.setdefault(
            str(customer), {name: Decimal(0) for name in BUCKETS})
        buckets[bucket_for(due_date, as_of)] += Decimal(debit) - Decimal(credit)
    customers = []
    totals = {name: Decimal(0) for name in BUCKETS}
    for key in sorted(per_customer):
        buckets = per_customer[key]
        for name in BUCKETS:
            totals[name] += buckets[name]
        customers.append({"customer_id": key, **buckets, "total": sum(buckets.values())})
    return {
        "as_of": as_of,
        "customers": customers,
        "total": {**totals, "total": sum(totals.values())},
    }
