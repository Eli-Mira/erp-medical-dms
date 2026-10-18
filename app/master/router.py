"""Read-only master-data lookups for the invoice screen.

Scope rules mirror the invoice API exactly so the UI can only offer references
that invoice creation would accept:

- customers  : active, territory-assigned; non-owner callers limited to their
               ``platform.user_territory`` grants (same rule as invoice create).
- warehouses : non-global callers limited to warehouses owned through their
               ``platform.user_branch`` grants; an optional ``branch_id`` keeps
               only warehouses that own that branch or are routed to it via
               ``inventory.branch_warehouse``.
- branches   : non-global callers limited to their ``platform.user_branch`` grants.
- products   : active catalog rows (invoice create only checks ``is_active``).

Reads only. No writes, no commits, no schema changes.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.db import get_db
from app.master.schemas import BranchOut, CustomerOut, ProductOut, WarehouseOut

router = APIRouter(prefix="/master", tags=["master-data"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

# Same role set that may read the invoice pipeline.
READ_ROLES = {
    "owner",
    "finance",
    "sales_manager",
    "district_manager",
    "medical_rep",
    "read_only_auditor",
}
# Roles that see every branch/warehouse without a per-row grant.
GLOBAL_WAREHOUSE_ROLES = {"owner", "finance", "warehouse_staff", "read_only_auditor"}
GLOBAL_BRANCH_ROLES = {"owner", "finance", "read_only_auditor"}

PRODUCT_LIMIT_DEFAULT = 100
PRODUCT_LIMIT_MAX = 500


def _role(user):
    role = user["role"]
    if (
        not user["is_active"]
        or role not in READ_ROLES
        or (role == "owner" and not user["is_owner"])
    ):
        raise HTTPException(403, "Master data access denied")
    return role


def _territories(db, user):
    """Territory ids a non-owner may reference; None means unrestricted."""
    if _role(user) == "owner":
        return None
    rows = db.execute(
        text("SELECT territory_id FROM platform.user_territory WHERE user_id=:uid"),
        {"uid": user["id"]},
    ).fetchall()
    return {r[0] for r in rows}


def _branches(db, user):
    """Branch ids a non-global caller may reference; None means unrestricted."""
    if user["role"] in GLOBAL_BRANCH_ROLES:
        return None
    rows = db.execute(
        text("SELECT branch_id FROM platform.user_branch WHERE user_id=:uid"),
        {"uid": user["id"]},
    ).fetchall()
    return {r[0] for r in rows}


def _warehouses(db, user):
    """Active warehouse ids a non-global caller may reference; None is global."""
    if user["role"] in GLOBAL_WAREHOUSE_ROLES:
        return None
    rows = db.execute(
        text(
            "SELECT w.id FROM platform.user_branch ub "
            "JOIN master_data.master_warehouse w ON w.branch_id = ub.branch_id "
            "WHERE ub.user_id = :uid AND w.is_active"
        ),
        {"uid": user["id"]},
    ).fetchall()
    return {r[0] for r in rows}


@router.get("/branches")
def list_branches(db: Db, current: CurrentUser) -> list[BranchOut]:
    _role(current)
    scope = _branches(db, current)
    if scope is not None and not scope:
        return []
    where, params = "", {}
    if scope is not None:
        where = "WHERE id = ANY(CAST(:branches AS uuid[]))"
        params["branches"] = [str(b) for b in scope]
    rows = db.execute(
        text(
            "SELECT id, code, name_ar, name_en FROM master_data.master_branch "
            + where
            + " ORDER BY name_ar"
        ),
        params,
    ).mappings()
    return [BranchOut.model_validate(dict(row)) for row in rows]


@router.get("/warehouses")
def list_warehouses(
    db: Db, current: CurrentUser, branch_id: UUID | None = None
) -> list[WarehouseOut]:
    _role(current)
    scope = _warehouses(db, current)
    if scope is not None and not scope:
        return []
    clauses = ["w.is_active"]
    params: dict = {}
    if scope is not None:
        clauses.append("w.id = ANY(CAST(:warehouses AS uuid[]))")
        params["warehouses"] = [str(w) for w in scope]
    if branch_id is not None:
        clauses.append(
            "(w.branch_id = :branch_id OR EXISTS ("
            "SELECT 1 FROM inventory.branch_warehouse bw "
            "WHERE bw.branch_id = :branch_id AND bw.warehouse_id = w.id))"
        )
        params["branch_id"] = branch_id
    rows = db.execute(
        text(
            "SELECT w.id, w.branch_id, w.code, w.name_ar, w.name_en, w.is_active "
            "FROM master_data.master_warehouse w WHERE "
            + " AND ".join(clauses)
            + " ORDER BY w.name_ar"
        ),
        params,
    ).mappings()
    return [WarehouseOut.model_validate(dict(row)) for row in rows]


@router.get("/customers")
def list_customers(
    db: Db, current: CurrentUser, branch_id: UUID | None = None
) -> list[CustomerOut]:
    territories = _territories(db, current)
    if territories is not None and not territories:
        return []
    # Invoice create requires an active, territory-assigned customer whose
    # branch matches the invoice branch; a null branch can never satisfy that,
    # so it must never be offered here either.
    clauses = ["c.is_active", "c.territory_id IS NOT NULL", "c.branch_id IS NOT NULL"]
    params: dict = {}
    if territories is not None:
        clauses.append("c.territory_id = ANY(CAST(:territories AS uuid[]))")
        params["territories"] = [str(t) for t in territories]
    if branch_id is not None:
        clauses.append("c.branch_id = :branch_id")
        params["branch_id"] = branch_id
    rows = db.execute(
        text(
            "SELECT c.id, c.code, c.name_ar, c.name_en, c.branch_id, c.territory_id "
            "FROM master_data.master_customer c WHERE "
            + " AND ".join(clauses)
            + " ORDER BY c.name_ar"
        ),
        params,
    ).mappings()
    return [CustomerOut.model_validate(dict(row)) for row in rows]


@router.get("/products")
def list_products(
    db: Db, current: CurrentUser, q: str | None = None, limit: int = PRODUCT_LIMIT_DEFAULT
) -> list[ProductOut]:
    _role(current)
    if limit < 1:
        limit = PRODUCT_LIMIT_DEFAULT
    limit = min(limit, PRODUCT_LIMIT_MAX)
    clauses = ["is_active"]
    params: dict = {"limit": limit}
    if q:
        clauses.append("(name_ar ILIKE :q OR name_en ILIKE :q OR sku ILIKE :q)")
        params["q"] = f"%{q}%"
    rows = db.execute(
        text(
            "SELECT id, sku, name_ar, name_en, base_price, vat_rate "
            "FROM master_data.master_product WHERE "
            + " AND ".join(clauses)
            + " ORDER BY name_ar LIMIT :limit"
        ),
        params,
    ).mappings()
    return [ProductOut.model_validate(dict(row)) for row in rows]
