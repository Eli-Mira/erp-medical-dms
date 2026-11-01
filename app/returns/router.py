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
from app.inventory.router import GLOBAL_WAREHOUSE_ROLES, _scope_warehouses
from app.returns.schemas import ReturnIn

router = APIRouter(prefix="/returns", tags=["returns"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

MANAGE_ROLES = {"owner", "finance", "warehouse_staff", "sales_manager"}


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
    scope = _scope_warehouses(db, current)
    if scope is not None and (
        warehouse not in scope
        or not db.execute(
            text(
                "SELECT 1 FROM master_data.master_customer c "
                "JOIN platform.user_territory ut ON ut.territory_id=c.territory_id "
                "WHERE c.id=:c AND ut.user_id=:u"
            ),
            {"c": customer, "u": current["id"]},
        ).scalar()
    ):
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
        inv = db.execute(
            text(
                "SELECT 1 FROM sales.sales_invoice WHERE id=:id AND customer_id=:c FOR SHARE"
            ),
            {"id": invoice, "c": customer},
        ).scalar()
        if not inv:
            raise HTTPException(422, "Invoice reference is not valid for this customer")
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
    if current["role"] not in GLOBAL_WAREHOUSE_ROLES:
        scope = _scope_warehouses(db, current)
        conditions.extend(
            [
                "warehouse_id = ANY(CAST(:warehouses AS uuid[]))",
                (
                    "customer_id IN (SELECT c.id FROM master_data.master_customer c "
                    "JOIN platform.user_territory ut ON ut.territory_id=c.territory_id "
                    "WHERE ut.user_id=:uid)"
                ),
            ]
        )
        params.update(warehouses=[str(w) for w in scope], uid=current["id"])
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
