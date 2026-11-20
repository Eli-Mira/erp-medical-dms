"""Customer receivables API (finance).

Read/write scope per PRD §2:
  read:  owner, finance, sales_manager, district_manager, read_only_auditor
  write: owner, finance

Branch-scoped sales_manager/district_manager are restricted to customers in
their assigned branches (platform.user_branch). The 'invoice' entry type is
reserved for the posting flow and is rejected by the API.
"""
import ipaddress
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.finance import ar, aging, exports, statements
from app.finance.schemas import (
    AgingOut,
    EntryIn,
    EntryOut,
    StatementOut,
)

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


def _require_visible_customer(db, user, customer_id):
    """404 for a missing or out-of-scope customer, never revealing existence."""
    branches = _scope_branches(db, user)
    customer = db.execute(
        text("SELECT branch_id FROM master_data.master_customer WHERE id=:id"),
        {"id": customer_id}).mappings().one_or_none()
    if customer is None or (branches is not None and customer["branch_id"] not in branches):
        raise HTTPException(404, "Customer not found")


@router.get("/balances")
def list_balances(db: Db, current: CurrentUser, customer_id: UUID | None = None,
                  territory_id: UUID | None = None) -> list[dict]:
    _role(current, READ_ROLES)
    if customer_id is not None:
        _require_visible_customer(db, current, customer_id)
    return ar.balances(db, branches=_scope_branches(db, current),
                       customer_id=customer_id, territory_id=territory_id)


@router.get("/entries")
def list_entries(
    db: Db,
    current: CurrentUser,
    customer_id: UUID | None = None,
    entry_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0, le=10_000_000),
) -> list[EntryOut]:
    _role(current, READ_ROLES)
    return [
        EntryOut.model_validate(row)
        for row in _visible_entries(
            db,
            current,
            customer_id,
            entry_type,
            date_from,
            date_to,
            limit=limit,
            offset=offset,
        )
    ]


def _visible_entries(
    db,
    current,
    customer_id=None,
    entry_type=None,
    date_from=None,
    date_to=None,
    limit=None,
    offset=0,
):
    return ar.list_entries(
        db,
        str(customer_id) if customer_id else None,
        entry_type,
        date_from,
        date_to,
        branches=_scope_branches(db, current),
        limit=limit,
        offset=offset,
    )


def _branch_customers(db, branches):
    if not branches:
        return set()
    return {r[0] for r in db.execute(text(
        "SELECT id FROM master_data.master_customer WHERE branch_id = ANY(CAST(:b AS uuid[]))"),
        {"b": [str(b) for b in branches]}).fetchall()}


@router.get("/statements/{customer_id}", response_model=StatementOut)
def customer_statement(customer_id: UUID, db: Db, current: CurrentUser,
                       date_from: date | None = None, date_to: date | None = None) -> StatementOut:
    _role(current, READ_ROLES)
    _require_visible_customer(db, current, customer_id)
    return StatementOut.model_validate(statements.statement(
        db, customer_id=customer_id, date_from=date_from, date_to=date_to))


@router.get("/aging", response_model=AgingOut)
def ar_aging(db: Db, current: CurrentUser, as_of: date | None = None,
             customer_id: UUID | None = None,
             territory_id: UUID | None = None) -> AgingOut:
    _role(current, READ_ROLES)
    if customer_id is not None:
        _require_visible_customer(db, current, customer_id)
    return AgingOut.model_validate(aging.aging(
        db, as_of=as_of or datetime.now(UTC).astimezone().date(),
        customer_id=customer_id, branches=_scope_branches(db, current),
        territory_id=territory_id))


@router.get("/balances/export")
def export_balances(db: Db, current: CurrentUser, customer_id: UUID | None = None,
                    territory_id: UUID | None = None):
    _role(current, READ_ROLES)
    if customer_id is not None:
        _require_visible_customer(db, current, customer_id)
    rows = ar.balances(db, branches=_scope_branches(db, current),
                       customer_id=customer_id, territory_id=territory_id)
    return exports.csv_response(
        "ar_balances.csv", ["customer_id", "balance"],
        [[exports.cell(row["customer_id"]), exports.cell(row["balance"])] for row in rows])


ENTRY_CSV_HEADERS = ["id", "customer_id", "invoice_id", "entry_type", "entry_date",
                     "due_date", "debit", "credit", "reason_id", "note", "created_by",
                     "created_at", "receipt_id", "reverses_entry_id"]


@router.get("/entries/export")
def export_entries(db: Db, current: CurrentUser, customer_id: UUID | None = None,
                   entry_type: str | None = None, date_from: date | None = None,
                   date_to: date | None = None):
    _role(current, READ_ROLES)
    rows = _visible_entries(db, current, customer_id, entry_type, date_from, date_to)
    return exports.csv_response(
        "ar_entries.csv", ENTRY_CSV_HEADERS,
        [[exports.cell(row.get(header)) for header in ENTRY_CSV_HEADERS] for row in rows])


AGING_CSV_HEADERS = ["customer_id", "current", "d1_30", "d31_60", "d61_90",
                     "over_90", "undated", "total"]


@router.get("/aging/export")
def export_aging(db: Db, current: CurrentUser, as_of: date | None = None,
                 customer_id: UUID | None = None,
                 territory_id: UUID | None = None):
    _role(current, READ_ROLES)
    if customer_id is not None:
        _require_visible_customer(db, current, customer_id)
    payload = aging.aging(
        db, as_of=as_of or datetime.now(UTC).astimezone().date(),
        customer_id=customer_id, branches=_scope_branches(db, current),
        territory_id=territory_id)
    return exports.csv_response(
        "ar_ledger_aging.csv", AGING_CSV_HEADERS,
        [[exports.cell(customer["customer_id"])]
         + [exports.cell(customer[header]) for header in AGING_CSV_HEADERS[1:]]
         for customer in payload["customers"]])


@router.get("/statements/{customer_id}/export")
def export_statement(customer_id: UUID, db: Db, current: CurrentUser,
                     date_from: date | None = None, date_to: date | None = None):
    _role(current, READ_ROLES)
    _require_visible_customer(db, current, customer_id)
    payload = statements.statement(db, customer_id=customer_id,
                                   date_from=date_from, date_to=date_to)
    headers = ["entry_date", "entry_type", "invoice_id", "receipt_id", "due_date",
               "debit", "credit", "balance", "note"]
    return exports.csv_response(
        f"ar_statement_{customer_id}.csv", headers,
        [[exports.cell(line.get(header)) for header in headers] for line in payload["lines"]])


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
