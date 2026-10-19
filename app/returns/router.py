"""Sales returns API (V2 §2B.12): explicit return transactions."""
import ipaddress
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.inventory import service as inv_service

router = APIRouter(prefix="/returns", tags=["returns"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

MANAGE_ROLES = {"owner", "finance", "warehouse_staff", "sales_manager"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Returns access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@router.post("", status_code=201)
def create_return(payload: dict, request: Request, db: Db, current: CurrentUser):
    _role(current, MANAGE_ROLES)
    customer = payload.get("customer_id")
    product = payload.get("product_id")
    warehouse = payload.get("warehouse_id")
    batch = payload.get("batch_id")
    qty = payload.get("quantity")
    rdate = payload.get("return_date")
    reason = payload.get("reason")
    invoice = payload.get("invoice_id")
    if not customer or not product or not warehouse or qty is None or not rdate:
        raise HTTPException(422, "customer, product, warehouse, quantity, return_date required")
    try:
        q = Decimal(str(qty))
    except (ValueError, TypeError, InvalidOperation, ArithmeticError):
        raise HTTPException(422, "quantity must be numeric")
    if q <= 0:
        raise HTTPException(422, "quantity must be positive")
    for table, ident, label in (
        ("master_data.master_customer", customer, "customer"),
        ("master_data.master_product", product, "product"),
        ("master_data.master_warehouse", warehouse, "warehouse"),
    ):
        if not db.execute(text(f"SELECT 1 FROM {table} WHERE id=:id AND is_active"),
                          {"id": ident}).scalar():
            raise HTTPException(422, f"{label} not active")
    if batch is not None:
        br = db.execute(text("SELECT product_id, warehouse_id FROM inventory.batch_record WHERE id=:id FOR SHARE"),
                        {"id": batch}).mappings().one_or_none()
        if br is None or str(br["product_id"]) != str(product) or str(br["warehouse_id"]) != str(warehouse):
            raise HTTPException(422, "Batch does not match product and warehouse")
    if invoice is not None:
        inv = db.execute(text("SELECT 1 FROM sales.sales_invoice WHERE id=:id"),
                         {"id": invoice}).scalar()
        if not inv:
            raise HTTPException(422, "invoice not found")
    rid = db.execute(
        text("""INSERT INTO sales.sales_return
            (customer_id, product_id, warehouse_id, batch_id, quantity,
             return_date, reason, invoice_id, created_by)
            VALUES (:c, :p, :w, :b, :q, :rd, :reason, :inv, :actor)
            RETURNING id"""),
        {"c": customer, "p": product, "w": warehouse, "b": batch, "q": q,
         "rd": rdate, "reason": reason, "inv": invoice, "actor": current["id"]},
    ).scalar()
    # Increase warehouse stock via an explicit 'return' movement.
    inv_service.record_movement(db, actor_id=current["id"], warehouse_id=warehouse,
                               product_id=product, batch_id=batch,
                               movement_type="return", quantity=q,
                               note=reason, source_type="return", source_id=rid)
    log_audit(db, current["id"], "created", "sales_return", rid, None,
              {"customer": customer, "product": product, "warehouse": warehouse,
               "quantity": str(q), "return_date": rdate},
              ip_address=_host(request), user_agent=request.headers.get("user-agent"))
    db.commit()
    return {"id": str(rid), "customer_id": customer, "product_id": product,
            "warehouse_id": warehouse, "batch_id": batch, "quantity": str(q),
            "return_date": rdate, "reason": reason}


@router.get("")
def list_returns(db: Db, current: CurrentUser, customer_id: UUID | None = None,
                 product_id: UUID | None = None, limit: int = 50, offset: int = 0):
    if limit < 1 or limit > 200: raise HTTPException(422, 'limit 1..200')
    if offset < 0: raise HTTPException(422, 'offset >= 0')
    _role(current, MANAGE_ROLES | {"read_only_auditor", "district_manager"})
    conditions, params = [], {"limit": limit, "offset": offset}
    if customer_id is not None:
        conditions.append("customer_id = :customer_id")
        params["customer_id"] = customer_id
    if product_id is not None:
        conditions.append("product_id = :product_id")
        params["product_id"] = product_id
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text("SELECT * FROM sales.sales_return" + where +
             " ORDER BY return_date DESC, created_at DESC LIMIT :limit OFFSET :offset"),
        params,
    ).mappings()
    return [dict(r) for r in rows]
