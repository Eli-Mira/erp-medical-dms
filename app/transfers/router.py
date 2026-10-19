"""Warehouse-to-warehouse transfers (V2 §2B.3).

Transfers are inventory movements, never sales: they decrease the source
warehouse, increase the destination, preserve batch, create no debt/revenue/
territory sale. Two linked movements (transfer_out / transfer_in) share one
transfer reference id; the audit log records the operation.
"""
import ipaddress
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.inventory import service as inv_service

router = APIRouter(prefix="/transfers", tags=["transfers"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

MANAGE_ROLES = {"owner", "finance", "warehouse_staff"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Transfer access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def _scope(db, user):
    role = user["role"]
    if role in {"owner", "finance", "warehouse_staff", "read_only_auditor"}:
        return None
    rows = db.execute(
        text("SELECT w.id FROM platform.user_branch ub JOIN master_data.master_warehouse w "
             "ON w.branch_id = ub.branch_id WHERE ub.user_id=:uid AND w.is_active"),
        {"uid": user["id"]},
    ).fetchall()
    s = {r[0] for r in rows}
    if not s:
        raise HTTPException(403, "Transfer access denied")
    return s


def _warehouse_ok(db, wid):
    return db.execute(
        text("SELECT 1 FROM master_data.master_warehouse WHERE id=:id AND is_active"),
        {"id": wid},
    ).scalar()


@router.post("", status_code=201)
def create_transfer(payload: dict, request: Request, db: Db, current: CurrentUser):
    _role(current, MANAGE_ROLES)
    src = payload.get("source_warehouse_id")
    dst = payload.get("destination_warehouse_id")
    product = payload.get("product_id")
    batch = payload.get("batch_id")
    qty = payload.get("quantity")
    note = payload.get("note")
    if not src or not dst or not product or qty is None:
        raise HTTPException(422, "source, destination, product and quantity required")
    if src == dst:
        raise HTTPException(422, "source and destination must differ")
    try:
        q = Decimal(str(qty))
    except (ValueError, TypeError, InvalidOperation, ArithmeticError):
        raise HTTPException(422, "quantity must be numeric")
    if q <= 0:
        raise HTTPException(422, "quantity must be positive")
    scope = _scope(db, current)
    for wid in (src, dst):
        if scope is not None and wid not in scope:
            raise HTTPException(403, "Warehouse outside your scope")
        if not _warehouse_ok(db, wid):
            raise HTTPException(422, "Warehouse not active")
    if not db.execute(text("SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active"),
                      {"id": product}).scalar():
        raise HTTPException(422, "Product not active")
    dst_batch = None
    if batch is not None:
        br = db.execute(text("SELECT product_id, warehouse_id, batch_no, "
                             "manufacture_date, expiry_date FROM inventory.batch_record "
                             "WHERE id=:id FOR SHARE"),
                        {"id": batch}).mappings().one_or_none()
        if br is None or str(br["product_id"]) != str(product) or str(br["warehouse_id"]) != str(src):
            raise HTTPException(422, "Batch does not match product and source warehouse")
        dst_batch = db.execute(
            text("""INSERT INTO inventory.batch_record
                (product_id, warehouse_id, batch_no, manufacture_date, expiry_date)
                VALUES (:p, :w, :bn, :md, :ed)
                ON CONFLICT (product_id, warehouse_id, batch_no) DO NOTHING
                RETURNING id"""),
            {"p": product, "w": dst, "bn": br["batch_no"],
             "md": br["manufacture_date"], "ed": br["expiry_date"]},
        ).scalar()
        if dst_batch is None:
            dst_batch = db.execute(
                text("SELECT id FROM inventory.batch_record WHERE product_id=:p "
                     "AND warehouse_id=:w AND batch_no=:bn"),
                {"p": product, "w": dst, "bn": br["batch_no"]},
            ).scalar()
    transfer_id = uuid4()
    try:
        inv_service.record_movement(db, actor_id=current["id"], warehouse_id=src,
                                   product_id=product, batch_id=batch,
                                   movement_type="transfer_out", quantity=-q,
                                   note=note, source_type="transfer",
                                   source_id=transfer_id)
        inv_service.record_movement(db, actor_id=current["id"], warehouse_id=dst,
                                   product_id=product, batch_id=dst_batch,
                                   movement_type="transfer_in", quantity=q,
                                   note=note, source_type="transfer",
                                   source_id=transfer_id)
    except inv_service.InsufficientStock as exc:
        db.rollback()
        raise HTTPException(409, str(exc))
    log_audit(db, current["id"], "created", "stock_transfer", transfer_id, None,
              {"source": src, "destination": dst, "product": product,
               "quantity": str(q), "batch": batch},
              ip_address=_host(request), user_agent=request.headers.get("user-agent"))
    db.commit()
    return {"id": str(transfer_id), "source_warehouse_id": src,
            "destination_warehouse_id": dst, "product_id": product,
            "batch_id": batch, "quantity": str(q)}


@router.get("")
def list_transfers(db: Db, current: CurrentUser, limit: int = 50, offset: int = 0):
    if limit < 1 or limit > 200: raise HTTPException(422, 'limit 1..200')
    if offset < 0: raise HTTPException(422, 'offset >= 0')
    _role(current, MANAGE_ROLES | {"sales_manager", "district_manager",
                                   "read_only_auditor"})
    scope = _scope(db, current)
    conditions, params = [], {"limit": limit, "offset": offset}
    if scope is not None:
        conditions.append("m.warehouse_id = ANY(:whs)")
        params["whs"] = [str(w) for w in scope]
    where = (" AND " + " AND ".join(conditions)) if conditions else ""
    # One row per transfer reference: the transfer_out movement carries the
    # negative quantity; pair it with the matching transfer_in for completeness.
    rows = db.execute(
        text("""SELECT m.id, m.warehouse_id AS source_warehouse_id,
                       m.product_id, m.batch_id, (-m.quantity) AS quantity,
                       m.note, m.created_at, m.created_by
                FROM inventory.stock_movement m
                WHERE m.movement_type='transfer_out'""" + where +
             " ORDER BY m.created_at DESC LIMIT :limit OFFSET :offset"),
        params,
    ).mappings()
    return [dict(r) for r in rows]
