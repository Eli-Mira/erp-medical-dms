"""Settings API: configurable business-policy values with owner-only writes."""
import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.repo import log_audit
from app.auth.router import get_current_user
from app.db import get_db
from app.settings import service
from app.settings.schemas import InventoryPolicyIn, InventoryPolicyOut

router = APIRouter(prefix="/settings", tags=["settings"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

# Settings are management/business policy; not readable by gate reps.
READ_ROLES = {
    "owner", "finance", "sales_manager", "district_manager", "read_only_auditor",
}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Settings access denied")
    return role


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@router.get("/inventory-policy", response_model=InventoryPolicyOut)
def read_inventory_policy(db: Db, current: CurrentUser) -> InventoryPolicyOut:
    _role(current, READ_ROLES)
    return InventoryPolicyOut.model_validate(service.read_policy(db))


@router.put("/inventory-policy", response_model=InventoryPolicyOut)
def write_inventory_policy(
    payload: InventoryPolicyIn, request: Request, db: Db, current: CurrentUser
) -> InventoryPolicyOut:
    # _role enforces role=="owner" AND the is_owner private-boundary flag (D10).
    _role(current, {"owner"})
    old = service.read_policy(db)
    service.write_policy(db, current["id"], payload.stock_cover_window_days,
                         payload.overstock_threshold_days)
    new = {"stock_cover_window_days": payload.stock_cover_window_days,
           "overstock_threshold_days": payload.overstock_threshold_days}
    log_audit(db, current["id"], "settings_changed", "platform_setting",
              None, old, new,
              ip_address=_host(request),
              user_agent=request.headers.get("user-agent"))
    db.commit()
    return InventoryPolicyOut.model_validate(new)
