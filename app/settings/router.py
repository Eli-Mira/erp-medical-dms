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

# Same set that may read the invoice pipeline; settings are business policy.
READ_ROLES = {
    "owner", "finance", "sales_manager", "district_manager",
    "medical_rep", "read_only_auditor",
}


def _host(request):
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:


        return None


@router.get("/inventory-policy", response_model=InventoryPolicyOut)
def read_inventory_policy(db: Db, current: CurrentUser) -> InventoryPolicyOut:
    if not current["is_active"] or current["role"] not in READ_ROLES or (
        current["role"] == "owner" and not current["is_owner"]
    ):
        raise HTTPException(403, "Settings access denied")
    return InventoryPolicyOut.model_validate(service.read_policy(db))

@router.put("/inventory-policy", response_model=InventoryPolicyOut)
def write_inventory_policy(
    payload: InventoryPolicyIn, request: Request, db: Db, current: CurrentUser
) -> InventoryPolicyOut:
    if not current["is_active"] or current["role"] != "owner" or not current["is_owner"]:
        raise HTTPException(403, "Owner only")
    old = service.read_policy(db)
    service.write_policy(db, current["id"], payload.stock_cover_window_days,
                         payload.overstock_threshold_days)
    log_audit(db, current["id"], "settings_changed", "platform_setting",
              None, old, service.read_policy(db),
              ip_address=_host(request),
              user_agent=request.headers.get("user-agent"))
    db.commit()
    return InventoryPolicyOut.model_validate(service.read_policy(db))
