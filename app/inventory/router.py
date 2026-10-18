"""Inventory API: stock ledger and balances.

Movement types 'sale', 'return' and 'transfer_*' are reserved for the invoice
posting and transfer flows; they are not accepted here while posting is
disabled.
"""
import ipaddress
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.inventory import service
from app.inventory.schemas import (
    BalanceOut,
    BatchOut,
    CoverOut,
    MovementIn,
    MovementOut,
    MovementResult,
)
from app.settings import service as settings_service

router = APIRouter(prefix="/inventory", tags=["inventory"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

# Explicit user_branch grants cover owned warehouses, never fulfillment routes.
READ_ROLES = {"owner", "finance", "warehouse_staff", "read_only_auditor",
              "sales_manager", "district_manager"}
WRITE_ROLES = {"owner", "finance", "warehouse_staff"}

# Roles granted access to ALL warehouses (no per-warehouse filtering).
GLOBAL_WAREHOUSE_ROLES = {"owner", "finance", "warehouse_staff", "read_only_auditor"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Inventory access denied")
    return role


def _scope_warehouses(db, user):
    """Active warehouses owned by explicit branch grants; None means global."""
    role = user["role"]
    if role in GLOBAL_WAREHOUSE_ROLES:
        return None
    if role not in READ_ROLES:
        raise HTTPException(403, "Inventory access denied")
    rows = db.execute(
        text("SELECT w.id FROM platform.user_branch ub "
             "JOIN master_data.master_warehouse w ON w.branch_id = ub.branch_id "
             "WHERE ub.user_id = :uid AND w.is_active"),
        {"uid": user["id"]},
    ).fetchall()
    warehouses = {r[0] for r in rows}
    if not warehouses:
        raise HTTPException(403, "Inventory access denied")
    return warehouses


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@router.get("/stock")
def list_stock(db: Db, current: CurrentUser, warehouse_id: UUID | None = None,
               product_id: UUID | None = None, batch_id: UUID | None = None) -> list[BalanceOut]:
    _role(current, READ_ROLES)
    scope = _scope_warehouses(db, current)
    if scope is not None and warehouse_id is not None and warehouse_id not in scope:
        raise HTTPException(404, "Warehouse not found")
    warehouse_ids = list(scope) if scope is not None else None
    return [BalanceOut.model_validate(row)
            for row in service.list_balances(db, warehouse_id=warehouse_id,
                                             product_id=product_id, batch_id=batch_id,
                                             warehouse_ids=warehouse_ids)]


@router.get("/batches")
def list_batches(db: Db, current: CurrentUser, warehouse_id: UUID | None = None,
                 product_id: UUID | None = None) -> list[BatchOut]:
    _role(current, READ_ROLES)
    scope = _scope_warehouses(db, current)
    if scope is not None and warehouse_id is not None and warehouse_id not in scope:
        raise HTTPException(404, "Warehouse not found")
    warehouse_ids = list(scope) if scope is not None else None
    return [BatchOut.model_validate(row)
            for row in service.list_batches(db, warehouse_id=warehouse_id,
                                            product_id=product_id,
                                            warehouse_ids=warehouse_ids)]


@router.get("/cover")
def cover_report(db: Db, current: CurrentUser, warehouse_id: UUID | None = None,
                 product_id: UUID | None = None) -> list[CoverOut]:
    _role(current, READ_ROLES)
    scope = _scope_warehouses(db, current)
    if scope is not None and warehouse_id is not None and warehouse_id not in scope:
        raise HTTPException(404, "Warehouse not found")
    policy = settings_service.read_policy(db)
    warehouse_ids = list(scope) if scope is not None else None
    return [CoverOut.model_validate(row)
            for row in service.cover_report(
                db, policy["stock_cover_window_days"],
                policy["overstock_threshold_days"],
                warehouse_id=warehouse_id, product_id=product_id,
                warehouse_ids=warehouse_ids)]


@router.get("/movements")
def list_movements(db: Db, current: CurrentUser, warehouse_id: UUID | None = None,
                   product_id: UUID | None = None, batch_id: UUID | None = None,
                   movement_type: str | None = None, date_from: datetime | None = None,
                   date_to: datetime | None = None) -> list[MovementOut]:
    _role(current, READ_ROLES)
    scope = _scope_warehouses(db, current)
    warehouse_ids = list(scope) if scope is not None else None
    if scope is not None and warehouse_id is not None and warehouse_id not in scope:
        raise HTTPException(404, "Warehouse not found")
    rows = service.list_movements(db, warehouse_id=warehouse_id, product_id=product_id,
                                  batch_id=batch_id, movement_type=movement_type,
                                  date_from=date_from, date_to=date_to,
                                  warehouse_ids=warehouse_ids,
                                  scoped_user_id=current["id"] if scope is not None else None)
    return [MovementOut.model_validate(row) for row in rows]


@router.post("/movements", status_code=201)
def record_movement(payload: MovementIn, request: Request, db: Db, current: CurrentUser) -> MovementResult:
    _role(current, WRITE_ROLES)
    scope = _scope_warehouses(db, current)
    if scope is not None and payload.warehouse_id not in scope:
        raise HTTPException(404, "Warehouse not found")
    if payload.movement_type == "adjustment":
        reason = db.execute(text(
            "SELECT 1 FROM audit.reason_code WHERE id=:id AND is_active AND category='adjustment' FOR SHARE"),
            {"id": payload.reason_id}).scalar()
        if not reason:
            raise HTTPException(422, "An active adjustment reason code is required")
    # Table names are fixed literals here, not request input.
    for table, identifier in (("master_data.master_product", payload.product_id),
                              ("master_data.master_warehouse", payload.warehouse_id)):
        active = db.execute(text(f"SELECT 1 FROM {table} WHERE id=:id AND is_active FOR SHARE"),
                            {"id": identifier}).scalar()
        if not active:
            raise HTTPException(422, "Product and warehouse must be active")
    if payload.batch_id is not None:
        batch = db.execute(text(
            "SELECT product_id, warehouse_id FROM inventory.batch_record WHERE id=:id FOR SHARE"),
            {"id": payload.batch_id}).mappings().one_or_none()
        if batch is None or batch["product_id"] != payload.product_id or batch["warehouse_id"] != payload.warehouse_id:
            raise HTTPException(422, "Batch does not match product and warehouse")
    try:
        movement_id, balance = service.record_movement(
            db, actor_id=current["id"], warehouse_id=payload.warehouse_id,
            product_id=payload.product_id, batch_id=payload.batch_id,
            movement_type=payload.movement_type, quantity=payload.quantity,
            unit_cost=payload.unit_cost, note=payload.note)
        movement = MovementOut.model_validate(service.fetch_movement(db, movement_id))
        log_audit(db, current["id"], "created", "stock_movement", movement_id, None,
                  movement.model_dump(mode="json"), _host(request),
                  request.headers.get("user-agent", "")[:1000])
        db.commit()
        return MovementResult(movement=movement, balance_quantity=balance)
    except service.InsufficientStock as error:
        db.rollback()
        raise HTTPException(409, str(error)) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(422, "Movement violates a database reference or value constraint") from error
    except Exception:
        db.rollback()
        raise
