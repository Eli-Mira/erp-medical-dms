"""Sales targets API (V2 §2B.13): management sets, reps see their own.

Owner decision 2026-10-19: rep + optional product + month, target in units.
Actuals are computed from posted invoice lines only — while posting is off
they read as null, never fabricated.
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
from app.sales import target_repo
from app.sales.schemas import TargetIn, TargetOut

router = APIRouter(prefix="/targets", tags=["targets"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

SEE_TARGETS_ROLES = {
    "owner",
    "finance",
    "sales_manager",
    "district_manager",
    "read_only_auditor",
}
MANAGE_TARGETS_ROLES = {"owner", "sales_manager"}


def _role(user, allowed):
    role = user["role"]
    if (
        not user["is_active"]
        or role not in allowed
        or (role == "owner" and not user["is_owner"])
    ):
        raise HTTPException(403, "Targets access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@router.get("")
def list_targets(
    db: Db,
    current: CurrentUser,
    rep_id: UUID | None = None,
    product_id: UUID | None = None,
    month: date | None = None,
    territory_id: UUID | None = None,
) -> list[TargetOut]:
    role = _role(current, SEE_TARGETS_ROLES | {"medical_rep"})
    if role == "medical_rep":
        rep_id = current["id"]
    return [
        TargetOut.model_validate(row)
        for row in target_repo.list_targets(
            db,
            rep_id=rep_id,
            product_id=product_id,
            month=month,
            territory_id=territory_id,
        )
    ]


@router.post("", response_model=TargetOut, status_code=201)
def upsert_target(
    payload: TargetIn, request: Request, db: Db, current: CurrentUser
) -> TargetOut:
    _role(current, MANAGE_TARGETS_ROLES)
    period_month = payload.period_month.replace(day=1)
    if payload.rep_id is not None:
        valid = db.execute(
            text(
                "SELECT 1 FROM platform.platform_user WHERE id=:id AND is_active "
                "AND role='medical_rep'"
            ),
            {"id": payload.rep_id},
        ).scalar()
        if not valid:
            raise HTTPException(422, "rep_id must reference an active medical rep")
    else:
        valid = db.execute(
            text("SELECT 1 FROM master_data.master_territory WHERE id=:id"),
            {"id": payload.territory_id},
        ).scalar()
        if not valid:
            raise HTTPException(
                422, "territory_id must reference an existing territory"
            )
    if payload.product_id is not None:
        product = db.execute(
            text("SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active"),
            {"id": payload.product_id},
        ).scalar()
        if not product:
            raise HTTPException(422, "product_id must reference an active product")
    old = target_repo.existing_target(
        db,
        payload.rep_id,
        payload.product_id,
        period_month,
        territory_id=payload.territory_id,
    )
    target_id = target_repo.upsert(
        db,
        actor_id=current["id"],
        rep_id=payload.rep_id,
        territory_id=payload.territory_id,
        product_id=payload.product_id,
        period_month=period_month,
        target_quantity=payload.target_quantity,
    )
    rows = target_repo.list_targets(
        db,
        rep_id=payload.rep_id,
        territory_id=payload.territory_id,
        product_id=payload.product_id,
        month=period_month,
    )
    result = TargetOut.model_validate(
        next(row for row in rows if row["id"] == target_id)
    )
    log_audit(
        db,
        current["id"],
        "upserted",
        "sales_target",
        target_id,
        old and {"target_quantity": str(old["target_quantity"])},
        {"target_quantity": str(payload.target_quantity)},
        ip_address=_host(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return result
