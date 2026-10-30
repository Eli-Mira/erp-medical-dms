"""Authentication + session endpoints (P2.4 + P2.6 audit).

Session token == platform_session.id (UUID), stateful in DB (§2). No schema
columns invented: the session PK carries the token. Logout deletes the row.
"""
import datetime
import uuid as uuidlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from . import repo

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer()


class UserAdministrationIn(BaseModel):
    model_config = {"extra": "forbid"}

    role: str
    is_active: bool
    branch_ids: list[uuidlib.UUID]


class UserAdministrationOut(BaseModel):
    id: str
    username: str
    role: str
    is_owner: bool
    is_active: bool
    branch_ids: list[str]


async def _administration_payload(request: Request):
    # Strict JSON mode accepts UUID strings, not coerced booleans or extra fields.
    from pydantic import ValidationError

    try:
        payload = UserAdministrationIn.model_validate_json(
            await request.body(), strict=True
        )
    except ValidationError:
        # Never echo rejected credentials or forged actor fields.
        raise HTTPException(422, "Invalid user administration payload") from None
    if len(payload.branch_ids) > 500 or len(set(payload.branch_ids)) != len(
        payload.branch_ids
    ):
        raise HTTPException(422, "Invalid branch assignments")
    return payload


def _administration_owner(current):
    # Preserve the existing require_owner boundary: is_owner, not a role grant.
    if not current["is_active"] or not current["is_owner"]:
        raise HTTPException(403, "owner-only")


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: str
    username: str
    role: str
    is_owner: bool


def _parse_uuid(token: str):
    try:
        return uuidlib.UUID(token)
    except Exception:
        return None


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db=Depends(get_db),
):
    sid = _parse_uuid(creds.credentials)
    if sid is None:
        raise HTTPException(status_code=401, detail="invalid session token")
    session = repo.get_session(db, sid)
    if not session or session["expires_at"] < datetime.datetime.now(datetime.timezone.utc):
        raise HTTPException(status_code=401, detail="session expired")
    user = repo.get_user_by_id(db, session["user_id"])
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="user inactive or not found")
    return user


AdministrationUser = Annotated[dict, Depends(get_current_user)]
AdministrationDb = Annotated[Session, Depends(get_db)]
AdministrationPayload = Annotated[UserAdministrationIn, Depends(_administration_payload)]
AdministrationCredentials = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]


@router.post("/login", response_model=LoginOut)
def login(request: Request, payload: LoginIn, db=Depends(get_db)):
    from .security import verify_password

    # Serialize session issuance with administration and session revocation.
    user = repo.get_user_by_username(db, payload.username, lock=True)
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="invalid credentials")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    import ipaddress

    ip = request.client.host if request.client else None
    if ip:
        try:  # inet column rejects non-IP host strings (e.g. TestClient "testclient")
            ipaddress.ip_address(ip)
        except ValueError:
            ip = None
    sid = repo.create_session(db, user["id"], ip)
    repo.log_audit(db, user["id"], "login", "platform_session", sid, None, {"ip": ip})
    db.commit()
    return LoginOut(access_token=str(sid))


@router.post("/logout")
def logout(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme), db=Depends(get_db)
):
    sid = _parse_uuid(creds.credentials)
    if sid:
        session = repo.get_session(db, sid)
        if session:
            repo.log_audit(db, session["user_id"], "logout", "platform_session", sid, None, None)
            repo.delete_session(db, sid)
            db.commit()
    return {"ok": True}


@router.get("/users", response_model=list[UserAdministrationOut])
def list_administration_users(current: AdministrationUser, db: AdministrationDb):
    _administration_owner(current)
    return [
        UserAdministrationOut.model_validate(row)
        for row in repo.administration_users(db)
    ]


@router.get("/users/options")
def administration_options(current: AdministrationUser, db: AdministrationDb):
    from sqlalchemy import text

    from .rbac import ROLES

    _administration_owner(current)
    branches = (
        db.execute(
            text(
                "SELECT id, code, name_ar, name_en FROM master_data.master_branch ORDER BY code, id"
            )
        )
        .mappings()
        .all()
    )
    return {
        "roles": list(ROLES),
        "branches": [
            {
                "id": str(row["id"]),
                "code": row["code"],
                "name_ar": row["name_ar"],
                "name_en": row["name_en"],
            }
            for row in branches
        ],
    }


@router.put("/users/{user_id}", response_model=UserAdministrationOut)
def administer_user(
    user_id: uuidlib.UUID,
    request: Request,
    payload: AdministrationPayload,
    current: AdministrationUser,
    creds: AdministrationCredentials,
    db: AdministrationDb,
):
    from sqlalchemy.exc import IntegrityError

    from .rbac import ROLES

    _administration_owner(current)
    try:
        repo.lock_user_administration(db, current["id"], user_id)
        # Dependencies may have run before another owner revoked this session.
        actor = get_current_user(request, creds, db)
        _administration_owner(actor)
        rows = repo.administration_users(db, user_id)
        if not rows:
            raise HTTPException(404, "User not found")
        before = rows[0]
        if payload.role not in ROLES:
            raise HTTPException(422, "Unknown role")
        if payload.role == "owner" and not before["is_owner"]:
            raise HTTPException(422, "Owner status cannot be granted here")
        branches = sorted(str(value) for value in payload.branch_ids)
        if repo.administration_branches(db, branches) != set(branches):
            raise HTTPException(422, "Invalid branch assignments")
        after = {
            **before,
            "role": payload.role,
            "is_active": payload.is_active,
            "branch_ids": branches,
        }
        response = UserAdministrationOut.model_validate(after)
        if before == after:
            db.rollback()
            return response
        if str(actor["id"]) == str(user_id) and (
            before["role"] != after["role"]
            or not after["is_active"]
            or not set(before["branch_ids"]).issubset(branches)
        ):
            raise HTTPException(409, "Self-lockout is forbidden")
        if (
            before["is_owner"]
            and before["is_active"]
            and not after["is_active"]
            and repo.active_owner_count(db) <= 1
        ):
            raise HTTPException(409, "The last active owner must remain active")
        repo.write_user_administration(
            db, user_id, payload.role, payload.is_active, branches
        )
        repo.log_audit(
            db,
            actor["id"],
            "updated",
            "platform_user",
            user_id,
            before,
            response.model_dump(mode="json"),
        )
        db.commit()
        return response
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "User administration conflict") from None
    except Exception:
        db.rollback()
        raise


@router.get("/me", response_model=MeOut)
def me(current=Depends(get_current_user)):
    return MeOut(
        id=str(current["id"]),
        username=current["username"],
        role=current["role"],
        is_owner=bool(current["is_owner"]),
    )
