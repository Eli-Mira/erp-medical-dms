"""Private/owner accounts (D40): isolated protected module, owner-only.

Same PostgreSQL DB, separate schema, separate permissions/audit. No company
AR/stock code paths are shared. Lightweight ledger entries only.
"""
import ipaddress
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db

router = APIRouter(prefix="/private-accounts", tags=["private-accounts"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]


def _owner(user):
    if not user["is_active"] or user["role"] != "owner" or not user["is_owner"]:
        raise HTTPException(403, "Owner only")


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@router.get("")
def list_entries(db: Db, current: CurrentUser, limit: int = 50, offset: int = 0):
    _owner(current)
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit 1..200")
    if offset < 0:
        raise HTTPException(422, "offset >= 0")
    rows = db.execute(
        text("SELECT id, account_label, entry_date, debit, credit, note, "
             "created_by, created_at FROM private.account_entry "
             "ORDER BY entry_date DESC, created_at DESC LIMIT :l OFFSET :o"),
        {"l": limit, "o": offset},
    ).mappings()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_entry(payload: dict, request: Request, db: Db, current: CurrentUser):
    _owner(current)
    label = (payload.get("account_label") or "").strip()
    edate = payload.get("entry_date")
    debit = payload.get("debit", 0)
    credit = payload.get("credit", 0)
    note = payload.get("note")
    if not label or not edate:
        raise HTTPException(422, "account_label and entry_date required")
    try:
        d = Decimal(str(debit))
        c = Decimal(str(credit))
    except (ValueError, TypeError, InvalidOperation, ArithmeticError):
        raise HTTPException(422, "debit/credit must be numeric")
    if not d.is_finite() or not c.is_finite():
        raise HTTPException(422, "debit/credit must be finite")
    if d < 0 or c < 0 or (d == 0 and c == 0):
        raise HTTPException(422, "one of debit/credit must be > 0")
    rid = db.execute(
        text("""INSERT INTO private.account_entry
            (account_label, entry_date, debit, credit, note, created_by)
            VALUES (:l, :d, :db, :cr, :n, :actor) RETURNING id"""),
        {"l": label, "d": edate, "db": d, "cr": c, "n": note, "actor": current["id"]},
    ).scalar()
    log_audit(db, current["id"], "created", "private_account_entry", rid, None,
              {"account_label": label, "debit": str(d), "credit": str(c)},
              ip_address=_host(request), user_agent=request.headers.get("user-agent"))
    db.commit()
    return {"id": str(rid), "account_label": label, "entry_date": edate,
            "debit": str(d), "credit": str(c), "note": note}
