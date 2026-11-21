"""Reason codes (P2.9): read by all, write by owner/admin."""
import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db

router = APIRouter(prefix="/reason-codes", tags=["reason-codes"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

READ_ROLES = {
    "owner",
    "admin",
    "finance",
    "sales_manager",
    "district_manager",
    "medical_rep",
    "warehouse_staff",
    "read_only_auditor",
}
WRITE_ROLES = {"owner", "admin"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Reason-code access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


class ReasonCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=60)
    category: str | None = Field(default=None, max_length=60)
    name_ar: str | None = Field(default=None, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)

    @field_validator("code", "category", "name_ar", "name_en")
    @classmethod
    def no_null_and_normalize(cls, v: str | None, info):
        # Reject null byte in any string field
        if isinstance(v, str):
            if "\x00" in v:
                raise ValueError(f"{info.field_name} contains null byte")
            # For optional fields, turn empty strings into None
            if info.field_name != "code" and v == "":
                return None
        return v


@router.get("")
def list_reason_codes(db: Db, current: CurrentUser, category: str | None = None):
    _role(current, READ_ROLES)
    params = {}
    where = ""
    if category is not None:
        where = " WHERE category = :category"
        params["category"] = category
    rows = db.execute(
        text(
            "SELECT id, code, name_ar, name_en, category, is_active "
            "FROM audit.reason_code"
            + where
            + " ORDER BY category, code"
        ),
        params,
    ).mappings()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_reason_code(payload: ReasonCodeIn, request: Request, db: Db, current: CurrentUser):
    _role(current, WRITE_ROLES)

    try:
        rid = db.execute(
            text(
                """INSERT INTO audit.reason_code (id, code, name_ar, name_en, category)
                   VALUES (gen_random_uuid(), :code, :ar, :en, :cat) RETURNING id"""
            ),
            {
                "code": payload.code,
                "ar": payload.name_ar,
                "en": payload.name_en,
                "cat": payload.category,
            },
        ).scalar()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "reason code already exists or invalid")

    log_audit(
        db,
        current["id"],
        "created",
        "reason_code",
        rid,
        None,
        {"code": payload.code, "category": payload.category},
        ip_address=_host(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {
        "id": str(rid),
        "code": payload.code,
        "name_ar": payload.name_ar,
        "name_en": payload.name_en,
        "category": payload.category,
        "is_active": True,
    }
