"""Private/owner accounts (D40): isolated protected module, owner-only.

Same PostgreSQL DB, separate schema, separate permissions/audit. No company
AR/stock code paths are shared. Lightweight ledger entries only.
"""
import ipaddress
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db

router = APIRouter(prefix="/private-accounts", tags=["private-accounts"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

PrivateMoney = Annotated[
    Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
]


class PrivateAccountEntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    account_label: Annotated[str, Field(min_length=1, max_length=120)]
    entry_date: date
    debit: PrivateMoney = Decimal("0.00")
    credit: PrivateMoney = Decimal("0.00")
    note: Annotated[str, Field(max_length=4000)] | None = None

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def reject_inexact_inputs(cls, value):
        if isinstance(value, (bool, float)):
            raise ValueError("Use a decimal string or integer, not a float or boolean")
        return value

    @field_validator("account_label", "note")
    @classmethod
    def reject_null_characters(cls, value):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Text cannot contain null characters")
        return value

    @model_validator(mode="after")
    def validate_one_side(self):
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Exactly one of debit or credit must be > 0")
        return self


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
def create_entry(
    payload: PrivateAccountEntryIn,
    request: Request,
    db: Db,
    current: CurrentUser,
):
    _owner(current)
    label = payload.account_label
    edate = payload.entry_date.isoformat()
    d = payload.debit
    c = payload.credit
    note = payload.note
    rid = db.execute(
        text("""INSERT INTO private.account_entry
            (account_label, entry_date, debit, credit, note, created_by)
            VALUES (:l, :d, :db, :cr, :n, :actor) RETURNING id"""),
        {"l": label, "d": payload.entry_date, "db": d, "cr": c, "n": note, "actor": current["id"]},
    ).scalar()
    log_audit(db, current["id"], "created", "private_account_entry", rid, None,
              {"account_label": label, "debit": str(d), "credit": str(c)},
              ip_address=_host(request), user_agent=request.headers.get("user-agent"))
    db.commit()
    return {"id": str(rid), "account_label": label, "entry_date": edate,
            "debit": str(d), "credit": str(c), "note": note}
