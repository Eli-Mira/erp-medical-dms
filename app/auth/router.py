"""Authentication + session endpoints (P2.4 + P2.6 audit).

Session token == platform_session.id (UUID), stateful in DB (§2). No schema
columns invented: the session PK carries the token. Logout deletes the row.
"""
import datetime
import uuid as uuidlib

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..db import get_db
from . import repo

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer()


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
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user


@router.post("/login", response_model=LoginOut)
def login(request: Request, payload: LoginIn, db=Depends(get_db)):
    from .security import verify_password

    user = repo.get_user_by_username(db, payload.username)
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


@router.get("/me", response_model=MeOut)
def me(current=Depends(get_current_user)):
    return MeOut(
        id=str(current["id"]),
        username=current["username"],
        role=current["role"],
        is_owner=bool(current["is_owner"]),
    )
