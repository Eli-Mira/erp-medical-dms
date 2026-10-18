"""Marketing spend + objective/KPI (V2 §2B.16–2B.18)."""
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

router = APIRouter(prefix="/marketing", tags=["marketing"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

READ_ROLES = {"owner", "finance", "sales_manager", "district_manager",
              "medical_rep", "read_only_auditor"}
WRITE_ROLES = {"owner", "finance", "sales_manager"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Marketing access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@router.post("/spend", status_code=201)
def create_spend(payload: dict, request: Request, db: Db, current: CurrentUser):
    _role(current, WRITE_ROLES)
    kol = payload.get("kol_id")
    territory = payload.get("territory_id")
    sdate = payload.get("spend_date")
    amount = payload.get("amount")
    activity = payload.get("activity_type")
    notes = payload.get("notes")
    products = payload.get("product_ids") or []
    if not sdate or amount is None or not activity:
        raise HTTPException(422, "spend_date, amount, activity_type required")
    try:
        amt = Decimal(str(amount))
    except (ValueError, TypeError, InvalidOperation, ArithmeticError):
        raise HTTPException(422, "amount must be numeric")
    if amt < 0:
        raise HTTPException(422, "amount must be non-negative")
    if kol is not None and not db.execute(
            text("SELECT 1 FROM marketing.marketing_kol WHERE id=:id AND is_active"),
            {"id": kol}).scalar():
        raise HTTPException(422, "kol not active")
    if territory is not None and not db.execute(
            text("SELECT 1 FROM master_data.master_territory WHERE id=:id"),
            {"id": territory}).scalar():
        raise HTTPException(422, "territory not found")
    for pid in products:
        if not db.execute(text("SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active"),
                          {"id": pid}).scalar():
            raise HTTPException(422, f"product {pid} not active")
    sid = db.execute(
        text("""INSERT INTO marketing.marketing_spend
            (kol_id, territory_id, spend_date, amount, activity_type, notes, created_by)
            VALUES (:kol, :terr, :sd, :amt, :act, :notes, :actor)
            RETURNING id"""),
        {"kol": kol, "terr": territory, "sd": sdate, "amt": amt,
         "act": activity, "notes": notes, "actor": current["id"]},
    ).scalar()
    for pid in products:
        db.execute(text("INSERT INTO marketing.marketing_spend_product (spend_id, product_id) "
                        "VALUES (:s, :p) ON CONFLICT DO NOTHING"),
                   {"s": sid, "p": pid})
    log_audit(db, current["id"], "created", "marketing_spend", sid, None,
              {"kol": kol, "territory": territory, "amount": str(amt),
               "activity": activity, "products": products},
              ip_address=_host(request), user_agent=request.headers.get("user-agent"))
    db.commit()
    return {"id": str(sid), "kol_id": kol, "territory_id": territory,
            "spend_date": sdate, "amount": str(amt), "activity_type": activity,
            "notes": notes, "product_ids": products}


@router.get("/spend")
def list_spend(db: Db, current: CurrentUser, kol_id: UUID | None = None,
               territory_id: UUID | None = None, limit: int = 50, offset: int = 0):
    _role(current, READ_ROLES)
    conditions, params = [], {"limit": limit, "offset": offset}
    if kol_id is not None:
        conditions.append("kol_id = :kol_id")
        params["kol_id"] = kol_id
    if territory_id is not None:
        conditions.append("territory_id = :territory_id")
        params["territory_id"] = territory_id
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text("SELECT s.*, (SELECT array_agg(product_id) FROM marketing.marketing_spend_product "
             "WHERE spend_id=s.id) AS product_ids FROM marketing.marketing_spend s" + where +
             " ORDER BY s.spend_date DESC LIMIT :limit OFFSET :offset"),
        params,
    ).mappings()
    return [dict(r) for r in rows]


@router.post("/objectives", status_code=201)
def create_objective(payload: dict, request: Request, db: Db, current: CurrentUser):
    _role(current, WRITE_ROLES)
    spend = payload.get("spend_id")
    kol = payload.get("kol_id")
    product = payload.get("product_id")
    territory = payload.get("territory_id")
    objective = payload.get("objective")
    if not objective:
        raise HTTPException(422, "objective required")
    if spend is not None and not db.execute(
            text("SELECT 1 FROM marketing.marketing_spend WHERE id=:id"), {"id": spend}).scalar():
        raise HTTPException(422, "spend not found")
    if kol is not None and not db.execute(
            text("SELECT 1 FROM marketing.marketing_kol WHERE id=:id AND is_active"),
            {"id": kol}).scalar():
        raise HTTPException(422, "kol not active")
    if product is not None and not db.execute(
            text("SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active"),
            {"id": product}).scalar():
        raise HTTPException(422, "product not active")
    if territory is not None and not db.execute(
            text("SELECT 1 FROM master_data.master_territory WHERE id=:id"),
            {"id": territory}).scalar():
        raise HTTPException(422, "territory not found")
    oid = db.execute(
        text("""INSERT INTO marketing.marketing_objective
            (spend_id, kol_id, product_id, territory_id, objective,
             expected_kpi, actual_result, followup_notes, created_by)
            VALUES (:spend, :kol, :product, :terr, :obj, :kpi, :actual, :fu, :actor)
            RETURNING id"""),
        {"spend": spend, "kol": kol, "product": product, "terr": territory,
         "obj": objective, "kpi": payload.get("expected_kpi"),
         "actual": payload.get("actual_result"),
         "fu": payload.get("followup_notes"), "actor": current["id"]},
    ).scalar()
    log_audit(db, current["id"], "created", "marketing_objective", oid, None,
              {"objective": objective, "spend": spend, "kol": kol, "product": product},
              ip_address=_host(request), user_agent=request.headers.get("user-agent"))
    db.commit()
    return {"id": str(oid), "spend_id": spend, "kol_id": kol,
            "product_id": product, "territory_id": territory,
            "objective": objective,
            "expected_kpi": payload.get("expected_kpi"),
            "actual_result": payload.get("actual_result"),
            "followup_notes": payload.get("followup_notes")}


@router.get("/objectives")
def list_objectives(db: Db, current: CurrentUser, kol_id: UUID | None = None,
                    product_id: UUID | None = None, limit: int = 50, offset: int = 0):
    _role(current, READ_ROLES)
    conditions, params = [], {"limit": limit, "offset": offset}
    if kol_id is not None:
        conditions.append("kol_id = :kol_id")
        params["kol_id"] = kol_id
    if product_id is not None:
        conditions.append("product_id = :product_id")
        params["product_id"] = product_id
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text("SELECT * FROM marketing.marketing_objective" + where +
             " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
        params,
    ).mappings()
    return [dict(r) for r in rows]
