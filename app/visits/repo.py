"""Customer stock-visit persistence (V2 §2B.10, §2B.11).

One visit carries one or more lines. Sell-through is not a client field the
caller can fudge: the API computes it from the four quantity inputs and the
schema rejects anything that disagrees, so the CHECK on the table is the
enforcement, not a promise in the UI.
"""
from sqlalchemy import text

_LINE_COLS = (
    "l.id, l.visit_id, l.product_id, l.batch_id, l.quantity_prev, "
    "l.quantity_delivered, l.quantity_returned, l.quantity_current, "
    "l.sell_through, l.amount, l.payment_method, l.notes"
)
_VISIT_COLS = "v.id, v.customer_id, v.rep_id, v.visit_date, v.notes, v.created_by, v.created_at"


def _where(conditions, params):
    return (" WHERE " + " AND ".join(conditions)) if conditions else ""


def create_visit(db, *, customer_id, rep_id, visit_date, notes, lines, actor_id):
    """Insert one visit plus its lines in the caller's transaction.

    Returns the visit row with its lines attached. The sell-through CHECK on
    the table rejects any line whose arithmetic disagrees with the formula, so
    the caller cannot persist a fudged figure.
    """
    visit_id = db.execute(
        text(
            "INSERT INTO sales.customer_stock_visit "
            "(customer_id, rep_id, visit_date, notes, created_by) "
            "VALUES (:c, :r, :d, :n, :a) RETURNING id"
        ),
        {"c": customer_id, "r": rep_id, "d": visit_date, "n": notes, "a": actor_id},
    ).scalar_one()

    for line in lines:
        st = (
            line["quantity_prev"]
            + line["quantity_delivered"]
            - line["quantity_returned"]
            - line["quantity_current"]
        )
        db.execute(
            text(
                "INSERT INTO sales.customer_stock_visit_line "
                "(visit_id, product_id, batch_id, quantity_prev, "
                "quantity_delivered, quantity_returned, quantity_current, "
                "sell_through, amount, payment_method, notes) "
                "VALUES (:v, :p, :b, :pv, :dl, :rt, :cu, :st, :am, :pm, :nt)"
            ),
            {
                "v": visit_id,
                "p": line["product_id"],
                "b": line["batch_id"],
                "pv": line["quantity_prev"],
                "dl": line["quantity_delivered"],
                "rt": line["quantity_returned"],
                "cu": line["quantity_current"],
                "st": st,
                "am": line["amount"],
                "pm": line["payment_method"],
                "nt": line["notes"],
            },
        )
    return list_visits(db, visit_id=visit_id)[0]


def delete_visit(db, *, visit_id, actor_id):
    """Hard-delete a visit (operational record, not a posted transaction).

    Returns True if a row was removed. The audit log records the deletion.
    """
    deleted = db.execute(
        text(
            "DELETE FROM sales.customer_stock_visit "
            "WHERE id = :id RETURNING id, customer_id, rep_id, visit_date"
        ),
        {"id": visit_id},
    ).mappings().one_or_none()
    return deleted


def list_visits(db, *, customer_id=None, rep_id=None, visit_id=None,
                visit_date=None, limit=100, offset=0):
    conditions, params = [], {"limit": limit, "offset": offset}
    if customer_id is not None:
        conditions.append("v.customer_id = :c")
        params["c"] = customer_id
    if rep_id is not None:
        conditions.append("v.rep_id = :r")
        params["r"] = rep_id
    if visit_id is not None:
        conditions.append("v.id = :v")
        params["v"] = visit_id
    if visit_date is not None:
        conditions.append("v.visit_date = :d")
        params["d"] = visit_date
    rows = db.execute(
        text(
            f"SELECT {_VISIT_COLS}, {_LINE_COLS} "
            "FROM sales.customer_stock_visit v "
            "JOIN sales.customer_stock_visit_line l ON l.visit_id = v.id"
            f"{_where(conditions, params)} "
            "ORDER BY v.visit_date DESC, v.id, l.id "
            "LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings()
    return [dict(r) for r in rows]


def fetch_visit(db, visit_id):
    rows = list_visits(db, visit_id=visit_id, limit=1)
    if not rows:
        return None
    return rows[0]


def visits_for_customer(db, customer_id, limit=50):
    return list_visits(db, customer_id=customer_id, limit=limit)