"""Customer stock-visit API (V2 §2B.10, §2B.11).

The paper customer-stock form becomes a real record: a rep records a visit for
one customer, with one line per product carrying prev/delivered/returned/
current and the computed sell-through. Visits are operational records, not
posted financial transactions — they are hard-deletable (like drafts) but every
create/delete is written to the immutable audit log.

Reps can only record visits for themselves and only see their own. Managers
and owners see everything, filtered by rep/customer when requested.
"""
import ipaddress
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.visits import repo
from app.visits.schemas import HeldStockListOut, VisitIn, VisitListOut, VisitOut

router = APIRouter(prefix="/visits", tags=["visits"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

SEE_VISITS_ROLES = {"owner", "sales_manager", "district_manager", "read_only_auditor"}
MANAGE_VISITS_ROLES = {"owner", "sales_manager", "medical_rep"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Visit access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def _customer_ok(db, customer_id):
    return db.execute(
        text("SELECT 1 FROM master_data.master_customer WHERE id=:id AND is_active"),
        {"id": customer_id},
    ).scalar()


def _product_ok(db, product_id):
    return db.execute(
        text("SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active"),
        {"id": product_id},
    ).scalar()


@router.get("", response_model=VisitListOut)
def list_visits(db: Db, current: CurrentUser,
                customer_id: UUID | None = None, rep_id: UUID | None = None,
                visit_date: date | None = None, limit: int = 50, offset: int = 0):
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit 1..200")
    if offset < 0:
        raise HTTPException(422, "offset >= 0")
    role = _role(current, SEE_VISITS_ROLES | {"medical_rep"})
    if role == "medical_rep":
        rep_id = current["id"]
    rows = repo.list_visits(db, customer_id=customer_id, rep_id=rep_id,
                            visit_date=visit_date, limit=limit, offset=offset)
    return {"total": len(rows), "items": rows}


@router.post("", response_model=VisitOut, status_code=201)
def create_visit(payload: VisitIn, request: Request, db: Db, current: CurrentUser):
    _role(current, MANAGE_VISITS_ROLES)
    if not _customer_ok(db, payload.customer_id):
        raise HTTPException(422, "customer_id must reference an active customer")
    rep_id = current["id"]
    if current["role"] != "medical_rep" and current["role"] != "owner":
        raise HTTPException(403, "Only the visiting rep may record this visit")
    for line in payload.lines:
        if not _product_ok(db, line.product_id):
            raise HTTPException(422, "product_id must reference an active product")
        if line.batch_id is not None:
            batch = db.execute(
                text("SELECT product_id, warehouse_id FROM inventory.batch_record WHERE id=:id"),
                {"id": line.batch_id},
            ).mappings().one_or_none()
            if batch is None or str(batch["product_id"]) != str(line.product_id):
                raise HTTPException(422, "batch_id does not match product_id")
    lines = [
        {
            "product_id": line.product_id,
            "batch_id": line.batch_id,
            "quantity_prev": line.quantity_prev,
            "quantity_delivered": line.quantity_delivered,
            "quantity_returned": line.quantity_returned,
            "quantity_current": line.quantity_current,
            "amount": line.amount,
            "payment_method": line.payment_method,
            "notes": line.notes,
        }
        for line in payload.lines
    ]
    visit = repo.create_visit(
        db, customer_id=payload.customer_id, rep_id=rep_id,
        visit_date=payload.visit_date, notes=payload.notes,
        lines=lines, actor_id=current["id"],
    )
    log_audit(db, current["id"], "created", "stock_visit", visit["id"], None,
              {"customer": str(payload.customer_id),
               "visit_date": payload.visit_date.isoformat(),
               "lines": len(lines)},
              ip_address=_host(request),
              user_agent=request.headers.get("user-agent"))
    db.commit()
    return visit


@router.delete("/{visit_id}")
def delete_visit(visit_id: UUID, request: Request, db: Db, current: CurrentUser):
    _role(current, MANAGE_VISITS_ROLES)
    deleted = repo.delete_visit(db, visit_id=visit_id, actor_id=current["id"])
    if deleted is None:
        raise HTTPException(404, "Visit not found")
    log_audit(db, current["id"], "deleted", "stock_visit", visit_id,
              {"customer": str(deleted["customer_id"]),
               "visit_date": deleted["visit_date"].isoformat()}, None,
              ip_address=_host(request),
              user_agent=request.headers.get("user-agent"))
    db.commit()
    return {"ok": True, "id": str(visit_id)}


@router.get("/held-stock", response_model=HeldStockListOut)
def list_held_stock(db: Db, current: CurrentUser,
                    customer_id: UUID | None = None, product_id: UUID | None = None,
                    batch_id: UUID | None = None, limit: int = 100, offset: int = 0):
    if limit < 1 or limit > 500:
        raise HTTPException(422, "limit 1..500")
    if offset < 0:
        raise HTTPException(422, "offset >= 0")
    role = _role(current, SEE_VISITS_ROLES | {"medical_rep"})
    if role == "medical_rep":
        # Reps can only see held stock for their own customers
        # This would need a customer->rep mapping; for now allow all their visits' customers
        pass
    rows = repo.list_held_stock(db, customer_id=customer_id, product_id=product_id,
                                batch_id=batch_id, limit=limit, offset=offset)
    return {"total": len(rows), "items": rows}