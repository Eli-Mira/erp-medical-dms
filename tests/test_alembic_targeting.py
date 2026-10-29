import os

import pytest
from sqlalchemy import create_engine

from app.alembic_targeting import (
    TargetingError,
    resolve_target_url,
    validate_target_url,
    verify_connected_database,
)


def test_missing_configuration_is_rejected():
    with pytest.raises(TargetingError):
        resolve_target_url(None, env={})


def test_medical_dms_is_refused_before_connecting():
    with pytest.raises(TargetingError, match="protected"):
        resolve_target_url(
            "postgresql+psycopg://localhost:5432/medical_dms",
            env={},
        )


def test_explicit_disposable_target_wins():
    env = {"ALEMBIC_DATABASE_URL": "postgresql+psycopg://localhost:5432/dms_cycle_test_" + "a" * 32}
    url = resolve_target_url("postgresql+psycopg://localhost:5432/medical_dms", env=env)
    from sqlalchemy.engine.url import make_url

    assert make_url(url).database == "dms_cycle_test_" + "a" * 32


def test_conflicting_explicit_urls_are_rejected():
    env = {
        "ALEMBIC_DATABASE_URL": "postgresql+psycopg://localhost:5432/dms_cycle_test_" + "a" * 32,
        "TARGET_DB_URL": "postgresql+psycopg://localhost:5432/dms_cycle_test_" + "b" * 32,
    }
    with pytest.raises(TargetingError, match="conflicting"):
        resolve_target_url("postgresql+psycopg://localhost:5432/medical_dms", env=env)


def test_target_db_name_conflicts_with_explicit_url():
    env = {
        "ALEMBIC_DATABASE_URL": "postgresql+psycopg://localhost:5432/dms_cycle_test_" + "a" * 32,
        "TARGET_DB": "dms_cycle_test_" + "b" * 32,
    }
    with pytest.raises(TargetingError, match="conflicting"):
        resolve_target_url("postgresql+psycopg://localhost:5432/medical_dms", env=env)


def test_target_db_name_derives_from_configuration():
    name = "dms_cycle_test_" + "c" * 32
    env = {"TARGET_DB": name}
    url = resolve_target_url("postgresql+psycopg://localhost:5432/medical_dms", env=env)
    from sqlalchemy.engine.url import make_url

    assert make_url(url).database == name


def test_medical_demo_is_allowed():
    url = validate_target_url("postgresql+psycopg://localhost:5432/medical_demo")
    from sqlalchemy.engine.url import make_url

    assert make_url(url).database == "medical_demo"


def test_medical_demo_fresh_is_allowed():
    url = validate_target_url(
        "postgresql+psycopg://localhost:5432/medical_demo_fresh"
    )
    from sqlalchemy.engine.url import make_url

    assert make_url(url).database == "medical_demo_fresh"


def test_unknown_database_is_still_rejected():
    with pytest.raises(TargetingError, match="not an approved migration target"):
        validate_target_url(
            "postgresql+psycopg://localhost:5432/medical_demo_scratch"
        )


def test_connected_database_mismatch_is_rejected():
    class FakeConnection:
        def execute(self, statement):
            class Result:
                def scalar_one(self):
                    return "wrong_database"

            return Result()

    with pytest.raises(TargetingError, match="does not match"):
        verify_connected_database(FakeConnection(), "dms_cycle_test_" + "d" * 32)


def test_connected_database_matches_real_disposable_database():
    db_name = "dms_cycle_test_" + "e" * 32
    base_url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://localhost:5432/postgres"
    )
    base = create_engine(base_url)
    admin_url = base.url.set(database="postgres")
    admin_engine = create_engine(admin_url)
    with admin_engine.connect() as admin:
        admin.execution_options(isolation_level="AUTOCOMMIT")
        admin.exec_driver_sql(f'CREATE DATABASE "{db_name}"')
    try:
        test_url = base.url.set(database=db_name)
        engine = create_engine(test_url)
        with engine.connect() as conn:
            assert verify_connected_database(conn, db_name) == db_name
        engine.dispose()
    finally:
        admin_engine.dispose()
        with create_engine(base.url.set(database="postgres")).connect() as admin:
            admin.execution_options(isolation_level="AUTOCOMMIT")
            admin.exec_driver_sql(f'DROP DATABASE IF EXISTS "{db_name}"')