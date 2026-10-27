"""Inventory stock ledger and balances.

A movement is an append-only ledger row; the balance row is the running total
per (warehouse, product, batch). Both are written in the caller's transaction,
so a failed movement cannot leave a half-applied balance.
"""

from sqlalchemy import text


class InsufficientStock(Exception):
    """A movement would drive a stock balance below zero."""


def _apply_balance(db, warehouse_id, product_id, batch_id, delta):
    """Add `delta` to one balance row atomically; return the new quantity."""
    keys = {"w": warehouse_id, "p": product_id, "b": batch_id}
    if delta >= 0:
        inserted = db.execute(
            text("""
            INSERT INTO inventory.stock_balance
                (warehouse_id, product_id, batch_id, quantity, updated_at)
            VALUES (:w, :p, :b, :delta, now())
            ON CONFLICT DO NOTHING
            RETURNING quantity
        """),
            {**keys, "delta": delta},
        ).scalar()
        if inserted is not None:
            return inserted
    current = db.execute(
        text("""
        SELECT quantity FROM inventory.stock_balance
        WHERE warehouse_id=:w AND product_id=:p AND batch_id IS NOT DISTINCT FROM :b
        FOR UPDATE
    """),
        keys,
    ).scalar_one_or_none()
    if current is None:
        raise InsufficientStock("No stock balance exists to decrease")
    new_quantity = current + delta
    if new_quantity < 0:
        raise InsufficientStock(f"Available {current}, requested {delta}")
    db.execute(
        text("""
        UPDATE inventory.stock_balance SET quantity=:q, updated_at=now()
        WHERE warehouse_id=:w AND product_id=:p AND batch_id IS NOT DISTINCT FROM :b
    """),
        {**keys, "q": new_quantity},
    )
    return new_quantity


def record_movement(
    db,
    *,
    actor_id,
    warehouse_id,
    product_id,
    batch_id,
    movement_type,
    quantity,
    unit_cost=None,
    source_type="manual",
    source_id=None,
    note=None,
    invoice_line_id=None,
    reverses_movement_id=None,
):
    """Append a movement and update its balance in the caller's transaction."""
    balance = _apply_balance(db, warehouse_id, product_id, batch_id, quantity)
    movement_id = db.execute(
        text("""
        INSERT INTO inventory.stock_movement
            (warehouse_id, product_id, batch_id, movement_type, quantity,
             unit_cost, source_type, source_id, note, created_by, invoice_line_id, reverses_movement_id)
        VALUES (:w, :p, :b, :mt, :q, :uc, :st, :sid, :note, :actor, :line, :reverses)
        RETURNING id
    """),
        {
            "w": warehouse_id,
            "p": product_id,
            "b": batch_id,
            "mt": movement_type,
            "q": quantity,
            "uc": unit_cost,
            "st": source_type,
            "sid": source_id,
            "note": note,
            "actor": actor_id,
            "line": invoice_line_id,
            "reverses": reverses_movement_id,
        },
    ).scalar_one()
    return movement_id, balance


def fetch_movement(db, movement_id):
    row = (
        db.execute(
            text("SELECT * FROM inventory.stock_movement WHERE id=:id"),
            {"id": movement_id},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def _filters(
    warehouse_id=None,
    product_id=None,
    batch_id=None,
    movement_type=None,
    date_from=None,
    date_to=None,
    warehouse_ids=None,
):
    """Build a WHERE clause from bound values; column names are fixed literals."""
    clauses, params = [], {}
    if warehouse_ids is not None:
        if warehouse_ids:
            clauses.append("warehouse_id = ANY(CAST(:warehouse_ids AS uuid[]))")
            params["warehouse_ids"] = [str(w) for w in warehouse_ids]
        else:
            clauses.append("1 = 0")
    for column, value in (
        ("warehouse_id", warehouse_id),
        ("product_id", product_id),
        ("batch_id", batch_id),
        ("movement_type", movement_type),
    ):
        if value is not None:
            clauses.append(f"{column} = :{column}")
            params[column] = value
    if date_from is not None:
        clauses.append("created_at >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        clauses.append("created_at < :date_to")
        params["date_to"] = date_to
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def list_batches(
    db, warehouse_id=None, product_id=None, warehouse_ids=None
):
    """Batch/expiry snapshots: every batch with its on-hand quantity, FEFO order.

    LEFT JOIN keeps batches without any balance row (quantity 0) visible.
    """
    clauses, params = [], {}
    if warehouse_ids is not None:
        if warehouse_ids:
            clauses.append("b.warehouse_id = ANY(CAST(:warehouse_ids AS uuid[]))")
            params["warehouse_ids"] = [str(w) for w in warehouse_ids]
        else:
            clauses.append("1 = 0")
    if warehouse_id is not None:
        clauses.append("b.warehouse_id = :warehouse_id"); params["warehouse_id"] = warehouse_id
    if product_id is not None:
        clauses.append("b.product_id = :product_id"); params["product_id"] = product_id
    clause = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(
        text(
            "SELECT b.id, b.product_id, b.warehouse_id, b.batch_no, "
            "b.manufacture_date, b.expiry_date, COALESCE(sb.quantity, 0) AS quantity "
            "FROM inventory.batch_record b "
            "LEFT JOIN inventory.stock_balance sb "
            "ON sb.batch_id = b.id AND sb.warehouse_id = b.warehouse_id "
            "AND sb.product_id = b.product_id"
            + clause +
            " ORDER BY b.expiry_date, b.batch_no"
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def cover_report(
    db, window_days, threshold_days, warehouse_id=None, product_id=None,
    warehouse_ids=None,
):
    """Stock-cover / overstock per (warehouse, product) from real ledgers only.

    Cover days = on-hand ÷ (posted sales quantity in the window ÷ window).
    With no posted sales in the window the status is ``no_sales_history`` —
    never a fabricated rate.
    """
    clauses, params = [], {"window_days": window_days}
    if warehouse_ids is not None:
        if warehouse_ids:
            clauses.append("bal.warehouse_id = ANY(CAST(:warehouse_ids AS uuid[]))")
            params["warehouse_ids"] = [str(w) for w in warehouse_ids]
        else:
            clauses.append("1 = 0")
    if warehouse_id is not None:
        clauses.append("bal.warehouse_id = :warehouse_id")
        params["warehouse_id"] = warehouse_id
    if product_id is not None:
        clauses.append("bal.product_id = :product_id")
        params["product_id"] = product_id
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(
        text("""
        WITH bal AS (
            SELECT warehouse_id, product_id, SUM(quantity) AS on_hand
            FROM inventory.stock_balance
            GROUP BY warehouse_id, product_id
            HAVING SUM(quantity) > 0
        ),
        sales_rate AS (
            SELECT i.warehouse_id AS w, l.product_id AS p,
                   SUM(l.quantity) AS sold
            FROM sales.sales_invoice i
            JOIN sales.sales_invoice_line l ON l.invoice_id = i.id
            WHERE i.posting_status = 'Posted'
              AND i.invoice_date >= CURRENT_DATE - CAST(:window_days AS integer)
              AND i.invoice_date <= CURRENT_DATE
            GROUP BY 1, 2
        )
        SELECT bal.warehouse_id, bal.product_id, bal.on_hand, s.sold
        FROM bal LEFT JOIN sales_rate s
            ON s.w = bal.warehouse_id AND s.p = bal.product_id
        """ + where + " ORDER BY bal.warehouse_id, bal.product_id"),
        params,
    ).mappings()
    report = []
    for row in rows:
        on_hand = row["on_hand"]
        sold = row["sold"]
        avg_daily = sold / window_days if sold is not None else None
        cover_days = on_hand / avg_daily if avg_daily else None
        if sold is None:
            status = "no_sales_history"
        elif cover_days > threshold_days:
            status = "overstock"
        else:
            status = "ok"
        report.append({
            "warehouse_id": row["warehouse_id"],
            "product_id": row["product_id"],
            "on_hand": on_hand,
            "sold_in_window": sold,
            "avg_daily_sales": avg_daily,
            "cover_days": cover_days,
            "window_days": window_days,
            "threshold_days": threshold_days,
            "status": status,
        })
    return report


def list_balances(
    db, warehouse_id=None, product_id=None, batch_id=None, warehouse_ids=None
):
    where, params = _filters(
        warehouse_id, product_id, batch_id, warehouse_ids=warehouse_ids
    )
    rows = db.execute(
        text(
            "SELECT warehouse_id, product_id, batch_id, quantity, updated_at "
            "FROM inventory.stock_balance"
            + where
            + " ORDER BY warehouse_id, product_id, batch_id NULLS LAST"
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def list_movements(
    db,
    warehouse_id=None,
    product_id=None,
    batch_id=None,
    movement_type=None,
    date_from=None,
    date_to=None,
    warehouse_ids=None,
    scoped_user_id=None,
):
    where, params = _filters(
        warehouse_id,
        product_id,
        batch_id,
        movement_type,
        date_from,
        date_to,
        warehouse_ids=warehouse_ids,
    )
    if scoped_user_id is not None:
        # A shared stock pool is not permission to read every source invoice.
        where += (
            (" AND " if where else " WHERE ")
            + """(
            (source_type = 'manual' AND source_id IS NULL)
            OR (source_type = 'invoice' AND EXISTS (
                SELECT 1 FROM sales.sales_invoice i
                JOIN platform.user_branch ub ON ub.branch_id = i.branch_id
                JOIN platform.user_territory ut ON ut.territory_id = i.territory_id
                WHERE i.id = stock_movement.source_id
                  AND i.warehouse_id = stock_movement.warehouse_id
                  AND ub.user_id = :scoped_user_id AND ut.user_id = :scoped_user_id
            ))
        )"""
        )
        params["scoped_user_id"] = scoped_user_id
    rows = db.execute(
        text(
            "SELECT * FROM inventory.stock_movement"
            + where
            + " ORDER BY created_at DESC, id"
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def expiry_warnings(
    db, warning_days: int, warehouse_id=None, warehouse_ids=None
):
    """Batches expiring within `warning_days` days (V2 §2B.7)."""
    clauses, params = [], {"days": warning_days}
    if warehouse_ids is not None:
        if warehouse_ids:
            clauses.append("b.warehouse_id = ANY(CAST(:warehouse_ids AS uuid[]))")
            params["warehouse_ids"] = [str(w) for w in warehouse_ids]
        else:
            clauses.append("1 = 0")
    if warehouse_id is not None:
        clauses.append("b.warehouse_id = :warehouse_id")
        params["warehouse_id"] = warehouse_id
    clause = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(
        text(
            "SELECT b.id, b.product_id, b.warehouse_id, b.batch_no, "
            "b.manufacture_date, b.expiry_date, "
            "COALESCE(sb.quantity, 0) AS quantity, "
            "(b.expiry_date - CURRENT_DATE) AS days_until_expiry "
            "FROM inventory.batch_record b "
            "LEFT JOIN inventory.stock_balance sb "
            "ON sb.batch_id = b.id AND sb.warehouse_id = b.warehouse_id "
            "AND sb.product_id = b.product_id"
            + clause +
            " AND b.expiry_date <= CURRENT_DATE + CAST(:days AS integer) "
            "AND b.expiry_date >= CURRENT_DATE "
            "AND COALESCE(sb.quantity, 0) > 0 "
            "ORDER BY b.expiry_date, b.batch_no"
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]
