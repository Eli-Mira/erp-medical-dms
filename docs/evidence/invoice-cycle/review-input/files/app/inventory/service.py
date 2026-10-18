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
