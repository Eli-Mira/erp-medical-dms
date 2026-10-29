"""Alembic database-target resolution and verification.

This module keeps migration targeting explicit and safe:

* configuration precedence is defined and conflicts are rejected;
* protected databases (notably ``medical_dms``) are refused for routine work;
* the URL passed to SQLAlchemy is the exact URL that was validated;
* the database reported by PostgreSQL (``current_database()``) is compared with
  the expected name before any migration is allowed to run.

It intentionally does not import ``app.db`` or read ``.env`` files. Callers pass
the configuration URL they want to use.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine.url import make_url

PROTECTED_DATABASES = frozenset({"medical_dms"})
PERMITTED_DISPOSABLE_RE = re.compile(r"^dms_cycle_test_[0-9a-f]{32}$")
# Routine migration targets. ``medical_demo`` is rebuilt from scratch by
# ``scripts/make_demo.py``; ``medical_demo_fresh`` is the persistent seeded demo
# database (``scripts/seed_demo_fresh.py``). Both are local, synthetic-only.
# ``medical_dms`` is protected and is never a permitted target.
DEFAULT_ALLOWED_DATABASES = frozenset({"medical_demo", "medical_demo_fresh"})

EXPLICIT_URL_ENV_VARS = ("ALEMBIC_DATABASE_URL", "TARGET_DB_URL")
EXPLICIT_NAME_ENV_VARS = ("TARGET_DB", "ALEMBIC_TARGET_DB", "ALEMBIC_TARGET_DATABASE")
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class TargetingError(ValueError):
    """Raised when a migration target cannot be resolved safely."""


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def _normalize_url(value: str) -> str:
    return make_url(value).render_as_string(hide_password=False)


def _extract_database_name(value: str) -> str:
    return make_url(value).database or ""


def _permitted_name(name: str, *, allowed_databases: set[str] | None = None) -> bool:
    if name in PROTECTED_DATABASES:
        return False
    if allowed_databases is None:
        allowed = set(DEFAULT_ALLOWED_DATABASES)
    else:
        allowed = set(allowed_databases)
    if name in allowed:
        return True
    return bool(PERMITTED_DISPOSABLE_RE.fullmatch(name))


def validate_target_url(
    url: str,
    *,
    allowed_databases: set[str] | None = None,
    local_hosts: set[str] | None = None,
) -> str:
    """Validate and return the canonical form of a SQLAlchemy URL."""
    try:
        parsed = make_url(url)
    except Exception as exc:  # pragma: no cover - make_url raises various types
        raise TargetingError(f"invalid database URL: {exc}") from exc

    hosts = LOCAL_HOSTS if local_hosts is None else local_hosts
    if parsed.host not in hosts:
        raise TargetingError(
            f"database host {parsed.host!r} is not a permitted local host"
        )
    if not parsed.database:
        raise TargetingError("database URL does not name a database")

    name = parsed.database
    if name in PROTECTED_DATABASES:
        raise TargetingError(
            f"refusing protected database {name!r} for routine migrations"
        )
    if not _permitted_name(name, allowed_databases=allowed_databases):
        raise TargetingError(
            f"database {name!r} is not an approved migration target "
            "(use dms_cycle_test_<32 hex>, medical_demo, or an explicitly "
            "allowed database)"
        )
    return parsed.render_as_string(hide_password=False)


def resolve_target_url(
    config_url: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    allowed_databases: set[str] | None = None,
) -> str:
    """Resolve a migration URL using explicit, documented precedence.

    Precedence:
    1. Explicit full-URL environment variables.
    2. Explicit database-name environment variables (combined with config_url).
    3. The supplied configuration URL (for example alembic.ini).

    Conflicting explicit targets are rejected rather than silently chosen.
    """
    environment = _env(env)

    explicit_urls = {
        name: environment[name]
        for name in EXPLICIT_URL_ENV_VARS
        if environment.get(name)
    }
    if len(explicit_urls) > 1:
        normalized = {_normalize_url(value) for value in explicit_urls.values()}
        if len(normalized) > 1:
            raise TargetingError(
                "conflicting explicit database targets: "
                + ", ".join(
                    f"{name}={make_url(value).render_as_string(hide_password=True)}"
                    for name, value in explicit_urls.items()
                )
            )

    explicit_names = {
        name: environment[name]
        for name in EXPLICIT_NAME_ENV_VARS
        if environment.get(name)
    }
    if len(explicit_names) > 1:
        names = {value for value in explicit_names.values()}
        if len(names) > 1:
            raise TargetingError(
                "conflicting explicit database targets: "
                + ", ".join(f"{name}={value}" for name, value in explicit_names.items())
            )

    if explicit_urls and explicit_names:
        url_value = next(iter(explicit_urls.values()))
        name_value = next(iter(explicit_names.values()))
        if _extract_database_name(url_value) != name_value:
            raise TargetingError(
                "conflicting explicit database targets: "
                f"URL names {_extract_database_name(url_value)!r}, "
                f"TARGET_DB names {name_value!r}"
            )

    if explicit_urls:
        candidate = next(iter(explicit_urls.values()))
    elif explicit_names:
        if config_url is None:
            raise TargetingError(
                "TARGET_DB requires a configuration URL to provide host and credentials"
            )
        name = next(iter(explicit_names.values()))
        parsed = make_url(config_url)
        candidate = parsed.set(database=name).render_as_string(hide_password=False)
    elif config_url is not None:
        candidate = config_url
    else:
        raise TargetingError("missing database configuration for Alembic target")

    return validate_target_url(
        candidate, allowed_databases=allowed_databases
    )


def verify_connected_database(connection: Any, expected_database: str) -> str:
    """Compare PostgreSQL's current_database() with the exact expected name."""
    actual = connection.execute(text("SELECT current_database()")).scalar_one()
    if actual != expected_database:
        raise TargetingError(
            f"connected database {actual!r} does not match expected "
            f"{expected_database!r}"
        )
    return str(actual)


# Compatibility aliases for tests and callers that use shorter names.
resolve_database_url = resolve_target_url
validate_database_target = validate_target_url
verify_connected_db = verify_connected_database
assert_permitted_target = validate_target_url
resolve_alembic_target = resolve_target_url
resolve_alembic_database_url = resolve_target_url


def make_url_database(url: str) -> str:
    return make_url(url).database or ""
