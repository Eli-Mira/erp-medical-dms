"""Parameterized invoice persistence; commits belong to the API transaction."""
from sqlalchemy import text


def fetch_invoice(db, invoice_id, *, lock=False):
    suffix = " FOR UPDATE" if lock else " FOR SHARE"
    row = db.execute(text("SELECT * FROM sales.sales_invoice WHERE id=:id" + suffix), {"id": invoice_id}).mappings().one_or_none()
    if row is None:
        return None
    result = dict(row)
    result["lines"] = [dict(line) for line in db.execute(
        text("SELECT * FROM sales.sales_invoice_line WHERE invoice_id=:id ORDER BY line_no"), {"id": invoice_id}
    ).mappings()]
    return result


def list_invoices(db, *, customer_id, status, date_from, date_to, limit, offset,
                  territories, created_by, posted_only):
    """Scoped invoice listing WHERE conditions come only from fixed literals."""
    conditions, params = [], {"limit": limit, "offset": offset}
    if customer_id is not None:
        conditions.append("i.customer_id = :customer_id"); params["customer_id"] = customer_id
    if status is not None:
        conditions.append("i.posting_status = :status"); params["status"] = status
    if date_from is not None:
        conditions.append("i.invoice_date >= :date_from"); params["date_from"] = date_from
    if date_to is not None:
        conditions.append("i.invoice_date <= :date_to"); params["date_to"] = date_to
    if territories is not None:
        conditions.append("i.territory_id = ANY(:territories)"); params["territories"] = territories
    if created_by is not None:
        conditions.append("i.created_by = :created_by"); params["created_by"] = created_by
    if posted_only:
        conditions.append("i.posted_at IS NOT NULL")
    clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(text(
        "SELECT i.*, count(*) OVER () AS total_count FROM sales.sales_invoice i" + clause +
        " ORDER BY i.invoice_date DESC, i.created_at DESC LIMIT :limit OFFSET :offset"
    ), params).mappings().all()
    total = int(rows[0]["total_count"]) if rows else 0
    # Rows are header snapshots only; lines stay empty — use GET /invoices/{id}.
    return [dict(r, lines=[]) for r in rows], total


def insert_invoice(db, values):
    return db.execute(text("""
        INSERT INTO sales.sales_invoice
            (invoice_no, branch_id, territory_id, warehouse_id, customer_id, invoice_date,
             notes, created_by, updated_by, total_before_discount, total_discount,
             total_net, vat_amount, grand_total)
        VALUES (:invoice_no, :branch_id, :territory_id, :warehouse_id, :customer_id,
                :invoice_date, :notes, :actor, :actor, :total_before_discount,
                :total_discount, :total_net, :vat_amount, :grand_total) RETURNING id
    """), values).scalar_one()


def replace_header(db, invoice_id, values):
    db.execute(text("""
        UPDATE sales.sales_invoice SET
            invoice_no=:invoice_no, branch_id=:branch_id, territory_id=:territory_id,
            warehouse_id=:warehouse_id, customer_id=:customer_id, invoice_date=:invoice_date,
            notes=:notes, updated_by=:actor, updated_at=now(), version=version+1,
            total_before_discount=:total_before_discount, total_discount=:total_discount,
            total_net=:total_net, vat_amount=:vat_amount, grand_total=:grand_total
        WHERE id=:id
    """), {**values, "id": invoice_id})
    db.execute(text("DELETE FROM sales.sales_invoice_line WHERE invoice_id=:id"), {"id": invoice_id})


def insert_lines(db, invoice_id, lines):
    db.execute(text("""
        INSERT INTO sales.sales_invoice_line
            (invoice_id,line_no,product_id,batch_id,quantity,unit_price,discount_pct,
             net_price,line_total,vat_rate,vat_amount,notes)
        VALUES (:invoice_id,:line_no,:product_id,:batch_id,:quantity,:unit_price,
                :discount_pct,:net_price,:line_total,:vat_rate,:vat_amount,:notes)
    """), [{**line, "invoice_id": invoice_id} for line in lines])


def void_draft(db, invoice_id, actor, reason_id):
    db.execute(text("""
        UPDATE sales.sales_invoice SET posting_status='Voided', voided_at=now(),
            voided_by=:actor, void_reason_id=:reason, updated_by=:actor,
            updated_at=now(), version=version+1 WHERE id=:id
    """), {"id": invoice_id, "actor": actor, "reason": reason_id})
