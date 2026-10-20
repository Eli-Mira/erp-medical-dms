from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

try:
    from app.alembic_targeting import (
        resolve_alembic_target,
        verify_connected_database,
    )
except (ImportError, ModuleNotFoundError):  # pragma: no cover - supports direct alembic execution
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.alembic_targeting import (
        resolve_alembic_target,
        verify_connected_database,
    )

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _config_url() -> str | None:
    try:
        return config.get_main_option("sqlalchemy.url")
    except (KeyError, ValueError):
        return None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = resolve_alembic_target(_config_url())
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configured_url = _config_url()
    target_url = resolve_alembic_target(configured_url)
    from sqlalchemy.engine.url import make_url

    expected_database = make_url(target_url).database

    connectable = create_engine(target_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # Preflight on the same connection; migrations and revision tracking are
        # committed by Alembic's transaction below. Re-check through a fresh
        # connection after command completion in tests/verification.
        verify_connected_database(connection, expected_database)
        # The preflight SELECT above can leave an open transaction on some
        # drivers. Close it so Alembic owns the migration transaction.
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
