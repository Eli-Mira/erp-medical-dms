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
    customers = db.execute(
        text("""SELECT id, code, name_ar, name_en FROM master_data.master_customer
                WHERE is_active AND (code ILIKE :q OR name_ar ILIKE :q OR name_en ILIKE :q)
                ORDER BY name_ar LIMIT :limit"""),
        {"q": like, "limit": limit},
    ).mappings()
    products = db.execute(
        text("""SELECT id, sku, name_ar, name_en FROM master_data.master_product
                WHERE is_active AND (sku ILIKE :q OR name_ar ILIKE :q OR name_en ILIKE :q)
                ORDER BY name_ar LIMIT :limit"""),
        {"q": like, "limit": limit},
    ).mappings()
    return {"customers": [dict(r) for r in customers],
            "products": [dict(r) for r in products]}
