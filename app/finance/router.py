"""Customer receivables API (finance).

Read/write scope per PRD §2:
  read:  owner, finance, sales_manager, district_manager, read_only_auditor
  write: owner, finance

Branch-scoped sales_manager/district_manager are restricted to customers in
their assigned branches (platform.user_branch). The 'invoice' entry type is
reserved for the posting flow and is rejected by the API.
"""
import ipaddress
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.finance import ar
from app.finance.schemas import EntryIn, EntryOut

router = APIRouter(prefix="/ar", tags=["ar"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

READ_ROLES = {"owner", "finance", "sales_manager", "district_manager", "read_only_auditor"}
WRITE_ROLES = {"owner", "finance"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Receivables access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def _scope_branches(db, user):
    """Return branch ids a branch-scoped user may touch, else None (global)."""
    role = user["role"]
    if role in {"owner", "finance", "read_only_auditor"}:
        return None
    rows = db.execute(text("SELECT branch_id FROM platform.user_branch WHERE user_id=:u"),
                      {"u": user["id"]}).fetchall()
    if not rows:
        return set()  # assigned-but-empty -> deny all
    return {r[0] for r in rows}


@router.get("/balances")
def list_balances(db: Db, current: CurrentUser, customer_id: UUID | None = None) -> list[dict]:
    _role(current, READ_ROLES)
    branches = _scope_branches(db, current)
    if branches is not None and not branches:
        return []  # branch-scoped but assigned nothing -> deny all
    if customer_id is not None:
        customer = db.execute(text("SELECT branch_id FROM master_data.master_customer WHERE id=:id"),
                              {"id": customer_id}).mappings().one_or_none()
        if customer is None or (branches is not None and customer["branch_id"] not in branches):
            raise HTTPException(404, "Customer not found")
        return [{"customer_id": str(customer_id), "balance": str(ar.customer_balance(db, customer_id))}]
    where, params = "", {}
    if branches is not None:
        where = "WHERE c.branch_id = ANY(CAST(:branches AS uuid[]))"
        params["branches"] = [str(b) for b in branches]
    rows = db.execute(text(
        "SELECT c.id AS customer_id, COALESCE(SUM(e.debit), 0) - COALESCE(SUM(e.credit), 0) AS balance "
        "FROM master_data.master_customer c "
        "LEFT JOIN finance.ar_entry e ON e.customer_id = c.id " + where +
        " GROUP BY c.id ORDER BY c.id"), params).mappings()
    return [{"customer_id": str(r["customer_id"]), "balance": str(r["balance"])} for r in rows]


@router.get("/entries")
def list_entries(db: Db, current: CurrentUser, customer_id: UUID | None = None,
                 entry_type: str | None = None, date_from: date | None = None,
                 date_to: date | None = None) -> list[EntryOut]:
    _role(current, READ_ROLES)
    rows = ar.list_entries(db, str(customer_id) if customer_id else None, entry_type, date_from, date_to)
    branches = _scope_branches(db, current)
    if branches is not None:
        allowed = _branch_customers(db, branches)
        rows = [r for r in rows if r["customer_id"] in allowed]
    return [EntryOut.model_validate(row) for row in rows]


def _branch_customers(db, branches):
    if not branches:
        return set()
    return {r[0] for r in db.execute(text(
        "SELECT id FROM master_data.master_customer WHERE branch_id = ANY(CAST(:b AS uuid[]))"),
        {"b": [str(b) for b in branches]}).fetchall()}


@router.post("/entries", status_code=201)
def record_entry(payload: EntryIn, request: Request, db: Db, current: CurrentUser) -> EntryOut:
    _role(current, WRITE_ROLES)
    if not db.execute(text("SELECT 1 FROM master_data.master_customer WHERE id=:id FOR SHARE"),
                      {"id": payload.customer_id}).scalar():
        raise HTTPException(422, "Customer must exist")
    try:
        entry_id = ar.record_entry(db, customer_id=payload.customer_id, entry_type=payload.entry_type,
                                   debit=payload.debit, credit=payload.credit, on_date=payload.entry_date,
                                   due_date=payload.due_date, reason_id=payload.reason_id,
                                   note=payload.note, actor_id=current["id"])
        row = db.execute(text("SELECT * FROM finance.ar_entry WHERE id=:id"), {"id": entry_id}).mappings().one()
        entry = EntryOut.model_validate(dict(row))
        log_audit(db, current["id"], "created", "ar_entry", entry_id, None,
                  entry.model_dump(mode="json"), _host(request), request.headers.get("user-agent", "")[:1000])
        db.commit()
        return entry
    except ValueError as error:
        db.rollback()
        raise HTTPException(403, str(error)) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(422, "Entry violates a database reference or value constraint") from error
    except Exception:
        db.rollback()
        raise
