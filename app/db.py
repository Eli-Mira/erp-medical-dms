"""Shared database wiring for the Medical Company System API.

Requires DATABASE_URL from the environment; no default database or credential.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")
_DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))
_DB_MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW", "20"))
_DB_POOL_TIMEOUT = int(os.environ.get("DB_POOL_TIMEOUT", "30"))
_DB_STATEMENT_TIMEOUT_MS = int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "30000"))
_DB_LOCK_TIMEOUT_MS = int(os.environ.get("DB_LOCK_TIMEOUT_MS", "5000"))
_connect_args = (
    {"options": f"-c statement_timeout={_DB_STATEMENT_TIMEOUT_MS} -c lock_timeout={_DB_LOCK_TIMEOUT_MS}"}
    if DATABASE_URL.startswith("postgresql")
    else {}
)
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_size=_DB_POOL_SIZE,
    max_overflow=_DB_MAX_OVERFLOW,
    pool_timeout=_DB_POOL_TIMEOUT,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
