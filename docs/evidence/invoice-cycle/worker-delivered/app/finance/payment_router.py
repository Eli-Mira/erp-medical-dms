"""Payment receipt API endpoints (collections).

Write: Owner, Finance only. Read: Owner, Finance, Sales Manager, District Manager,
Medical Rep (own), Read-Only Auditor (Posted-linked only).
All mutations behind POSTING_ENABLED gate.
"""
import ipaddress
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.config import POSTING_ENABLED
from app.db import get_db
from app.finance import payments
from app.finance.schemas import ReceiptIn, ReceiptOut, ReceiptVoidIn
from app.sales.router import _invoice, _role as _sales_role

router = APIRouter(prefix="/collections", tags=["collections"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

READ_ROLES = {"owner", "finance", "sales_manager", "district_manager", "medical_rep", "read_only_auditor"}
WRITE_ROLES = {"owner", "finance"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def _scope_branches(db, user):
    role = user["role"]
    if role in {"owner", "finance", "read_only_auditor"}:
        return None
    rows = db.execute(
        text("SELECT branch_id FROM platform.user_branch WHERE user_id=:u"),
        {"u": user["id"]},
    ).fetchall()
    if not rows:
        return set()
    return {r[0] for r in rows}


@router.get("/{receipt_id}")
def get_receipt(receipt_id: UUID, db: Db, current: CurrentUser) -> ReceiptOut:
    _role(current, READ_ROLES)
    receipt = payments.fetch_receipt(db, receipt_id)
    if receipt is None:
        raise HTTPException(404, "Receipt not found")
    # Scope via linked invoice
    _invoice(db, current, receipt["invoice_id"])
    return ReceiptOut.model_validate(receipt)


@router.get("")
def list_receipts(
    db: Db, current: CurrentUser,
    invoice_id: UUID | None = None,
    customer_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[ReceiptOut]:
    _role(current, READ_ROLES)
    branches = _scope_branches(db, current)
    rows = payments.list_receipts(
        db, invoice_id=invoice_id, customer_id=customer_id,
        branch_id=branches, date_from=date_from, date_to=date_to
    )
    return [ReceiptOut.model_validate(r) for r in rows]


@router.post("", status_code=201)
def create_receipt(payload: ReceiptIn, request: Request, db: Db, current: CurrentUser) -> ReceiptOut:
    _role(current, WRITE_ROLES)
    if not POSTING_ENABLED:
        raise HTTPException(
            409,
            "Collections disabled until posting can be updated atomically",
        )

    # Lock and validate the target invoice
    invoice = _invoice(db, current, payload.invoice_id, lock=True)
    if invoice["posting_status"] != "Posted":
        raise HTTPException(409, "Only Posted invoices accept collections")
    if invoice["version"] != payload.invoice_version:
        raise HTTPException(409, "Stale invoice version; reload before collecting")

    # Check overpayment
    paid = payments._sum_active_receipts(db, payload.invoice_id)
    if paid + payload.amount > invoice["grand_total"]:
        raise HTTPException(409, "Overpayment: amount exceeds outstanding balance")

    # Receipt no uniqueness enforced by DB constraint
    try:
        receipt_id = payments.create_receipt(
            db,
            invoice_id=payload.invoice_id,
            branch_id=invoice["branch_id"],
            customer_id=invoice["customer_id"],
            receipt_no=payload.receipt_no,
            receipt_date=payload.receipt_date,
            amount=payload.amount,
            method=payload.method,
            note=payload.note,
            actor_id=current["id"],
        )
    except IntegrityError as error:
        db.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_receipt_branch_no":
            raise HTTPException(409, "Receipt number already exists in this branch") from error
        raise HTTPException(422, "Receipt violates a database reference or value constraint") from error

    receipt = payments.fetch_receipt(db, receipt_id)
    _audit(db, request, current, "created", None, receipt)
    db.commit()
    return ReceiptOut.model_validate(receipt)


@router.post("/{receipt_id}/void")
def void_receipt(
    receipt_id: UUID, payload: ReceiptVoidIn, request: Request, db: Db, current: CurrentUser
) -> ReceiptOut:
    _role(current, WRITE_ROLES)
    if not POSTING_ENABLED:
        raise HTTPException(
            409,
            "Collections disabled until posting can be updated atomically",
        )

    # Validate active void reason
    reason = db.execute(
        text(
            "SELECT 1 FROM audit.reason_code WHERE id=:id AND is_active AND category IN ('void','reversal') FOR SHARE"
        ),
        {"id": payload.reason_id},
    ).scalar()
    if not reason:
        raise HTTPException(422, "An active void/reversal reason code is required")

    try:
        old = payments.fetch_receipt(db, receipt_id, lock=True)
        if old is None:
            raise HTTPException(404, "Receipt not found")
        if old["status"] != "Active":
            raise HTTPException(409, "Only Active receipts can be voided")
        if old["version"] != payload.version:
            raise HTTPException(409, "Stale receipt version; reload before voiding")

        # Scope via linked invoice
        _invoice(db, current, old["invoice_id"])

        receipt = payments.void_receipt(db, receipt_id, current["id"], payload.reason_id)
        _audit(db, request, current, "voided", old, receipt)
        db.commit()
        return ReceiptOut.model_validate(receipt)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(422, "Receipt void violates a database constraint") from error
    except Exception:
        db.rollback()
        raise


def _audit(db, request, user, action, old, new):
    host = _host(request)

    def _serializable(obj):
        if obj is None:
            return None
        if hasattr(obj, "model_dump"):
            obj = obj.model_dump(mode="json")
        if isinstance(obj, dict):
            return {
                k: (str(v) if isinstance(v, (UUID, date, datetime, Decimal)) else v)
                for k, v in obj.items()
            }
        return obj

    log_audit(
        db,
        user["id"],
        action,
        "payment_receipt",
        new["id"],
        _serializable(old),
        _serializable(new),
        host,
        request.headers.get("user-agent", "")[:1000],
    )