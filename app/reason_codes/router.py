"""Reason codes (P2.9): read by all, write by owner/admin."""
import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db

router = APIRouter(prefix="/reason-codes", tags=["reason-codes"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

READ_ROLES = {"owner", "admin", "finance", "sales_manager", "district_manager",
              "medical_rep", "warehouse_staff", "read_only_auditor"}
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


@router.get("")
def list_reason_codes(db: Db, current: CurrentUser, category: str | None = None):
    _role(current, READ_ROLES)
    params = {}
    where = ""
    if category is not None:
        where = " WHERE category = :category"
        params["category"] = category
    rows = db.execute(
        text("SELECT id, code, name_ar, name_en, category, is_active "
             "FROM audit.reason_code" + where + " ORDER BY category, code"),
        params,
    ).mappings()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_reason_code(payload: dict, request: Request, db: Db, current: CurrentUser):
    _role(current, WRITE_ROLES)
    code = (payload.get("code") or "").strip()
    category = (payload.get("category") or "").strip() or None
    name_ar = (payload.get("name_ar") or "").strip() or None
    name_en = (payload.get("name_en") or "").strip() or None
    if not code:
        raise HTTPException(422, "code required")
    try:
        rid = db.execute(
            text("""INSERT INTO audit.reason_code (id, code, name_ar, name_en, category)
                    VALUES (gen_random_uuid(), :code, :ar, :en, :cat) RETURNING id"""),
            {"code": code, "ar": name_ar, "en": name_en, "cat": category},
        ).scalar()
    except Exception:  # noqa: BLE001
        db.rollback()
        raise HTTPException(409, "reason code already exists or invalid")
    log_audit(db, current["id"], "created", "reason_code", rid, None,
              {"code": code, "category": category},
              ip_address=_host(request), user_agent=request.headers.get("user-agent"))
    db.commit()
    return {"id": str(rid), "code": code, "name_ar": name_ar, "name_en": name_en,
            "category": category, "is_active": True}
