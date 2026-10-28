"""Global search (P2.10): customers + products by name/code.

Customer visibility mirrors ``/master/customers``: only the owner is
unrestricted; every other role sees solely the territories granted to it, and
customers without a territory/branch are never offered. Products are a global
active catalogue, matching ``/master/products``.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.db import get_db
from app.text_search import like_pattern

router = APIRouter(prefix="/search", tags=["search"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]


def _territories(db, current):
    """Territory ids a non-owner may search; None means unrestricted."""
    if current["role"] == "owner":
        return None
    rows = db.execute(
        text("SELECT territory_id FROM platform.user_territory WHERE user_id=:uid"),
        {"uid": current["id"]},
    ).fetchall()
    return [r[0] for r in rows]


@router.get("")
def search(db: Db, current: CurrentUser, q: str = Query(min_length=1, max_length=100),
           limit: int = Query(20, ge=1, le=50)):
    if not current["is_active"]:
        raise HTTPException(403, "Search access denied")
    like = like_pattern(q)
    params = {"q": like, "limit": limit}

    clauses = [
        "c.is_active",
        "c.territory_id IS NOT NULL",
        "c.branch_id IS NOT NULL",
        "(c.code ILIKE :q OR c.name_ar ILIKE :q OR c.name_en ILIKE :q)",
    ]
    territories = _territories(db, current)
    if territories is not None:
        if not territories:
            customers = []
        else:
            clauses.append("c.territory_id = ANY(CAST(:territories AS uuid[]))")
            params["territories"] = [str(t) for t in territories]
    if territories is None or territories:
        customers = [dict(r) for r in db.execute(
            text("SELECT c.id, c.code, c.name_ar, c.name_en FROM master_data.master_customer c "
                 "WHERE " + " AND ".join(clauses) + " ORDER BY c.name_ar LIMIT :limit"),
            params,
        ).mappings()]

    products = [dict(r) for r in db.execute(
        text("""SELECT id, sku, name_ar, name_en FROM master_data.master_product
                WHERE is_active AND (sku ILIKE :q OR name_ar ILIKE :q OR name_en ILIKE :q)
                ORDER BY name_ar LIMIT :limit"""),
        {"q": like, "limit": limit},
    ).mappings()]
    return {"customers": customers, "products": products}
