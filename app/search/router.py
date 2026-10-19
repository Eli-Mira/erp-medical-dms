"""Global search (P2.10): customers + products by name/code."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.db import get_db

router = APIRouter(prefix="/search", tags=["search"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]


@router.get("")
def search(db: Db, current: CurrentUser, q: str = Query(min_length=1, max_length=100),
           limit: int = Query(20, ge=1, le=50)):
    if not current["is_active"]:
        raise HTTPException(403, "Search access denied")
    like = f"%{q}%"
    # Territory scoping mirrors master customers: non-global callers only see
    # customers in their granted territories.
    role = current["role"]
    global_roles = {"owner", "finance", "read_only_auditor", "admin"}
    territory_clause = ""
    params = {"q": like, "limit": limit}
    if role not in global_roles:
        rows = db.execute(
            text("SELECT territory_id FROM platform.user_territory WHERE user_id=:uid"),
            {"uid": current["id"]},
        ).fetchall()
        terrs = [r[0] for r in rows]
        if not terrs:
            return {"customers": [], "products": [dict(r) for r in db.execute(
                text("""SELECT id, sku, name_ar, name_en FROM master_data.master_product
                        WHERE is_active AND (sku ILIKE :q OR name_ar ILIKE :q OR name_en ILIKE :q)
                        ORDER BY name_ar LIMIT :limit"""),
                {"q": like, "limit": limit},
            ).mappings()]}
        territory_clause = " AND c.territory_id = ANY(:territories)"
        params["territories"] = terrs
    customers = db.execute(
        text("""SELECT c.id, c.code, c.name_ar, c.name_en
                FROM master_data.master_customer c
                WHERE c.is_active
                  AND (c.code ILIKE :q OR c.name_ar ILIKE :q OR c.name_en ILIKE :q)"""
             + territory_clause +
             " ORDER BY c.name_ar LIMIT :limit"),
        params,
    ).mappings()
    products = db.execute(
        text("""SELECT id, sku, name_ar, name_en FROM master_data.master_product
                WHERE is_active AND (sku ILIKE :q OR name_ar ILIKE :q OR name_en ILIKE :q)
                ORDER BY name_ar LIMIT :limit"""),
        {"q": like, "limit": limit},
    ).mappings()
    return {"customers": [dict(r) for r in customers],
            "products": [dict(r) for r in products]}
