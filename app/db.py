"""Shared database wiring for the Medical Company System API.

Requires DATABASE_URL from the environment; no default database or credential.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_timeout=10,
    connect_args={"connect_timeout": 2},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
