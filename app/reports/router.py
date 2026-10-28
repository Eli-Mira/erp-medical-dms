"""Read-only management-summary endpoint with role-scoped figures."""

import ipaddress
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.reports import service
from app.reports.schemas import ManagementSummaryOut

router = APIRouter(prefix="/reports", tags=["reports"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

# Management figures are a management view: reps and warehouse staff have
# their own scoped screens; auditors read everything (PRD role matrix).
READ_ROLES = service.GLOBAL_ROLES | service.SCOPED_ROLES


def _role(user):
    role = user["role"]
    if (
        not user["is_active"]
        or role not in READ_ROLES
        or (role == "owner" and not user["is_owner"])
    ):
        raise HTTPException(403, "Management report access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@router.get("/management-summary", response_model=ManagementSummaryOut)
def management_summary_view(
    db: Db,
    current: CurrentUser,
    request: Request,
    as_of: date | None = None,
) -> ManagementSummaryOut:
    """Posted-only sales/collections/AR/alerts figures as of a date."""
    _role(current)
    try:
        summary = service.management_summary(
            db, current, as_of or datetime.now(UTC).astimezone().date()
        )
        response = ManagementSummaryOut.model_validate(summary)
        log_audit(
            db,
            current["id"],
            "viewed",
            "management_summary",
            None,
            None,
            {"as_of": summary["as_of"].isoformat()},
            ip_address=_host(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise
