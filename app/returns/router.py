"""Sales returns API (V2 §2B.12): explicit return transactions."""

import ipaddress
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.inventory.router import _scope_warehouses
from decimal import Decimal, ROUND_HALF_UP
from app import config as app_config
from app.finance import ar as finance_ar
from app.inventory import service as inv_service
from app.returns.schemas import ReturnDecisionIn, ReturnIn
from app.sales.calc import vat_amount_for

router = APIRouter(prefix="/returns", tags=["returns"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

MANAGE_ROLES = {"owner", "finance", "warehouse_staff", "sales_manager"}
APPROVE_ROLES = {"owner", "finance"}
# Quarantine returns do not grant access to sellable stock.
GLOBAL_RETURN_ROLES = {"owner", "finance", "read_only_auditor"}


def _role(user, allowed):
    role = user["role"]
    if (
        not user["is_active"]
        or role not in allowed
        or (role == "owner" and not user["is_owner"])
    ):
        raise HTTPException(403, "Returns access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@router.post("", status_code=201)
def create_return(payload: ReturnIn, request: Request, db: Db, current: CurrentUser):
    _role(current, MANAGE_ROLES)
    customer, product = payload.customer_id, payload.product_id
    warehouse, batch = payload.warehouse_id, payload.batch_id
    q, rdate = payload.quantity, payload.return_date.isoformat()
    reason, invoice = payload.reason, payload.invoice_id
    scope = None
    if current["role"] not in GLOBAL_RETURN_ROLES:
        scope = _scope_warehouses(db, current)
    if scope is not None:
        if warehouse not in scope:
            raise HTTPException(404, "Return reference not found")
        if current["role"] == "warehouse_staff":
            scope_check = db.execute(
                text(
                    "SELECT 1 FROM master_data.master_customer c "
                    "JOIN platform.user_branch ub ON ub.branch_id=c.branch_id "
                    "WHERE c.id=:c AND ub.user_id=:u"
                ),
                {"c": customer, "u": current["id"]},
            ).scalar()
            if not scope_check:
                raise HTTPException(404, "Return reference not found")
        else:
            scope_check = db.execute(
                text(
                    "SELECT 1 FROM master_data.master_customer c "
                    "JOIN platform.user_territory ut ON ut.territory_id=c.territory_id "
                    "WHERE c.id=:c AND ut.user_id=:u"
                ),
                {"c": customer, "u": current["id"]},
            ).scalar()
            if not scope_check:
                raise HTTPException(404, "Return reference not found")
    for table, ident, label in (
        ("master_data.master_customer", customer, "customer"),
        ("master_data.master_product", product, "product"),
        ("master_data.master_warehouse", warehouse, "warehouse"),
    ):
        if not db.execute(
            text(f"SELECT 1 FROM {table} WHERE id=:id AND is_active FOR SHARE"),
            {"id": ident},
        ).scalar():
            raise HTTPException(422, f"{label} not active")
    if batch is not None:
        br = (
            db.execute(
                text(
                    "SELECT product_id, warehouse_id FROM inventory.batch_record WHERE id=:id FOR SHARE"
                ),
                {"id": batch},
            )
            .mappings()
            .one_or_none()
        )
        if (
            br is None
            or str(br["product_id"]) != str(product)
            or str(br["warehouse_id"]) != str(warehouse)
        ):
            raise HTTPException(422, "Batch does not match product and warehouse")
    if invoice is not None:
        # Lock the invoice row to prevent concurrent over-return
        inv = db.execute(
            text(
                "SELECT 1 FROM sales.sales_invoice WHERE id=:id AND customer_id=:c FOR UPDATE"
            ),
            {"id": invoice, "c": customer},
        ).scalar()
        if not inv:
            raise HTTPException(422, "Invoice reference is not valid for this customer")
        # Query total invoiced quantity for (invoice_id, product_id)
        invoiced_qty_result = db.execute(
            text(
                "SELECT COALESCE(SUM(quantity), 0) FROM sales.sales_invoice_line WHERE invoice_id=:inv AND product_id=:pid"
            ),
            {"inv": invoice, "pid": product},
        ).scalar()
        invoiced_qty = Decimal(str(invoiced_qty_result))
        # Query already returned quantity for (invoice_id, product_id) across all non-rejected returns
        already_returned_result = db.execute(
            text(
                "SELECT COALESCE(SUM(quantity), 0) FROM sales.sales_return WHERE invoice_id=:inv AND product_id=:pid AND status <> 'rejected'"
            ),
            {"inv": invoice, "pid": product},
        ).scalar()
        already_returned = Decimal(str(already_returned_result))
        qty_decimal = Decimal(str(q))
        if invoiced_qty <= Decimal("0") or already_returned + qty_decimal > invoiced_qty:
            raise HTTPException(422, "Return quantity exceeds invoiced quantity for this product")
    try:
        rid = db.execute(
            text("""INSERT INTO sales.sales_return
                (customer_id, product_id, warehouse_id, batch_id, quantity,
                 return_date, reason, invoice_id, created_by, status)
                VALUES (:c, :p, :w, :b, :q, :rd, :reason, :inv, :actor, 'quarantined')
                RETURNING id"""),
            {
                "c": customer,
                "p": product,
                "w": warehouse,
                "b": batch,
                "q": q,
                "rd": rdate,
                "reason": reason,
                "inv": invoice,
                "actor": current["id"],
            },
        ).scalar()
        # Intake records physical custody only; approval/release is deferred.
        log_audit(
            db,
            current["id"],
            "created",
            "sales_return",
            rid,
            None,
            {
                "customer": str(customer),
                "product": str(product),
                "warehouse": str(warehouse),
                "quantity": str(q),
                "return_date": rdate,
                "status": "quarantined",
            },
            ip_address=_host(request),
            user_agent=request.headers.get("user-agent"),
        )
        result = {
            "id": str(rid),
            "customer_id": customer,
            "product_id": product,
            "warehouse_id": warehouse,
            "batch_id": batch,
            "quantity": str(q),
            "return_date": rdate,
            "reason": reason,
            "status": "quarantined",
        }
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.get("")
def list_returns(
    db: Db,
    current: CurrentUser,
    customer_id: UUID | None = None,
    product_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
):
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit 1..200")
    if offset < 0:
        raise HTTPException(422, "offset >= 0")
    _role(current, MANAGE_ROLES | {"read_only_auditor", "district_manager"})
    conditions, params = [], {"limit": limit, "offset": offset}
    if current["role"] not in GLOBAL_RETURN_ROLES:
        scope = _scope_warehouses(db, current)
        conditions.append("warehouse_id = ANY(CAST(:warehouses AS uuid[]))")
        params["warehouses"] = [str(w) for w in scope]
        if current["role"] == "warehouse_staff":
            conditions.append(
                "customer_id IN (SELECT c.id FROM master_data.master_customer c "
                "JOIN platform.user_branch ub ON ub.branch_id=c.branch_id "
                "WHERE ub.user_id=:uid)"
            )
            params["uid"] = current["id"]
        else:
            conditions.append(
                "customer_id IN (SELECT c.id FROM master_data.master_customer c "
                "JOIN platform.user_territory ut ON ut.territory_id=c.territory_id "
                "WHERE ut.user_id=:uid)"
            )
            params["uid"] = current["id"]
    if customer_id is not None:
        conditions.append("customer_id = :customer_id")
        params["customer_id"] = customer_id
    if product_id is not None:
        conditions.append("product_id = :product_id")
        params["product_id"] = product_id
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(
            "SELECT * FROM sales.sales_return"
            + where
            + " ORDER BY return_date DESC, created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings()
    return [{**dict(r), "quantity": str(r["quantity"])} for r in rows]

@router.post("/{return_id}/settle")
def settle_return(
    return_id: UUID,
    payload: ReturnDecisionIn,
    request: Request,
    db: Db,
    current: CurrentUser,
):
    # Role check
    if not _role(current, APPROVE_ROLES):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    # Posting enabled gate
    if not app_config.POSTING_ENABLED:
        raise HTTPException(status_code=409, detail="Return settlement disabled while POSTING_ENABLED is false")
    # Lock return row
    ret = db.execute(
        text("SELECT * FROM sales.sales_return WHERE id = :id FOR UPDATE"),
        {"id": return_id},
    ).mappings().one_or_none()
    if ret is None:
        raise HTTPException(status_code=404, detail="Return not found")
    # State machine guard
    if ret["status"] != "quarantined" or ret["decided_at"] is not None or ret["restock_movement_id"] is not None or ret["credit_note_entry_id"] is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Return already settled or not quarantined (status={ret['status']})",
        )
    # Re-verify invoice quantities if invoice_id present
    if ret["invoice_id"] is not None:
        # Lock the invoice row so concurrent settlements against the same invoice serialize cleanly
        inv_lock = db.execute(
            text("SELECT 1 FROM sales.sales_invoice WHERE id = :id FOR UPDATE"),
            {"id": ret["invoice_id"]},
        ).scalar()
        if not inv_lock:
            raise HTTPException(409, "Invoice no longer exists")
        # Re-verify invoiced_qty from sales_invoice_line
        invoiced_qty_result = db.execute(
            text(
                "SELECT COALESCE(SUM(quantity), 0) FROM sales.sales_invoice_line WHERE invoice_id=:inv AND product_id=:pid"
            ),
            {"inv": ret["invoice_id"], "pid": ret["product_id"]},
        ).scalar()
        invoiced_qty = Decimal(str(invoiced_qty_result))
        # Query already_settled from sales_return WHERE invoice_id=:inv AND product_id=:pid AND id <> :rid AND status IN ('approved_restock', 'scrapped')
        already_settled_result = db.execute(
            text(
                "SELECT COALESCE(SUM(quantity), 0) FROM sales.sales_return WHERE invoice_id=:inv AND product_id=:pid AND id <> :rid AND status IN ('approved_restock', 'scrapped')"
            ),
            {"inv": ret["invoice_id"], "pid": ret["product_id"], "rid": return_id},
        ).scalar()
        already_settled = Decimal(str(already_settled_result))
        qty = Decimal(str(ret["quantity"]))
        if invoiced_qty <= Decimal("0") or already_settled + qty > invoiced_qty:
            raise HTTPException(409, "Return quantity exceeds invoiced quantity for this product")
    # Determine pricing
    unit_price = payload.unit_price
    vat_rate = payload.vat_rate
    if ret["invoice_id"] and unit_price is None:
        line = db.execute(
            text(
                "SELECT COALESCE(net_price, unit_price) AS unit_price, vat_rate FROM sales.sales_invoice_line "
                "WHERE invoice_id = :inv AND product_id = :pid LIMIT 1"
            ),
            {"inv": ret["invoice_id"], "pid": ret["product_id"]},
        ).mappings().one_or_none()
        if line:
            unit_price = Decimal(str(line["unit_price"]))
            if vat_rate is None:
                vat_rate = Decimal(str(line["vat_rate"]))
    if unit_price is None or vat_rate is None:
        prod = db.execute(
            text(
                "SELECT base_price, vat_rate FROM master_data.master_product WHERE id = :pid"
            ),
            {"pid": ret["product_id"]},
        ).mappings().one_or_none()
        if unit_price is None:
            unit_price = Decimal(str(prod["base_price"]))
        if vat_rate is None:
            vat_rate = Decimal(str(prod["vat_rate"]))
    # Override with payload if provided
    if payload.unit_price is not None:
        unit_price = payload.unit_price
    if payload.vat_rate is not None:
        vat_rate = payload.vat_rate
    # Accounting calculations (matches app.sales.calc VAT-inclusive pricing)
    CENT = Decimal("0.01")
    qty = Decimal(str(ret["quantity"]))
    unit_p = Decimal(str(unit_price)).quantize(CENT, rounding=ROUND_HALF_UP)
    vat_r = Decimal(str(vat_rate)).quantize(CENT, rounding=ROUND_HALF_UP)
    gross_credit = (qty * unit_p).quantize(CENT, rounding=ROUND_HALF_UP)
    vat_reversal = vat_amount_for(gross_credit, vat_r)
    net_credit = (gross_credit - vat_reversal).quantize(CENT, rounding=ROUND_HALF_UP)

    try:
        restock_movement_id = None
        credit_note_entry_id = None
        if payload.decision == "approved_restock":
            restock_movement_id, _ = inv_service.record_movement(
                db,
                warehouse_id=ret["warehouse_id"],
                product_id=ret["product_id"],
                batch_id=ret["batch_id"],
                movement_type="return",
                quantity=qty,
                unit_cost=None,
                source_type="sales_return",
                source_id=ret["id"],
                note=f"Return restock release {ret['id']}",
                actor_id=current["id"],
            )
        # Credit note
        if payload.issue_credit_note and gross_credit > Decimal("0"):
            credit_note_entry_id = finance_ar.record_entry(
                db,
                customer_id=ret["customer_id"],
                entry_type="credit_note",
                debit=Decimal("0.00"),
                credit=gross_credit,
                on_date=ret["return_date"],
                note=f"Return credit note {ret['id']} (net={net_credit}, vat={vat_reversal})",
                actor_id=current["id"],
                invoice_id=ret["invoice_id"],
            )
        # Update return
        db.execute(
            text(
                "UPDATE sales.sales_return SET status=:st, unit_price=:up, vat_rate=:vr, "
                "net_credit=:nc, vat_reversal=:vat, gross_credit=:gc, restock_movement_id=:mv, "
                "credit_note_entry_id=:ar, decided_by=:actor, decided_at=now(), decision_note=:note "
                "WHERE id=:id"
            ),
            {
                "st": payload.decision,
                "up": unit_price,
                "vr": vat_rate,
                "nc": net_credit,
                "vat": vat_reversal,
                "gc": gross_credit,
                "mv": restock_movement_id,
                "ar": credit_note_entry_id,
                "actor": current["id"],
                "note": payload.decision_note,
                "id": return_id,
            },
        )
        log_audit(
            db,
            current["id"],
            f"return_{payload.decision}",
            "sales_return",
            ret["id"],
            {"status": ret["status"]},
            {
                "status": payload.decision,
                "restock_movement_id": str(restock_movement_id) if restock_movement_id else None,
                "credit_note_entry_id": str(credit_note_entry_id) if credit_note_entry_id else None,
                "net_credit": str(net_credit),
                "vat_reversal": str(vat_reversal),
                "gross_credit": str(gross_credit),
            },
            ip_address=_host(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "id": str(ret["id"]),
        "status": payload.decision,
        "quantity": str(qty),
        "unit_price": str(unit_p),
        "vat_rate": str(vat_r),
        "net_credit": str(net_credit),
        "vat_reversal": str(vat_reversal),
        "gross_credit": str(gross_credit),
        "restock_movement_id": str(restock_movement_id) if restock_movement_id else None,
        "credit_note_entry_id": str(credit_note_entry_id) if credit_note_entry_id else None,
        "decided_by": current["id"],
    }
