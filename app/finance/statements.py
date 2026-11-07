"""Read-only customer AR statement.

Opening balance plus running-balance lines over an optional date range. All
money is exact Decimal (no float, no rounding); ordering is (entry_date, id)
so the statement is deterministic. date_from is inclusive and date_to
exclusive, matching ar.list_entries.
"""

from decimal import Decimal

from sqlalchemy import text


def statement(db, *, customer_id, date_from=None, date_to=None):
    params = {"c": str(customer_id)}
    range_clauses = []
    if date_from is not None:
        range_clauses.append("entry_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        range_clauses.append("entry_date < :date_to")
        params["date_to"] = date_to
    range_where = (" AND " + " AND ".join(range_clauses)) if range_clauses else ""
    if date_from is None:
        opening = Decimal(0)  # no start date -> nothing precedes the statement
    else:
        opening = db.execute(
            text(
                "SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance "
                "FROM finance.ar_entry WHERE customer_id = :c AND entry_date < :date_from"
            ),
            {"c": str(customer_id), "date_from": date_from},
        ).scalar()
    rows = db.execute(
        text(
            "SELECT * FROM finance.ar_entry WHERE customer_id = :c"
            + range_where
            + " ORDER BY entry_date ASC, id ASC"
        ),
        params,
    ).mappings()
    running = Decimal(opening)
    total_debit = Decimal(0)
    total_credit = Decimal(0)
    lines = []
    for row in rows:
        entry = dict(row)
        running += Decimal(entry["debit"]) - Decimal(entry["credit"])
        total_debit += Decimal(entry["debit"])
        total_credit += Decimal(entry["credit"])
        entry["balance"] = running
        lines.append(entry)
    return {
        "customer_id": str(customer_id),
        "date_from": date_from,
        "date_to": date_to,
        "opening_balance": Decimal(opening),
        "total_debit": total_debit,
        "total_credit": total_credit,
        "closing_balance": running,
        "lines": lines,
    }
