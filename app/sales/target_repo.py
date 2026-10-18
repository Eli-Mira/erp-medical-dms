"""Sales-target persistence; commits belong to the API transaction (V2 §2B.13)."""
from sqlalchemy import text


def list_targets(db, *, rep_id, product_id, month):
    """Target rows joined to actual posted sales, ordered for management reading.

    Whole-book targets (product NULL) compare against everything the rep sold
    that month; product targets against that product only.
    """
    conditions, params = [], {}
    if rep_id is not None:
        conditions.append("t.rep_id = :rep_id")
        params["rep_id"] = rep_id
    if product_id is not None:
        conditions.append("t.product_id = :product_id")
        params["product_id"] = product_id
    if month is not None:
        conditions.append("t.period_month = :month")
        params["month"] = month
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text("""
        WITH per_product AS (
            SELECT i.rep_id AS r, l.product_id AS p,
                   date_trunc('month', i.invoice_date)::date AS m,
                   SUM(l.quantity) AS sold
            FROM sales.sales_invoice i
            JOIN sales.sales_invoice_line l ON l.invoice_id = i.id
            WHERE i.posting_status = 'Posted'
            GROUP BY 1, 2, 3
        ),
        per_rep AS (
            SELECT i.rep_id AS r,
                   date_trunc('month', i.invoice_date)::date AS m,
                   SUM(l.quantity) AS sold
            FROM sales.sales_invoice i
            JOIN sales.sales_invoice_line l ON l.invoice_id = i.id
            WHERE i.posting_status = 'Posted'
            GROUP BY 1, 2
        )
        SELECT t.id, t.rep_id, t.product_id, t.period_month, t.target_quantity,
               CASE WHEN t.product_id IS NULL THEN pr.sold ELSE pp.sold END
                   AS actual_quantity,
               t.created_by, t.created_at
        FROM sales.sales_target t
        LEFT JOIN per_rep pr ON pr.r = t.rep_id AND pr.m = t.period_month
        LEFT JOIN per_product pp ON pp.r = t.rep_id AND pp.p = t.product_id
                                AND pp.m = t.period_month
        """ + where + " ORDER BY t.period_month DESC, t.rep_id, t.product_id NULLS LAST, t.id"),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def upsert(db, *, actor_id, rep_id, product_id, period_month, target_quantity):
    """Set-or-replace one target; the partial unique indexes prevent duplicates."""
    updated = db.execute(
        text("""
        UPDATE sales.sales_target SET target_quantity = :qty
        WHERE rep_id = :rep
          AND period_month = :month
          AND product_id IS NOT DISTINCT FROM :product
        RETURNING id
    """),
        {"rep": rep_id, "product": product_id, "month": period_month,
         "qty": target_quantity},
    ).scalar()
    if updated is not None:
        return updated
    created = db.execute(
        text("""
        INSERT INTO sales.sales_target
            (rep_id, product_id, period_month, target_quantity, created_by)
        VALUES (:rep, :product, :month, :qty, :actor)
        RETURNING id
    """),
        {"rep": rep_id, "product": product_id, "month": period_month,
         "qty": target_quantity, "actor": actor_id},
    ).scalar()
    if created is None:
        raise ValueError("upsert did not persist")
    return created


def fetch_target(db, target_id):
    row = db.execute(
        text("SELECT * FROM sales.sales_target WHERE id=:id"), {"id": target_id},
    ).mappings().one_or_none()
    return dict(row) if row else None


def existing_target(db, rep_id, product_id, period_month):
    row = db.execute(
        text("SELECT target_quantity FROM sales.sales_target "
             "WHERE rep_id=:rep AND period_month=:month "
             "AND product_id IS NOT DISTINCT FROM :product"),
        {"rep": rep_id, "product": product_id, "month": period_month},
    ).mappings().one_or_none()
    return None if row is None else dict(row)
