"""Read-only AR aging buckets by due date.

Each ledger entry contributes its signed amount (debit - credit) to the bucket
for its due_date; entries without a due_date go to 'undated'. Only entries dated
on or before the as-of date are included.

This is ledger aging, not invoice-outstanding aging: the current posting flow
does not set ar_entry.due_date for invoices, so posted invoices appear under
'undated' until a due date is recorded. Bucket boundaries and due-date rules are
PENDING ACCOUNTANT APPROVAL.
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
    clauses, params = ["e.entry_date <= :as_of"], {"as_of": as_of}
    if customer_id is not None:
        clauses.append("e.customer_id = :customer_id")
        params["customer_id"] = str(customer_id)
    if branches is not None:
        if not branches:
            return {
                "label": "ledger aging",
                "note": "Due-date bucket rules pending accountant approval.",
                "as_of": as_of,
                "customers": [],
                "total": {**{name: Decimal(0) for name in BUCKETS}, "total": Decimal(0)},
            }
        clauses.append("c.branch_id = ANY(CAST(:branches AS uuid[]))")
        params["branches"] = [str(b) for b in branches]
    if territory_id is not None:
        clauses.append("c.territory_id = :territory_id")
        params["territory_id"] = str(territory_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(
        text(
            "SELECT e.customer_id, "
            "COALESCE(SUM(CASE WHEN e.due_date IS NOT NULL AND e.due_date >= :as_of THEN e.debit - e.credit ELSE 0 END), 0) AS current, "
            "COALESCE(SUM(CASE WHEN e.due_date IS NOT NULL AND e.due_date < :as_of AND (CAST(:as_of AS date) - e.due_date) <= 30 THEN e.debit - e.credit ELSE 0 END), 0) AS d1_30, "
            "COALESCE(SUM(CASE WHEN e.due_date IS NOT NULL AND (CAST(:as_of AS date) - e.due_date) > 30 AND (CAST(:as_of AS date) - e.due_date) <= 60 THEN e.debit - e.credit ELSE 0 END), 0) AS d31_60, "
            "COALESCE(SUM(CASE WHEN e.due_date IS NOT NULL AND (CAST(:as_of AS date) - e.due_date) > 60 AND (CAST(:as_of AS date) - e.due_date) <= 90 THEN e.debit - e.credit ELSE 0 END), 0) AS d61_90, "
            "COALESCE(SUM(CASE WHEN e.due_date IS NOT NULL AND (CAST(:as_of AS date) - e.due_date) > 90 THEN e.debit - e.credit ELSE 0 END), 0) AS over_90, "
            "COALESCE(SUM(CASE WHEN e.due_date IS NULL THEN e.debit - e.credit ELSE 0 END), 0) AS undated "
            "FROM finance.ar_entry e "
            "JOIN master_data.master_customer c ON c.id = e.customer_id"
            + where
            + " GROUP BY e.customer_id ORDER BY e.customer_id::text"
        ),
        params,
    ).mappings()
    customers = []
    totals = {name: Decimal(0) for name in BUCKETS}
    for row in rows:
        buckets = {name: Decimal(row[name]) for name in BUCKETS}
        for name in BUCKETS:
            totals[name] += buckets[name]
        customers.append(
            {"customer_id": str(row["customer_id"]), **buckets, "total": sum(buckets.values())}
        )
    return {
        "label": "ledger aging",
        "note": "Due-date bucket rules pending accountant approval.",
        "as_of": as_of,
        "customers": customers,
        "total": {**totals, "total": sum(totals.values())},
    }
