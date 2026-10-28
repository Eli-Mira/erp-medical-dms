"""Audit read API: owner/finance reads; never a write (audit is append-only)."""
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.db import get_db

router = APIRouter(prefix="/audit", tags=["audit"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]

READ_ROLES = {"owner", "finance", "read_only_auditor"}


def _role(user, allowed):
    role = user["role"]
    if not user["is_active"] or role not in allowed or (role == "owner" and not user["is_owner"]):
        raise HTTPException(403, "Audit access denied")
    return role


@router.get("")
def list_audit(db: Db, current: CurrentUser, entity_type: str | None = None,
               actor_id: UUID | None = None, action: str | None = None,
               date_from: date | None = None, date_to: date | None = None,
               limit: int = 50, offset: int = 0):
    _role(current, READ_ROLES)
    conditions, params = [], {"limit": limit, "offset": offset}
    if entity_type is not None:
        conditions.append("a.entity_type = :entity_type")
        params["entity_type"] = entity_type
    if actor_id is not None:
        conditions.append("a.actor_user_id = :actor_id")
        params["actor_id"] = actor_id
    if action is not None:
        conditions.append("a.action = :action")
        params["action"] = action
    if date_from is not None:
        conditions.append("a.created_at >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        conditions.append("a.created_at < :date_to")
        params["date_to"] = date_to
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = db.execute(
        text("""SELECT a.id, a.actor_user_id, a.action, a.entity_type,
                       a.entity_id, a.old_values, a.new_values, a.created_at
                FROM audit.audit_log a""" + where +
             " ORDER BY a.created_at DESC LIMIT :limit OFFSET :offset"),
        params,
    ).mappings()
    return [dict(row) for row in rows]
