"""Sales-target persistence; commits belong to the API transaction (V2 §2B.13)."""

from sqlalchemy import text


def list_targets(db, *, rep_id, product_id, month, territory_id=None):
    """Compare each explicit target scope with posted invoice quantities only."""
    conditions, params = [], {}
    for column, value in (
        ("rep_id", rep_id),
        ("territory_id", territory_id),
        ("product_id", product_id),
        ("period_month", month),
    ):
        if value is not None:
            conditions.append("t." + column + " = :" + column)
            params[column] = value
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(
            """
        WITH posted AS (
            SELECT i.rep_id, i.territory_id, l.product_id,
                   date_trunc('month', i.invoice_date)::date AS month,
                   l.quantity
            FROM sales.sales_invoice i
            JOIN sales.sales_invoice_line l ON l.invoice_id = i.id
            WHERE i.posting_status = 'Posted'
        ),
        per_product AS (
            SELECT rep_id, product_id, month, SUM(quantity) AS sold
            FROM posted GROUP BY rep_id, product_id, month
        ),
        per_rep AS (
            SELECT rep_id, month, SUM(quantity) AS sold
            FROM posted GROUP BY rep_id, month
        ),
        per_territory_product AS (
            SELECT territory_id, product_id, month, SUM(quantity) AS sold
            FROM posted GROUP BY territory_id, product_id, month
        ),
        per_territory AS (
            SELECT territory_id, month, SUM(quantity) AS sold
            FROM posted GROUP BY territory_id, month
        )
        SELECT t.id, t.rep_id, t.territory_id, t.product_id,
               t.period_month, t.target_quantity,
               CASE WHEN t.rep_id IS NOT NULL THEN
                   CASE WHEN t.product_id IS NULL THEN pr.sold ELSE pp.sold END
               ELSE
                   CASE WHEN t.product_id IS NULL THEN tr.sold ELSE tp.sold END
               END AS actual_quantity,
               t.created_by, t.created_at
        FROM sales.sales_target t
        LEFT JOIN per_rep pr ON pr.rep_id = t.rep_id AND pr.month = t.period_month
        LEFT JOIN per_product pp ON pp.rep_id = t.rep_id AND pp.product_id = t.product_id
                                AND pp.month = t.period_month
        LEFT JOIN per_territory tr ON tr.territory_id = t.territory_id
                                 AND tr.month = t.period_month
        LEFT JOIN per_territory_product tp ON tp.territory_id = t.territory_id
                                         AND tp.product_id = t.product_id
                                         AND tp.month = t.period_month
        """
            + where
            + " ORDER BY t.period_month DESC, t.rep_id NULLS LAST, "
            "t.territory_id NULLS LAST, t.product_id NULLS LAST, t.id"
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def upsert(
    db,
    *,
    actor_id,
    rep_id,
    product_id,
    period_month,
    target_quantity,
    territory_id=None,
):
    """Atomically set one scope; conflict identifiers are fixed internal literals."""
    scope = "rep_id" if rep_id is not None else "territory_id"
    columns = scope + ", period_month"
    predicate = "product_id IS NULL"
    if product_id is not None:
        columns = scope + ", product_id, period_month"
        predicate = "product_id IS NOT NULL"
    if territory_id is not None:
        predicate += " AND territory_id IS NOT NULL"
    return db.execute(
        text(
            """
        INSERT INTO sales.sales_target
            (rep_id, territory_id, product_id, period_month, target_quantity, created_by)
        VALUES (:rep, :territory, :product, :month, :qty, :actor)
        ON CONFLICT ("""
            + columns
            + ") WHERE "
            + predicate
            + """
        DO UPDATE SET target_quantity = EXCLUDED.target_quantity
        RETURNING id
        """
        ),
        {
            "rep": rep_id,
            "territory": territory_id,
            "product": product_id,
            "month": period_month,
            "qty": target_quantity,
            "actor": actor_id,
        },
    ).scalar_one()


def fetch_target(db, target_id):
    row = (
        db.execute(
            text("SELECT * FROM sales.sales_target WHERE id=:id"),
            {"id": target_id},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def existing_target(db, rep_id, product_id, period_month, *, territory_id=None):
    row = (
        db.execute(
            text(
                "SELECT target_quantity FROM sales.sales_target "
                "WHERE rep_id IS NOT DISTINCT FROM :rep "
                "AND territory_id IS NOT DISTINCT FROM :territory "
                "AND period_month=:month "
                "AND product_id IS NOT DISTINCT FROM :product"
            ),
            {
                "rep": rep_id,
                "territory": territory_id,
                "product": product_id,
                "month": period_month,
            },
        )
        .mappings()
        .one_or_none()
    )
    return None if row is None else dict(row)
