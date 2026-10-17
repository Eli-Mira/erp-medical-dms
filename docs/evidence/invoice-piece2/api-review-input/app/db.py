"""Shared database wiring for the Medical Company System API.

Reads DATABASE_URL from the environment so the same code runs in Docker
(services compose DB_HOST=db) and locally (localhost). Dev default kept
in sync with docker-compose / .env.dev.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://dms:dms-dev@localhost:5432/medical_dms",
)
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
