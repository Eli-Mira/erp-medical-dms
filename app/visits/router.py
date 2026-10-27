"""Authorized stock visits; reported money never posts a collection or ledger."""

import ipaddress
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.visits import repo
from app.visits.schemas import HeldStockListOut, VisitIn, VisitListOut, VisitOut

router = APIRouter(prefix="/visits", tags=["visits"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
READ_ROLES = {
    "owner",
    "sales_manager",
    "district_manager",
    "read_only_auditor",
    "medical_rep",
}
WRITE_ROLES = {"owner", "medical_rep"}


def _role(user, allowed):
    role = user["role"]
    if (
        not user["is_active"]
        or role not in allowed
        or (role == "owner" and not user["is_owner"])
    ):
        raise HTTPException(403, "Visit access denied")
    return role


def _scope_user(user):
    return user["id"] if user["role"] in {"medical_rep", "district_manager"} else None


def _host(request):
    try:
        return (
            str(ipaddress.ip_address(request.client.host)) if request.client else None
        )
    except ValueError:
        return None


def _lock_customer(db, customer_id, current, *, active=False):
    params = {"id": customer_id}
    scope = ""
    if _scope_user(current) is not None:
        scope = " AND EXISTS (SELECT 1 FROM platform.user_territory ut WHERE ut.territory_id=c.territory_id AND ut.user_id=:uid)"
        params["uid"] = current["id"]
    # Serialize visits and their held-stock projection using the existing customer row.
    row = (
        db.execute(
            text(
                "SELECT c.id, c.is_active FROM master_data.master_customer c WHERE c.id=:id"
                + scope
                + " FOR UPDATE OF c"
            ),
            params,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Customer not found")
    if active and not row["is_active"]:
        raise HTTPException(422, "Customer must be active")


@router.get("", response_model=VisitListOut)
def list_visits(
    db: Db,
    current: CurrentUser,
    customer_id: UUID | None = None,
    rep_id: UUID | None = None,
    visit_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
):
    role = _role(current, READ_ROLES)
    if not 1 <= limit <= 200 or offset < 0:
        raise HTTPException(422, "limit 1..200 and offset >= 0")
    if role == "medical_rep":
        rep_id = current["id"]
    return repo.list_visits(
        db,
        customer_id=customer_id,
        rep_id=rep_id,
        visit_date=visit_date,
        scope_user_id=_scope_user(current),
        limit=limit,
        offset=offset,
    )


@router.get("/held-stock", response_model=HeldStockListOut)
def list_held_stock(
    db: Db,
    current: CurrentUser,
    customer_id: UUID | None = None,
    product_id: UUID | None = None,
    batch_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
):
    _role(current, READ_ROLES)
    if not 1 <= limit <= 500 or offset < 0:
        raise HTTPException(422, "limit 1..500 and offset >= 0")
    return repo.list_held_stock(
        db,
        customer_id=customer_id,
        product_id=product_id,
        batch_id=batch_id,
        scope_user_id=_scope_user(current),
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=VisitOut, status_code=201)
def create_visit(payload: VisitIn, request: Request, db: Db, current: CurrentUser):
    _role(current, WRITE_ROLES)
    try:
        _lock_customer(db, payload.customer_id, current, active=True)
        for line in payload.lines:
            product = db.execute(
                text(
                    "SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active FOR SHARE"
                ),
                {"id": line.product_id},
            ).scalar()
            if not product:
                raise HTTPException(422, "Product must be active")
            if line.batch_id is not None:
                batch = db.execute(
                    text(
                        "SELECT product_id FROM inventory.batch_record WHERE id=:id FOR SHARE"
                    ),
                    {"id": line.batch_id},
                ).scalar()
                if batch != line.product_id:
                    raise HTTPException(422, "Batch does not match product")
        visit = VisitOut.model_validate(
            repo.create_visit(
                db,
                customer_id=payload.customer_id,
                rep_id=current["id"],
                visit_date=payload.visit_date,
                notes=payload.notes,
                lines=[line.model_dump() for line in payload.lines],
                actor_id=current["id"],
            )
        )
        log_audit(
            db,
            current["id"],
            "created",
            "stock_visit",
            visit.id,
            None,
            visit.model_dump(mode="json"),
            ip_address=_host(request),
            user_agent=request.headers.get("user-agent", "")[:1000],
        )
        db.commit()
        return visit
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            422, "Visit violates a reference or quantity constraint"
        ) from error
    except Exception:
        db.rollback()
        raise


@router.delete("/{visit_id}")
def delete_visit(visit_id: UUID, request: Request, db: Db, current: CurrentUser):
    role = _role(current, WRITE_ROLES)
    try:
        visit = repo.fetch_visit(db, visit_id)
        if visit is None or (
            role == "medical_rep" and visit["rep_id"] != current["id"]
        ):
            raise HTTPException(404, "Visit not found")
        _lock_customer(db, visit["customer_id"], current)
        visit = repo.fetch_visit(db, visit_id)
        if visit is None:
            raise HTTPException(404, "Visit not found")
        old = VisitOut.model_validate(visit).model_dump(mode="json")
        repo.delete_visit(db, visit=visit)
        log_audit(
            db,
            current["id"],
            "deleted",
            "stock_visit",
            visit_id,
            old,
            None,
            ip_address=_host(request),
            user_agent=request.headers.get("user-agent", "")[:1000],
        )
        db.commit()
        return {"ok": True, "id": str(visit_id)}
    except Exception:
        db.rollback()
        raise
