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


def lock_user_administration(db, actor_id, target_id):
    # Serialize owner invariants without a migration; row locks also fence login.
    db.execute(text("LOCK TABLE platform.platform_user IN SHARE ROW EXCLUSIVE MODE"))
    db.execute(
        text(
            "SELECT id FROM platform.platform_user "
            "WHERE id IN (:actor, :target) ORDER BY id FOR UPDATE"
        ),
        {"actor": str(actor_id), "target": str(target_id)},
    ).fetchall()


def administration_users(db, user_id=None):
    rows = (
        db.execute(
            text(
                "SELECT u.id, u.username, u.role, u.is_owner, u.is_active, "
                "ARRAY(SELECT ub.branch_id FROM platform.user_branch ub "
                "WHERE ub.user_id=u.id ORDER BY ub.branch_id) AS branch_ids "
                "FROM platform.platform_user u "
                + ("WHERE u.id=:uid " if user_id is not None else "")
                + "ORDER BY u.username, u.id"
            ),
            {"uid": str(user_id)} if user_id is not None else {},
        )
        .mappings()
        .all()
    )
    return [
        {
            "id": str(row["id"]),
            "username": row["username"],
            "role": row["role"],
            "is_owner": bool(row["is_owner"]),
            "is_active": bool(row["is_active"]),
            "branch_ids": [str(value) for value in row["branch_ids"]],
        }
        for row in rows
    ]


def administration_branches(db, branch_ids):
    return {
        str(row[0])
        for row in db.execute(
            text(
                "SELECT id FROM master_data.master_branch "
                "WHERE id=ANY(CAST(:ids AS uuid[])) FOR KEY SHARE"
            ),
            {"ids": branch_ids},
        ).fetchall()
    }


def active_owner_count(db):
    return db.execute(
        text("SELECT count(*) FROM platform.platform_user WHERE is_owner AND is_active")
    ).scalar_one()


def write_user_administration(db, user_id, role, is_active, branch_ids):
    params = {"uid": str(user_id), "role": role, "active": is_active}
    db.execute(
        text(
            "UPDATE platform.platform_user SET role=:role, is_active=:active, "
            "updated_at=now() WHERE id=:uid"
        ),
        params,
    )
    db.execute(
        text("DELETE FROM platform.user_branch WHERE user_id=:uid"),
        {"uid": str(user_id)},
    )
    for branch_id in branch_ids:
        db.execute(
            text(
                "INSERT INTO platform.user_branch (user_id, branch_id) "
                "VALUES (:uid, :bid)"
            ),
            {"uid": str(user_id), "bid": branch_id},
        )
    # Roles have no approved ordering: revoke on every effective access change.
    db.execute(
        text("DELETE FROM platform.platform_session WHERE user_id=:uid"),
        {"uid": str(user_id)},
    )


def get_user_by_username(db, username, *, lock=False):
    row = db.execute(
        text(
            "SELECT id, username, password_hash, first_name, last_name, "
            "role, is_owner, is_active FROM platform.platform_user "
            "WHERE username = :u" + (" FOR UPDATE" if lock else "")
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
