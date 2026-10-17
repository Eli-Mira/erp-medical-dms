"""RBAC: role matrix + private/owner boundary (D10, P2.5).

Imports get_current_user from app.auth.router. Safe from an import cycle
because main.py registers the auth router before this router:
  from .auth.router import router as auth_router   # defines get_current_user
  from .auth.rbac import rbac_router              # imports it afterwards
"""
from fastapi import APIRouter, Depends, HTTPException

from .router import get_current_user

# Role model mirrors DATABASE_SCHEMA §2 (platform_user.role + is_owner).
ROLES = ("owner", "admin", "finance", "sales_manager", "district_manager",
         "medical_rep", "warehouse_staff", "read_only_auditor")

rbac_router = APIRouter(tags=["owner"])


def require_role(*roles: str):
    """Dependency factory: 403 unless the current user's role is allowed."""
    allowed = {roles} if isinstance(roles, str) else set(roles)

    def _check(current=Depends(get_current_user)):
        if current["role"] not in allowed:
            raise HTTPException(status_code=403, detail="insufficient role")
        return current

    return _check


def require_owner(current=Depends(get_current_user)):
    """D10 private/owner boundary: only is_owner accounts may proceed."""
    if not current["is_owner"]:
        raise HTTPException(status_code=403, detail="owner-only")
    return current


@rbac_router.get("/owner/panel")
def owner_panel(current=Depends(require_owner)):
    return {"panel": "owner", "user": current["username"]}
