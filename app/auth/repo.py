"""Data access for platform users, sessions, and the audit log.

All column sets match DATABASE_SCHEMA.md exactly (§2 platform, §10 audit).
Uses raw SQL via Core text() to avoid any schema/type drift.
"""
import datetime
import uuid

from sqlalchemy import text

from .security import hash_password  # re-exported for convenience
from ..db import SessionLocal

SESSION_TTL = datetime.timedelta(hours=24)


def get_user_by_username(db, username):
    row = db.execute(
        text(
            "SELECT id, username, password_hash, first_name, last_name, "
            "role, is_owner, is_active FROM platform.platform_user "
            "WHERE username = :u"
        ),
        {"u": username},
    ).fetchone()
    return row._mapping if row else None


def get_user_by_id(db, uid):
    row = db.execute(
        text(
            "SELECT id, username, password_hash, first_name, last_name, "
            "role, is_owner, is_active FROM platform.platform_user "
            "WHERE id = :uid"
        ),
        {"uid": str(uid)},
    ).fetchone()
    return row._mapping if row else None


def create_user(db, username, password, role="user", is_owner=False):
    db.execute(
        text(
            "INSERT INTO platform.platform_user "
            "(id, username, password_hash, role, is_owner, is_active, "
            "created_at, updated_at) "
            "VALUES (gen_random_uuid(), :u, :p, :role, :owner, true, now(), now())"
        ),
        {"u": username, "p": hash_password(password), "role": role, "owner": is_owner},
    )


def create_session(db, user_id, ip_address=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    row = db.execute(
        text(
            "INSERT INTO platform.platform_session "
            "(id, user_id, device_info, ip_address, created_at, expires_at) "
            "VALUES (gen_random_uuid(), :uid, :dev, :ip, :now, :exp) RETURNING id"
        ),
        {
            "uid": str(user_id),
            "dev": "api",
            "ip": ip_address,
            "now": now,
            "exp": now + SESSION_TTL,
        },
    ).fetchone()
    return row[0]


def get_session(db, sid):
    row = db.execute(
        text(
            "SELECT id, user_id, ip_address, created_at, expires_at "
            "FROM platform.platform_session WHERE id = :s"
        ),
        {"s": str(sid)},
    ).fetchone()
    return row._mapping if row else None


def delete_session(db, sid):
    db.execute(
        text("DELETE FROM platform.platform_session WHERE id = :s"),
        {"s": str(sid)},
    )


def log_audit(db, actor_user_id, action, entity_type, entity_id,
              old_values, new_values, ip_address=None, user_agent=None):
    """Immutable audit row (audit.audit_log — NO DELETE per §10)."""
    import json
    db.execute(
        text(
            "INSERT INTO audit.audit_log "
            "(id, actor_user_id, action, entity_type, entity_id, "
            "old_values, new_values, ip_address, user_agent, created_at) "
            "VALUES (gen_random_uuid(), :actor, :action, :et, :eid, "
            ":ov, :nv, :ip, :ua, now())"
        ),
        {
            "actor": str(actor_user_id) if actor_user_id else None,
            "action": action,
            "et": entity_type,
            "eid": str(entity_id) if entity_id else None,
            "ov": json.dumps(old_values) if old_values is not None else None,
            "nv": json.dumps(new_values) if new_values is not None else None,
            "ip": ip_address,
            "ua": user_agent,
        },
    )
