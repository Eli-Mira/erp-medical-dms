"""Customer-stock observations; transactions and authorization belong to routes."""

from sqlalchemy import text


def _visit_filter(
    customer_id=None, rep_id=None, visit_id=None, visit_date=None, scope_user_id=None
):
    clauses, params = [], {}
    for column, value in (
        ("customer_id", customer_id),
        ("rep_id", rep_id),
        ("id", visit_id),
        ("visit_date", visit_date),
    ):
        if value is not None:
            clauses.append(f"v.{column} = :{column}")
            params[column] = value
    if scope_user_id is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM platform.user_territory ut WHERE ut.user_id=:scope_user_id AND ut.territory_id=c.territory_id)"
        )
        params["scope_user_id"] = scope_user_id
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def list_visits(
    db,
    *,
    customer_id=None,
    rep_id=None,
    visit_id=None,
    visit_date=None,
    scope_user_id=None,
    limit=100,
    offset=0,
):
    where, params = _visit_filter(
        customer_id, rep_id, visit_id, visit_date, scope_user_id
    )
    source = " FROM sales.customer_stock_visit v JOIN master_data.master_customer c ON c.id=v.customer_id"
    total = db.execute(text("SELECT count(*)" + source + where), params).scalar_one()
    visits = [
        dict(row)
        for row in db.execute(
            text(
                "SELECT v.*"
                + source
                + where
                + " ORDER BY v.visit_date DESC, v.created_at DESC, v.id DESC LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": limit, "offset": offset},
        ).mappings()
    ]
    if visits:
        by_id = {row["id"]: row for row in visits}
        for row in visits:
            row["lines"] = []
        rows = db.execute(
            text(
                "SELECT * FROM sales.customer_stock_visit_line WHERE visit_id=ANY(CAST(:ids AS uuid[])) ORDER BY visit_id, id"
            ),
            {"ids": [str(row["id"]) for row in visits]},
        ).mappings()
        for row in rows:
            by_id[row["visit_id"]]["lines"].append(dict(row))
    return {"total": total, "items": visits}


def fetch_visit(db, visit_id):
    rows = list_visits(db, visit_id=visit_id, limit=1)["items"]
    return rows[0] if rows else None


def _refresh_held_stock(db, customer_id, product_id, batch_id):
    """Refresh the latest remaining observation while the customer row is locked."""
    keys = {"customer_id": customer_id, "product_id": product_id, "batch_id": batch_id}
    latest = (
        db.execute(
            text("""
        SELECT v.id, l.quantity_current
        FROM sales.customer_stock_visit v
        JOIN sales.customer_stock_visit_line l ON l.visit_id=v.id
        WHERE v.customer_id=:customer_id AND l.product_id=:product_id
          AND l.batch_id IS NOT DISTINCT FROM :batch_id
        ORDER BY v.visit_date DESC, v.created_at DESC, v.id DESC LIMIT 1
    """),
            keys,
        )
        .mappings()
        .one_or_none()
    )
    if latest is None:
        db.execute(
            text(
                "DELETE FROM sales.customer_held_stock WHERE customer_id=:customer_id AND product_id=:product_id AND batch_id IS NOT DISTINCT FROM :batch_id"
            ),
            keys,
        )
    else:
        db.execute(
            text("""
            INSERT INTO sales.customer_held_stock
                (customer_id, product_id, batch_id, quantity_on_hand, last_visit_id)
            VALUES (:customer_id, :product_id, :batch_id, :quantity, :visit_id)
            ON CONFLICT (customer_id, product_id, batch_id) DO UPDATE SET
                quantity_on_hand=EXCLUDED.quantity_on_hand,
                last_visit_id=EXCLUDED.last_visit_id, updated_at=clock_timestamp()
        """),
            {**keys, "quantity": latest["quantity_current"], "visit_id": latest["id"]},
        )


def create_visit(db, *, customer_id, rep_id, visit_date, notes, lines, actor_id):
    visit_id = db.execute(
        text("""
        INSERT INTO sales.customer_stock_visit
            (customer_id, rep_id, visit_date, notes, created_by, created_at)
        VALUES (:customer_id, :rep_id, :visit_date, :notes, :actor_id, clock_timestamp())
        RETURNING id
    """),
        {
            "customer_id": customer_id,
            "rep_id": rep_id,
            "visit_date": visit_date,
            "notes": notes,
            "actor_id": actor_id,
        },
    ).scalar_one()
    for line in lines:
        sold = (
            line["quantity_prev"]
            + line["quantity_delivered"]
            - line["quantity_returned"]
            - line["quantity_current"]
        )
        db.execute(
            text("""
            INSERT INTO sales.customer_stock_visit_line
                (visit_id, product_id, batch_id, quantity_prev, quantity_delivered,
                 quantity_returned, quantity_current, sell_through, amount, payment_method, notes)
            VALUES (:visit_id, :product_id, :batch_id, :quantity_prev, :quantity_delivered,
                    :quantity_returned, :quantity_current, :sell_through, :amount, :payment_method, :notes)
        """),
            {**line, "visit_id": visit_id, "sell_through": sold},
        )
        _refresh_held_stock(db, customer_id, line["product_id"], line["batch_id"])
    return fetch_visit(db, visit_id)


def delete_visit(db, *, visit):
    db.execute(
        text("DELETE FROM sales.customer_stock_visit WHERE id=:id"), {"id": visit["id"]}
    )
    for line in visit["lines"]:
        _refresh_held_stock(
            db, visit["customer_id"], line["product_id"], line["batch_id"]
        )


def list_held_stock(
    db,
    *,
    customer_id=None,
    product_id=None,
    batch_id=None,
    scope_user_id=None,
    limit=100,
    offset=0,
):
    clauses, params = [], {}
    for column, value in (
        ("customer_id", customer_id),
        ("product_id", product_id),
        ("batch_id", batch_id),
    ):
        if value is not None:
            clauses.append(f"chs.{column} = :{column}")
            params[column] = value
    if scope_user_id is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM platform.user_territory ut WHERE ut.user_id=:scope_user_id AND ut.territory_id=c.territory_id)"
        )
        params["scope_user_id"] = scope_user_id
    source = " FROM sales.customer_held_stock chs JOIN master_data.master_customer c ON c.id=chs.customer_id"
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    total = db.execute(text("SELECT count(*)" + source + where), params).scalar_one()
    rows = db.execute(
        text(
            "SELECT chs.*"
            + source
            + where
            + " ORDER BY chs.customer_id, chs.product_id, chs.batch_id NULLS LAST, chs.id LIMIT :limit OFFSET :offset"
        ),
        {**params, "limit": limit, "offset": offset},
    ).mappings()
    return {"total": total, "items": [dict(row) for row in rows]}
