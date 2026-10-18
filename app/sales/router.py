"""Draft-only invoices. Posting is guarded in the API and the database."""

import ipaddress
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.config import POSTING_ENABLED
from app.db import get_db
from app.inventory.service import InsufficientStock
from app.sales import repo, service
from app.sales.calc import invoice_totals, line_calc
from app.sales.schemas import DraftIn, DraftUpdate, InvoiceListOut, InvoiceOut, VoidIn

router = APIRouter(prefix="/invoices", tags=["invoices"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
INVOICE_ROLES = {
    "owner",
    "finance",
    "sales_manager",
    "district_manager",
    "medical_rep",
    "read_only_auditor",
}


def _role(user):
    role = user["role"]
    if (
        not user["is_active"]
        or role not in INVOICE_ROLES
        or (role == "owner" and not user["is_owner"])
    ):
        raise HTTPException(403, "Invoice access denied")
    return role


def _scope(db, user, territory_id):
    if _role(user) == "owner":
        return
    assigned = db.execute(
        text(
            "SELECT 1 FROM platform.user_territory WHERE user_id=:uid AND territory_id=:tid"
        ),
        {"uid": user["id"], "tid": territory_id},
    ).scalar()
    if not assigned:
        raise HTTPException(404, "Invoice or reference not found")


def _invoice(db, user, invoice_id, *, lock=False):
    role = _role(user)
    invoice = repo.fetch_invoice(db, invoice_id, lock=lock)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    _scope(db, user, invoice["territory_id"])
    if role == "medical_rep" and invoice["created_by"] != user["id"]:
        raise HTTPException(404, "Invoice not found")
    if role == "read_only_auditor" and invoice["posted_at"] is None:
        raise HTTPException(404, "Invoice not found")
    return invoice


# Roles that may reference any warehouse (no per-warehouse filtering).
GLOBAL_WAREHOUSE_ROLES = {"owner", "finance", "warehouse_staff", "read_only_auditor"}


def _warehouse_scope(db, user):
    """Active warehouses the caller may reference; None means global.

    Explicit platform.user_branch grants joined to master_warehouse.branch_id.
    Fulfillment routes (inventory.branch_warehouse) never grant access here.
    """
    role = user["role"]
    if role in GLOBAL_WAREHOUSE_ROLES:
        return None
    rows = db.execute(
        text(
            "SELECT w.id FROM platform.user_branch ub "
            "JOIN master_data.master_warehouse w ON w.branch_id = ub.branch_id "
            "WHERE ub.user_id = :uid AND w.is_active"
        ),
        {"uid": user["id"]},
    ).fetchall()
    warehouses = {r[0] for r in rows}
    if not warehouses:
        raise HTTPException(404, "Warehouse not found")
    return warehouses


def _prepare(db, user, payload):
    role = _role(user)
    if role == "read_only_auditor":
        raise HTTPException(403, "Read-only role")
    customer = (
        db.execute(
            text("SELECT * FROM master_data.master_customer WHERE id=:id FOR SHARE"),
            {"id": payload.customer_id},
        )
        .mappings()
        .one_or_none()
    )
    if (
        customer is None
        or not customer["is_active"]
        or customer["territory_id"] is None
    ):
        raise HTTPException(
            422, "Customer must be active and have an assigned territory"
        )
    _scope(db, user, customer["territory_id"])
    if customer["branch_id"] != payload.branch_id:
        raise HTTPException(422, "Customer does not belong to invoice branch")
    warehouse = (
        db.execute(
            text("SELECT * FROM master_data.master_warehouse WHERE id=:id FOR SHARE"),
            {"id": payload.warehouse_id},
        )
        .mappings()
        .one_or_none()
    )
    if warehouse is None or not warehouse["is_active"]:
        raise HTTPException(404, "Warehouse not found")
    scope = _warehouse_scope(db, user)
    if scope is not None and payload.warehouse_id not in scope:
        raise HTTPException(404, "Warehouse not found")
    if warehouse["branch_id"] != payload.branch_id:
        route = db.execute(
            text(
                "SELECT 1 FROM inventory.branch_warehouse "
                "WHERE branch_id = :b AND warehouse_id = :w"
            ),
            {"b": payload.branch_id, "w": payload.warehouse_id},
        ).scalar()
        if not route:
            raise HTTPException(
                422, "Source warehouse is not served to this sales territory"
            )
    lines, calculations = [], []
    for position, line in enumerate(payload.lines, 1):
        product = (
            db.execute(
                text("SELECT * FROM master_data.master_product WHERE id=:id FOR SHARE"),
                {"id": line.product_id},
            )
            .mappings()
            .one_or_none()
        )
        if product is None or not product["is_active"]:
            raise HTTPException(422, "Product must be active")
        if line.batch_id:
            batch = (
                db.execute(
                    text("SELECT * FROM inventory.batch_record WHERE id=:id FOR SHARE"),
                    {"id": line.batch_id},
                )
                .mappings()
                .one_or_none()
            )
            if (
                batch is None
                or batch["product_id"] != line.product_id
                or batch["warehouse_id"] != payload.warehouse_id
            ):
                raise HTTPException(
                    422, "Batch does not match product and source warehouse"
                )
            if batch["expiry_date"] < payload.invoice_date:
                raise HTTPException(422, "Batch expires before invoice date")
        price = product["base_price"] if line.unit_price is None else line.unit_price
        if price != product["base_price"] and role not in {"owner", "finance"}:
            raise HTTPException(403, "Price override requires Owner or Finance")
        rate = product["vat_rate"]
        net, total, vat = line_calc(line.quantity, price, line.discount_pct, rate)
        calculations.append((line.quantity, price, line.discount_pct, rate))
        lines.append(
            {
                **line.model_dump(),
                "line_no": position,
                "unit_price": price,
                "net_price": net,
                "line_total": total,
                "vat_rate": rate,
                "vat_amount": vat,
            }
        )
    totals = invoice_totals(calculations)
    if any(abs(value) >= 10**12 for value in totals.values()) or any(
        line["line_total"] >= 10**12 for line in lines
    ):
        raise HTTPException(422, "Invoice exceeds supported monetary precision")
    values = payload.model_dump(exclude={"lines", "version"})
    return {
        **values,
        **totals,
        "territory_id": customer["territory_id"],
        "actor": user["id"],
    }, lines


def _posting_references(db, user, invoice):
    """Revalidate grants/references without repricing the saved VAT snapshot."""
    scope = _warehouse_scope(db, user)
    if scope is not None and invoice["warehouse_id"] not in scope:
        raise HTTPException(404, "Warehouse not found")
    warehouse = (
        db.execute(
            text("SELECT * FROM master_data.master_warehouse WHERE id=:id FOR SHARE"),
            {"id": invoice["warehouse_id"]},
        )
        .mappings()
        .one_or_none()
    )
    if warehouse is None or not warehouse["is_active"]:
        raise HTTPException(404, "Warehouse not found")
    if (
        warehouse["branch_id"] != invoice["branch_id"]
        and not db.execute(
            text(
                "SELECT 1 FROM inventory.branch_warehouse WHERE branch_id=:b AND warehouse_id=:w FOR SHARE"
            ),
            {"b": invoice["branch_id"], "w": invoice["warehouse_id"]},
        ).scalar()
    ):
        raise HTTPException(409, "Source warehouse routing has changed")
    customer = (
        db.execute(
            text("SELECT * FROM master_data.master_customer WHERE id=:id FOR SHARE"),
            {"id": invoice["customer_id"]},
        )
        .mappings()
        .one_or_none()
    )
    if (
        customer is None
        or not customer["is_active"]
        or customer["branch_id"] != invoice["branch_id"]
        or customer["territory_id"] != invoice["territory_id"]
    ):
        raise HTTPException(409, "Customer reference or scope has changed")
    for line in invoice["lines"]:
        product = db.execute(
            text(
                "SELECT is_active FROM master_data.master_product WHERE id=:id FOR SHARE"
            ),
            {"id": line["product_id"]},
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(409, "Invoice product is no longer active")
        if line["batch_id"]:
            batch = (
                db.execute(
                    text("SELECT * FROM inventory.batch_record WHERE id=:id FOR SHARE"),
                    {"id": line["batch_id"]},
                )
                .mappings()
                .one_or_none()
            )
            if (
                batch is None
                or batch["product_id"] != line["product_id"]
                or batch["warehouse_id"] != invoice["warehouse_id"]
                or batch["expiry_date"] < invoice["invoice_date"]
            ):
                raise HTTPException(409, "Invoice batch reference has changed")


def _audit(db, request, user, action, old, new):
    host = request.client.host if request.client else None
    try:
        host = str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        host = None
    log_audit(
        db,
        user["id"],
        action,
        "sales_invoice",
        new.id,
        InvoiceOut.model_validate(old).model_dump(mode="json") if old else None,
        new.model_dump(mode="json"),
        host,
        request.headers.get("user-agent", "")[:1000],
    )


def _integrity_error(db, error):
    db.rollback()
    constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint == "uq_sales_invoice_branch_no":
        raise HTTPException(
            409, "Invoice number already exists in this branch"
        ) from error
    raise HTTPException(
        422, "Invoice violates a database reference or value constraint"
    ) from error


@router.post("", status_code=201)
def create_invoice(
    payload: DraftIn, request: Request, db: Db, current: CurrentUser
) -> InvoiceOut:
    values, lines = _prepare(db, current, payload)
    try:
        invoice_id = repo.insert_invoice(db, values)
        repo.insert_lines(db, invoice_id, lines)
        result = InvoiceOut.model_validate(repo.fetch_invoice(db, invoice_id))
        _audit(db, request, current, "created", None, result)
        db.commit()
        return result
    except IntegrityError as error:
        _integrity_error(db, error)
    except Exception:
        db.rollback()
        raise


@router.get("")
def list_invoices_view(
    db: Db,
    current: CurrentUser,
    customer_id: UUID | None = None,
    status: Literal["Draft", "Posted", "Voided"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> InvoiceListOut:
    role = _role(current)
    territories = created_by = None
    posted_only = False
    if role != "owner":
        territories = [
            row[0]
            for row in db.execute(
                text(
                    "SELECT territory_id FROM platform.user_territory WHERE user_id=:uid"
                ),
                {"uid": current["id"]},
            ).fetchall()
        ]
        if role == "medical_rep":
            created_by = current["id"]
        if role == "read_only_auditor":
            posted_only = True
    items, total = repo.list_invoices(
        db,
        customer_id=customer_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        territories=territories,
        created_by=created_by,
        posted_only=posted_only,
    )
    return InvoiceListOut(items=[InvoiceOut.model_validate(r) for r in items], total=total)


@router.get("/{invoice_id}")
def view_invoice(invoice_id: UUID, db: Db, current: CurrentUser) -> InvoiceOut:
    return InvoiceOut.model_validate(_invoice(db, current, invoice_id))


def _editable(invoice, version):
    if invoice["posting_status"] != "Draft":
        raise HTTPException(
            409, "Only drafts can be changed; posted reversals are disabled"
        )
    if invoice["version"] != version:
        raise HTTPException(409, "Stale invoice version; reload before editing")


@router.put("/{invoice_id}")
def update_invoice(
    invoice_id: UUID,
    payload: DraftUpdate,
    request: Request,
    db: Db,
    current: CurrentUser,
) -> InvoiceOut:
    try:
        old = _invoice(db, current, invoice_id, lock=True)
        _editable(old, payload.version)
        values, lines = _prepare(db, current, payload)
        repo.replace_header(db, invoice_id, values)
        repo.insert_lines(db, invoice_id, lines)
        result = InvoiceOut.model_validate(repo.fetch_invoice(db, invoice_id))
        _audit(db, request, current, "modified", old, result)
        db.commit()
        return result
    except IntegrityError as error:
        _integrity_error(db, error)
    except Exception:
        db.rollback()
        raise


@router.post("/{invoice_id}/post")
def post_invoice(
    invoice_id: UUID, request: Request, db: Db, current: CurrentUser
) -> InvoiceOut:
    if _role(current) not in {"owner", "finance", "sales_manager", "district_manager"}:
        raise HTTPException(403, "Posting permission denied")
    if not POSTING_ENABLED:
        _invoice(db, current, invoice_id)
        raise HTTPException(
            409,
            "Posting disabled until stock and receivables can be updated atomically",
        )

    try:
        old = _invoice(db, current, invoice_id, lock=True)
        if old["posting_status"] != "Draft":
            raise HTTPException(409, "Only a draft can be posted")
        _posting_references(db, current, old)
        result = service.post_invoice_atomic(db, invoice_id, current["id"])
        if result is None:
            raise HTTPException(404, "Invoice not found")
        snapshot = InvoiceOut.model_validate(repo.fetch_invoice(db, invoice_id))
        _audit(db, request, current, "posted", old, snapshot)
        db.commit()
        return snapshot
    except InsufficientStock as error:
        db.rollback()
        raise HTTPException(409, "Insufficient stock for one or more lines") from error
    except ValueError as error:
        db.rollback()
        raise HTTPException(409, str(error)) from error
    except IntegrityError as error:
        _integrity_error(db, error)
    except Exception:
        db.rollback()
        raise


@router.post("/{invoice_id}/void")
def void_invoice(
    invoice_id: UUID, payload: VoidIn, request: Request, db: Db, current: CurrentUser
) -> InvoiceOut:
    if _role(current) not in {"owner", "sales_manager"}:
        raise HTTPException(403, "Void requires Owner or Sales Manager")
    try:
        old = _invoice(db, current, invoice_id, lock=True)
        _editable(old, payload.version)
        reason = db.execute(
            text(
                "SELECT 1 FROM audit.reason_code WHERE id=:id AND is_active AND category='void' FOR SHARE"
            ),
            {"id": payload.reason_id},
        ).scalar()
        if not reason:
            raise HTTPException(422, "An active void reason code is required")
        repo.void_draft(db, invoice_id, current["id"], payload.reason_id)
        result = InvoiceOut.model_validate(repo.fetch_invoice(db, invoice_id))
        _audit(db, request, current, "voided", old, result)
        db.commit()
        return result
    except IntegrityError as error:
        _integrity_error(db, error)
    except Exception:
        db.rollback()
        raise


@router.post("/{invoice_id}/reverse")
def reverse_invoice(
    invoice_id: UUID, payload: VoidIn, request: Request, db: Db, current: CurrentUser
) -> InvoiceOut:
    if _role(current) not in {"owner", "finance"}:
        raise HTTPException(403, "Reversal requires Owner or Finance")
    if not POSTING_ENABLED:
        raise HTTPException(
            409,
            "Reversal disabled until stock and receivables can be updated atomically",
        )

    # Validate active void/reversal reason
    reason = db.execute(
        text(
            "SELECT 1 FROM audit.reason_code WHERE id=:id AND is_active AND category IN ('void','reversal') FOR SHARE"
        ),
        {"id": payload.reason_id},
    ).scalar()
    if not reason:
        raise HTTPException(422, "An active void/reversal reason code is required")

    try:
        old = _invoice(db, current, invoice_id, lock=True)
        if old["posting_status"] != "Posted":
            raise HTTPException(409, "Only Posted invoices can be reversed")
        if old["version"] != payload.version:
            raise HTTPException(409, "Stale invoice version; reload before reversing")

        result = service.reverse_invoice_atomic(
            db, invoice_id, current["id"], payload.reason_id
        )
        if result is None:
            raise HTTPException(404, "Invoice not found")

        snapshot = InvoiceOut.model_validate(repo.fetch_invoice(db, invoice_id))
        _audit(db, request, current, "reversed", old, snapshot)
        db.commit()
        return snapshot
    except ValueError as error:
        db.rollback()
        raise HTTPException(409, str(error)) from error
    except IntegrityError as error:
        db.rollback()
        _integrity_error(db, error)
    except Exception:
        db.rollback()
        raise
