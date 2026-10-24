"""Master-data lookups for the invoice screen and B Master Data slice.

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

B Master Data slice (PRD B-02/B-12/B-13) adds three company-wide references,
each gated to the roles that consume it (no purchasing/marketing role exists yet):

- suppliers  : active ``master_data.master_supplier`` rows (owner/finance/auditor).
- accounts   : active ``finance.coa_account`` rows, optionally by account type
               (owner/finance/auditor). No accounts are seeded — the COA
               structure is a business-policy question.
- doctors    : active ``marketing.marketing_kol`` rows; non-global callers are
               limited to their ``platform.user_branch`` grants. A doctor with no
               branch is never offered to a branch-scoped caller.

Supplier maintenance alone adds owner-only writes with atomic audit records.
Other reference routes remain read-only; no schema changes.
"""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.master.schemas import (
    AccountOut,
    BranchOut,
    CustomerOut,
    CustomerPatch,
    DoctorOut,
    ProductOut,
    SupplierIn,
    SupplierOut,
    SupplierPatch,
    WarehouseOut,
)
from app.text_search import like_pattern

router = APIRouter(prefix="/master", tags=["master-data"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

# Read roles (invoice pipeline). Unchanged.
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

# B Master Data slice: company-wide references, each limited to its consumers.
SUPPLIER_ROLES = {"owner", "finance", "read_only_auditor"}
ACCOUNT_ROLES = {"owner", "finance", "read_only_auditor"}
DOCTOR_ROLES = {
    "owner",
    "sales_manager",
    "district_manager",
    "medical_rep",
    "read_only_auditor",
}
AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]

LIMIT_DEFAULT = 100
LIMIT_MAX = 500


def _require(user, allowed: set[str]):
    role = user["role"]
    if (
        not user["is_active"]
        or role not in allowed
        or (role == "owner" and not user["is_owner"])
    ):
        raise HTTPException(403, "Master data access denied")
    return role


def _role(user):
    return _require(user, READ_ROLES)


def _limit(value: int) -> int:
    if value < 1:
        return LIMIT_DEFAULT
    return min(value, LIMIT_MAX)


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
    """Branch ids a non-global caller may reference; None is unrestricted."""
    if user["role"] in GLOBAL_BRANCH_ROLES:
        return None
    rows = db.execute(
        text("SELECT branch_id FROM platform.user_branch WHERE user_id=:uid"),
        {"uid": user["id"]},
    ).fetchall()
    return {r[0] for r in rows}


def _warehouses(db, user):
    """Resolve branch grants to actual active warehouse IDs, not routes."""
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


def _require_owner(current: CurrentUser) -> None:
    _require(current, {"owner"})


def _supplier_row(db, supplier_id: UUID, *, lock=False):
    row = (
        db.execute(
            text(
                "SELECT id, code, name_ar, name_en, contact_phone, address, is_active "
                "FROM master_data.master_supplier WHERE id = :id"
                + (" FOR UPDATE" if lock else "")
            ),
            {"id": str(supplier_id)},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return dict(row)


def _customer_row(db, customer_id: UUID, *, lock=False):
    row = (
        db.execute(
            text(
                "SELECT id, code, name_ar, name_en, branch_id, territory_id "
                "FROM master_data.master_customer WHERE id = :id"
                + (" FOR UPDATE" if lock else "")
            ),
            {"id": str(customer_id)},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return dict(row)


def _supplier_values(payload: SupplierIn) -> dict:
    return {
        "id": uuid4(),
        "code": payload.code,
        "name_ar": payload.name_ar,
        "name_en": payload.name_en,
        "contact_phone": payload.contact_phone,
        "address": payload.address,
    }


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


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: UUID, payload: CustomerPatch, db: Db, current: CurrentUser
):
    _require_owner(current)
    changes = payload.model_dump(exclude_unset=True)
    try:
        before = _customer_row(db, customer_id, lock=True)
        assignments = ", ".join(
            f"{field}=:{field}" for field in ("name_ar", "name_en") if field in changes
        )
        if assignments:
            db.execute(
                text(
                    "UPDATE master_data.master_customer SET "
                    + assignments
                    + " WHERE id=:id"
                ),
                {"id": customer_id, **changes},
            )
        response = CustomerOut.model_validate({**before, **changes})
        log_audit(
            db,
            current["id"],
            "updated",
            "master_customer",
            customer_id,
            CustomerOut.model_validate(before).model_dump(mode="json"),
            response.model_dump(mode="json"),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return response


@router.get("/products")
def list_products(
    db: Db, current: CurrentUser, q: str | None = None, limit: int = LIMIT_DEFAULT
) -> list[ProductOut]:
    _role(current)
    limit = _limit(limit)
    clauses = ["is_active"]
    params: dict = {"limit": limit}
    if q:
        clauses.append("(name_ar ILIKE :q OR name_en ILIKE :q OR sku ILIKE :q)")
        params["q"] = like_pattern(q)
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


@router.get("/suppliers")
def list_suppliers(
    db: Db,
    current: CurrentUser,
    q: str | None = None,
    limit: int = LIMIT_DEFAULT,
    include_inactive: bool = False,
) -> list[SupplierOut]:
    _require(current, SUPPLIER_ROLES)
    if include_inactive:
        _require_owner(current)
    clauses = ["(is_active OR :include_inactive)"]
    params: dict = {"limit": _limit(limit), "include_inactive": include_inactive}
    if q:
        clauses.append("(name_ar ILIKE :q OR name_en ILIKE :q OR code ILIKE :q)")
        params["q"] = like_pattern(q)
    rows = db.execute(
        text(
            "SELECT id, code, name_ar, name_en, contact_phone, address, is_active "
            "FROM master_data.master_supplier WHERE "
            + " AND ".join(clauses)
            + " ORDER BY name_ar LIMIT :limit"
        ),
        params,
    ).mappings()
    return [SupplierOut.model_validate(dict(row)) for row in rows]


@router.get("/accounts")
def list_accounts(
    db: Db,
    current: CurrentUser,
    account_type: AccountType | None = None,
    limit: int = LIMIT_DEFAULT,
) -> list[AccountOut]:
    _require(current, ACCOUNT_ROLES)
    clauses = ["is_active"]
    params: dict = {"limit": _limit(limit)}
    if account_type is not None:
        clauses.append("account_type = :account_type")
        params["account_type"] = account_type
    rows = db.execute(
        text(
            "SELECT id, code, name_ar, name_en, account_type, parent_id, is_active "
            "FROM finance.coa_account WHERE "
            + " AND ".join(clauses)
            + " ORDER BY code LIMIT :limit"
        ),
        params,
    ).mappings()
    return [AccountOut.model_validate(dict(row)) for row in rows]


@router.get("/doctors")
def list_doctors(
    db: Db,
    current: CurrentUser,
    branch_id: UUID | None = None,
    q: str | None = None,
    limit: int = LIMIT_DEFAULT,
) -> list[DoctorOut]:
    _require(current, DOCTOR_ROLES)
    scope = _branches(db, current)
    if scope is not None and not scope:
        return []
    clauses = ["is_active"]
    params: dict = {"limit": _limit(limit)}
    if scope is not None:
        clauses.append("branch_id = ANY(CAST(:branches AS uuid[]))")
        params["branches"] = [str(b) for b in scope]
    if branch_id is not None:
        clauses.append("branch_id = :branch_id")
        params["branch_id"] = branch_id
    if q:
        clauses.append(
            "(name_ar ILIKE :q OR name_en ILIKE :q OR code ILIKE :q "
            "OR specialty ILIKE :q)"
        )
        params["q"] = like_pattern(q)
    rows = db.execute(
        text(
            "SELECT id, code, name_ar, name_en, specialty, branch_id, "
            "contact_phone, is_active FROM marketing.marketing_kol WHERE "
            + " AND ".join(clauses)
            + " ORDER BY name_ar LIMIT :limit"
        ),
        params,
    ).mappings()
    return [DoctorOut.model_validate(dict(row)) for row in rows]


@router.post(
    "/suppliers",
    status_code=201,
    response_model=SupplierOut,
    responses={409: {"description": "Unique supplier code conflict"}},
)
def create_supplier(db: Db, current: CurrentUser, payload: SupplierIn):
    """Create a supplier as the confirmed active owner.

    One transaction owns the row + actor-bound audit; the response is validated
    against SupplierOut before commit. Any failure rolls back both.
    """
    _require_owner(current)
    values = _supplier_values(payload)
    try:
        db.execute(
            text(
                "INSERT INTO master_data.master_supplier "
                "(id, code, name_ar, name_en, contact_phone, address) "
                "VALUES (:id, :code, :name_ar, :name_en, :contact_phone, :address)"
            ),
            values,
        )
        response = SupplierOut.model_validate({**values, "is_active": True})
        log_audit(
            db,
            current["id"],
            "created",
            "master_supplier",
            values["id"],
            None,
            response.model_dump(mode="json"),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Supplier code already exists"
        ) from None
    except Exception:
        db.rollback()
        raise
    return response


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def get_supplier(db: Db, current: CurrentUser, supplier_id: UUID):
    """Retrieve a supplier for maintenance: active or inactive rows both work.

    Reads stay within the existing SUPPLIER_ROLES; inactive rows are not hidden.
    """
    _require(current, SUPPLIER_ROLES)
    return SupplierOut.model_validate(_supplier_row(db, supplier_id))


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: UUID, payload: SupplierPatch, db: Db, current: CurrentUser
):
    _require_owner(current)
    changes = payload.model_dump(exclude_unset=True)
    try:
        before = _supplier_row(db, supplier_id, lock=True)
        # Identifiers come only from this fixed whitelist; values remain parameters.
        columns = (
            "code",
            "name_ar",
            "name_en",
            "contact_phone",
            "address",
            "is_active",
        )
        assignments = ", ".join(
            f"{field}=:{field}" for field in columns if field in changes
        )
        db.execute(
            text(
                "UPDATE master_data.master_supplier SET "
                + assignments
                + " WHERE id=:id"
            ),
            {"id": supplier_id, **changes},
        )
        response = SupplierOut.model_validate({**before, **changes})
        log_audit(
            db,
            current["id"],
            "updated",
            "master_supplier",
            supplier_id,
            SupplierOut.model_validate(before).model_dump(mode="json"),
            response.model_dump(mode="json"),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Supplier code already exists") from None
    except Exception:
        db.rollback()
        raise
    return response


@router.delete("/suppliers/{supplier_id}", status_code=204)
def deactivate_supplier(supplier_id: UUID, db: Db, current: CurrentUser):
    _require_owner(current)
    try:
        before = _supplier_row(db, supplier_id, lock=True)
        if not before["is_active"]:
            db.rollback()
            return Response(status_code=204)
        db.execute(
            text("UPDATE master_data.master_supplier SET is_active=false WHERE id=:id"),
            {"id": supplier_id},
        )
        old = SupplierOut.model_validate(before).model_dump(mode="json")
        log_audit(
            db,
            current["id"],
            "deactivated",
            "master_supplier",
            supplier_id,
            old,
            {**old, "is_active": False},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return Response(status_code=204)
