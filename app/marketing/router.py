"""Marketing spend + objective/KPI (V2 §2B.16–2B.18)."""
import hashlib
import ipaddress
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.master.router import _branches, _territories

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


class SpendInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kol_id: UUID | None = None
    territory_id: UUID | None = None
    spend_date: date
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    activity_type: str = Field(min_length=1, max_length=40)
    notes: str | None = None
    product_ids: list[UUID] = Field(default_factory=list)


class ObjectiveInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    spend_id: UUID | None = None
    kol_id: UUID | None = None
    product_id: UUID | None = None
    territory_id: UUID | None = None
    objective: str = Field(min_length=1)
    expected_kpi: str | None = None
    actual_result: str | None = None
    followup_notes: str | None = None


def _validated(payload, model, db, current):
    try:
        values = model.model_validate(payload).model_dump(mode="json")
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_context=False)) from None
    if any(isinstance(value, str) and "\x00" in value for value in values.values()):
        raise HTTPException(422, "Null characters are not allowed")
    territory = values.get("territory_id")
    scope = _territories(db, current)
    if territory is not None:
        if scope is not None and UUID(territory) not in scope:
            raise HTTPException(403, "Territory access denied")
        if not db.execute(
            text("SELECT 1 FROM master_data.master_territory WHERE id=:id"),
            {"id": territory},
        ).scalar():
            raise HTTPException(422, "territory not found")
    kol = values.get("kol_id")
    if kol is not None:
        row = db.execute(
            text(
                "SELECT branch_id FROM marketing.marketing_kol WHERE id=:id AND is_active FOR SHARE"
            ),
            {"id": kol},
        ).first()
        if row is None:
            raise HTTPException(422, "kol not active")
        branches = _branches(db, current)
        if branches is not None and row[0] not in branches:
            raise HTTPException(403, "KOL branch access denied")
    products = values.get("product_ids", []) + (
        [values["product_id"]] if values.get("product_id") else []
    )
    for product in products:
        if not db.execute(
            text(
                "SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active FOR SHARE"
            ),
            {"id": product},
        ).scalar():
            raise HTTPException(422, "product not active")
    if "product_ids" in values:
        values["product_ids"] = list(dict.fromkeys(values["product_ids"]))
    spend = values.get("spend_id")
    if spend is not None:
        row = (
            db.execute(
                text(
                    "SELECT territory_id, kol_id FROM marketing.marketing_spend WHERE id=:id FOR SHARE"
                ),
                {"id": spend},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(422, "spend not found")
        _record_scope(db, current, row)
    return values


def _record_scope(db, current, row):
    scope = _territories(db, current)
    if (
        scope is not None
        and row["territory_id"] is not None
        and row["territory_id"] not in scope
    ):
        raise HTTPException(403, "Territory access denied")
    branches = _branches(db, current)
    if branches is not None and row["kol_id"] is not None:
        branch = db.execute(
            text("SELECT branch_id FROM marketing.marketing_kol WHERE id=:id"),
            {"id": row["kol_id"]},
        ).scalar()
        if branch not in branches:
            raise HTTPException(403, "KOL branch access denied")


def _list_scope(db, current, alias):
    assert alias in {"s", "marketing_objective"}
    conditions, params = [], {}
    territories = _territories(db, current)
    if territories is not None:
        conditions.append(
            f"({alias}.territory_id IS NULL OR {alias}.territory_id=ANY(CAST(:scope_territories AS uuid[])))"
        )
        params["scope_territories"] = [str(value) for value in territories]
    branches = _branches(db, current)
    if branches is not None:
        conditions.append(
            f"({alias}.kol_id IS NULL OR EXISTS (SELECT 1 FROM marketing.marketing_kol k WHERE k.id={alias}.kol_id AND k.branch_id=ANY(CAST(:scope_branches AS uuid[]))))"
        )
        params["scope_branches"] = [str(value) for value in branches]
    return conditions, params


def _transaction(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        db = kwargs["db"]
        try:
            return function(*args, **kwargs)
        except Exception:
            db.rollback()
            raise

    return wrapped


@router.post("/spend", status_code=201)
@_transaction
def create_spend(payload: dict, request: Request, db: Db, current: CurrentUser):
    _role(current, WRITE_ROLES)
    payload = _validated(payload, SpendInput, db, current)
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
    if not amt.is_finite() or amt < 0:
        raise HTTPException(422, "amount must be non-negative and finite")
    if (
        kol is not None
        and not db.execute(
            text("SELECT 1 FROM marketing.marketing_kol WHERE id=:id AND is_active"),
            {"id": kol},
        ).scalar()
    ):
        raise HTTPException(422, "kol not active")
    if (
        territory is not None
        and not db.execute(
            text("SELECT 1 FROM master_data.master_territory WHERE id=:id"),
            {"id": territory},
        ).scalar()
    ):
        raise HTTPException(422, "territory not found")
    for pid in products:
        if not db.execute(
            text("SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active"),
            {"id": pid},
        ).scalar():
            raise HTTPException(422, f"product {pid} not active")
    sid = db.execute(
        text("""INSERT INTO marketing.marketing_spend
            (kol_id, territory_id, spend_date, amount, activity_type, notes, created_by)
            VALUES (:kol, :terr, :sd, :amt, :act, :notes, :actor)
            RETURNING id"""),
        {
            "kol": kol,
            "terr": territory,
            "sd": sdate,
            "amt": amt,
            "act": activity,
            "notes": notes,
            "actor": current["id"],
        },
    ).scalar()
    for pid in products:
        db.execute(
            text(
                "INSERT INTO marketing.marketing_spend_product (spend_id, product_id) "
                "VALUES (:s, :p) ON CONFLICT DO NOTHING"
            ),
            {"s": sid, "p": pid},
        )
    log_audit(
        db,
        current["id"],
        "created",
        "marketing_spend",
        sid,
        None,
        {
            "kol": kol,
            "territory": territory,
            "amount": str(amt),
            "activity": activity,
            "products": products,
        },
        ip_address=_host(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {
        "id": str(sid),
        "kol_id": kol,
        "territory_id": territory,
        "spend_date": sdate,
        "amount": str(amt),
        "activity_type": activity,
        "notes": notes,
        "product_ids": products,
    }


@router.get("/spend")
def list_spend(
    db: Db,
    current: CurrentUser,
    kol_id: UUID | None = None,
    territory_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
):
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit 1..200")
    if offset < 0:
        raise HTTPException(422, "offset >= 0")
    _role(current, READ_ROLES)
    conditions, params = _list_scope(db, current, "s")
    params.update(limit=limit, offset=offset)
    if kol_id is not None:
        conditions.append("kol_id = :kol_id")
        params["kol_id"] = kol_id
    if territory_id is not None:
        conditions.append("territory_id = :territory_id")
        params["territory_id"] = territory_id
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(
            "SELECT s.*, (SELECT array_agg(product_id) FROM marketing.marketing_spend_product "
            "WHERE spend_id=s.id) AS product_ids FROM marketing.marketing_spend s"
            + where
            + " ORDER BY s.spend_date DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings()
    return [dict(r) for r in rows]


@router.post("/objectives", status_code=201)
@_transaction
def create_objective(payload: dict, request: Request, db: Db, current: CurrentUser):
    _role(current, WRITE_ROLES)
    payload = _validated(payload, ObjectiveInput, db, current)
    spend = payload.get("spend_id")
    kol = payload.get("kol_id")
    product = payload.get("product_id")
    territory = payload.get("territory_id")
    objective = payload.get("objective")
    if not objective:
        raise HTTPException(422, "objective required")
    if (
        spend is not None
        and not db.execute(
            text("SELECT 1 FROM marketing.marketing_spend WHERE id=:id"), {"id": spend}
        ).scalar()
    ):
        raise HTTPException(422, "spend not found")
    if (
        kol is not None
        and not db.execute(
            text("SELECT 1 FROM marketing.marketing_kol WHERE id=:id AND is_active"),
            {"id": kol},
        ).scalar()
    ):
        raise HTTPException(422, "kol not active")
    if (
        product is not None
        and not db.execute(
            text("SELECT 1 FROM master_data.master_product WHERE id=:id AND is_active"),
            {"id": product},
        ).scalar()
    ):
        raise HTTPException(422, "product not active")
    if (
        territory is not None
        and not db.execute(
            text("SELECT 1 FROM master_data.master_territory WHERE id=:id"),
            {"id": territory},
        ).scalar()
    ):
        raise HTTPException(422, "territory not found")
    oid = db.execute(
        text("""INSERT INTO marketing.marketing_objective
            (spend_id, kol_id, product_id, territory_id, objective,
             expected_kpi, actual_result, followup_notes, created_by)
            VALUES (:spend, :kol, :product, :terr, :obj, :kpi, :actual, :fu, :actor)
            RETURNING id"""),
        {
            "spend": spend,
            "kol": kol,
            "product": product,
            "terr": territory,
            "obj": objective,
            "kpi": payload.get("expected_kpi"),
            "actual": payload.get("actual_result"),
            "fu": payload.get("followup_notes"),
            "actor": current["id"],
        },
    ).scalar()
    log_audit(
        db,
        current["id"],
        "created",
        "marketing_objective",
        oid,
        None,
        {"objective": objective, "spend": spend, "kol": kol, "product": product},
        ip_address=_host(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {
        "id": str(oid),
        "spend_id": spend,
        "kol_id": kol,
        "product_id": product,
        "territory_id": territory,
        "objective": objective,
        "expected_kpi": payload.get("expected_kpi"),
        "actual_result": payload.get("actual_result"),
        "followup_notes": payload.get("followup_notes"),
    }


def _snapshot(db, current, kind, record_id, lock=False):
    table = "marketing_spend" if kind == "spend" else "marketing_objective"
    row = (
        db.execute(
            text(
                "SELECT * FROM marketing."
                + table
                + " WHERE id=:id"
                + (" FOR UPDATE" if lock else "")
            ),
            {"id": record_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Marketing record not found")
    _record_scope(db, current, row)
    result = dict(row)
    if kind == "spend":
        result["product_ids"] = [
            str(r[0])
            for r in db.execute(
                text(
                    "SELECT product_id FROM marketing.marketing_spend_product WHERE spend_id=:id ORDER BY product_id"
                ),
                {"id": record_id},
            )
        ]
    result = jsonable_encoder(result, custom_encoder={Decimal: str})
    result["revision"] = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode()
    ).hexdigest()
    return result


@router.get("/spend/{record_id}")
def get_spend(record_id: UUID, db: Db, current: CurrentUser):
    _role(current, READ_ROLES)
    return _snapshot(db, current, "spend", record_id)


@router.get("/objectives/{record_id}")
def get_objective(record_id: UUID, db: Db, current: CurrentUser):
    _role(current, READ_ROLES)
    return _snapshot(db, current, "objectives", record_id)


def _update(kind, record_id, payload, request, db, current):
    _role(current, WRITE_ROLES)
    payload = dict(payload)
    revision = payload.pop("revision", None)
    before = _snapshot(db, current, kind, record_id, lock=True)
    if revision != before["revision"]:
        raise HTTPException(409, "Record changed; reopen it before saving")
    model = SpendInput if kind == "spend" else ObjectiveInput
    values = _validated(payload, model, db, current)
    table = "marketing_spend" if kind == "spend" else "marketing_objective"
    columns = tuple(model.model_fields)
    assignments = ", ".join(
        column + "=:" + column for column in columns if column != "product_ids"
    )
    db.execute(
        text(
            "UPDATE marketing." + table + " SET " + assignments + " WHERE id=:record_id"
        ),
        {**values, "record_id": record_id},
    )
    if kind == "spend":
        db.execute(
            text("DELETE FROM marketing.marketing_spend_product WHERE spend_id=:id"),
            {"id": record_id},
        )
        for product in values["product_ids"]:
            db.execute(
                text(
                    "INSERT INTO marketing.marketing_spend_product (spend_id, product_id) VALUES (:id, :product)"
                ),
                {"id": record_id, "product": product},
            )
    after = _snapshot(db, current, kind, record_id)
    log_audit(
        db,
        current["id"],
        "updated",
        table,
        record_id,
        before,
        after,
        ip_address=_host(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return after


@router.patch("/spend/{record_id}")
@_transaction
def update_spend(
    record_id: UUID, payload: dict, request: Request, db: Db, current: CurrentUser
):
    return _update("spend", record_id, payload, request, db, current)


@router.patch("/objectives/{record_id}")
@_transaction
def update_objective(
    record_id: UUID, payload: dict, request: Request, db: Db, current: CurrentUser
):
    return _update("objectives", record_id, payload, request, db, current)


@router.get("/objectives")
def list_objectives(
    db: Db,
    current: CurrentUser,
    kol_id: UUID | None = None,
    product_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
):
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit 1..200")
    if offset < 0:
        raise HTTPException(422, "offset >= 0")
    _role(current, READ_ROLES)
    conditions, params = _list_scope(db, current, "marketing_objective")
    params.update(limit=limit, offset=offset)
    if kol_id is not None:
        conditions.append("kol_id = :kol_id")
        params["kol_id"] = kol_id
    if product_id is not None:
        conditions.append("product_id = :product_id")
        params["product_id"] = product_id
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(
            "SELECT * FROM marketing.marketing_objective"
            + where
            + " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings()
    return [dict(r) for r in rows]
