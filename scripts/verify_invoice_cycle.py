"""Run invoice-cycle tests only on a fresh synthetic PostgreSQL database."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from alembic import command

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def runner_database_url():
    explicit_url = os.environ.get("DATABASE_URL")
    if not explicit_url:
        raise ValueError("An explicit disposable-verifier DATABASE_URL is required")
    try:
        base = make_url(explicit_url)
        port = base.port
    except (ArgumentError, TypeError, ValueError):
        raise ValueError("Invalid disposable-verifier DATABASE_URL") from None
    if (
        base.drivername != "postgresql+psycopg"
        or base.host not in {"localhost", "127.0.0.1", "::1"}
        or port is None
        or not 1 <= port <= 65535
        or not (
            base.database in {"postgres", "erp_verify"}
            or re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", base.database or "")
        )
        or {"host", "hostaddr", "port", "dbname", "database", "service", "servicefile"}
        & base.query.keys()
    ):
        raise ValueError(
            "Verifier requires an explicit local endpoint, port and verifier database"
        )
    # Port 5432 is private loopback only in the approved container, never on the host.
    if port in {5432, 5434} and not Path("/.dockerenv").is_file():
        raise ValueError(
            "Company host ports 5432/5434 are forbidden; use the approved contained runner"
        )
    return base


def bindings():
    paths = {
        p
        for folder in ("app", "tests", "alembic", "web", "scripts")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    paths.update(
        p
        for pattern in (
            "*.xlsx",
            ".env*",
            "*compose*.yml",
            "Dockerfile",
            "requirements.txt",
        )
        for p in ROOT.glob(pattern)
        if p.is_file()
    )
    result = {}
    for path in sorted(paths):
        with path.open("rb") as source:
            result[path.relative_to(ROOT).as_posix()] = hashlib.file_digest(
                source, "sha256"
            ).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--chain", action="store_true")
    parser.add_argument("tests", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.stage):
        parser.error("stage must be a simple artifact name")
    base = runner_database_url()
    out = ROOT / "docs/evidence/invoice-cycle" / args.stage
    out.mkdir(parents=True, exist_ok=False)
    selectors = args.tests or ["tests/", "-q", "--tb=short"]
    if selectors[0] == "--":
        selectors = selectors[1:]
    # Never migrate/connect to the application database: admin is metadata/CREATE/DROP only.
    name = "dms_cycle_test_" + uuid4().hex
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", name) and name != base.database
    target = base.set(database=name)
    connection_target = {
        "namespace": "disposable-container" if Path("/.dockerenv").is_file() else "host",
        "host": target.host,
        "port": target.port,
        "database": name,
    }
    print("TEST_TARGET " + json.dumps(connection_target, sort_keys=True), flush=True)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    engine = create_engine(target)
    record = {
        "database": name,
        "connection_target": connection_target,
        "created": False,
        "removed": False,
        "configuration": {"APP_ENV": "test", "POSTING_ENABLED": "false"},
        "before": bindings(),
        "steps": [],
        "versions": {
            p: importlib.metadata.version(p)
            for p in ("fastapi", "sqlalchemy", "psycopg", "alembic", "pytest")
        },
    }
    code = 1
    try:
        with admin.connect() as db:
            db.exec_driver_sql(f'CREATE DATABASE "{name}"')
            record["created"] = True
            record["postgresql_version"] = db.exec_driver_sql(
                "SHOW server_version"
            ).scalar_one()
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option(
            "sqlalchemy.url",
            target.render_as_string(hide_password=False).replace("%", "%%"),
        )
        command.upgrade(cfg, "head")
        with engine.connect() as db:
            assert db.exec_driver_sql("SELECT current_database()").scalar_one() == name
            revision = db.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
        record["steps"].append({"action": "fresh-upgrade", "revision": revision})
        if args.chain:
            command.downgrade(cfg, "-1")
            command.upgrade(cfg, "head")
            with engine.connect() as db:
                assert (
                    db.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    ).scalar_one()
                    == revision
                )
            record["steps"].append({"action": "down-one-up-head", "revision": revision})
        env = {
            **os.environ,
            "DATABASE_URL": target.render_as_string(hide_password=False),
            "APP_ENV": "test",
            "POSTING_ENABLED": "false",
            "PYTHONIOENCODING": "utf-8",
        }
        argv = [
            sys.executable,
            "-m",
            "pytest",
            *selectors,
            "--junitxml=" + str(out / "pytest.xml"),
        ]
        record.update(argv=argv, cwd=str(ROOT))
        result = subprocess.run(
            argv,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        (out / "pytest.log").write_bytes(result.stdout)
        print(result.stdout.decode("utf-8", errors="replace"))
        record["exit_code"] = result.returncode
        code = result.returncode
        if (out / "pytest.xml").exists():
            # This XML is generated locally by the just-executed trusted pytest process.
            cases = ET.parse(out / "pytest.xml").findall(".//testcase")
            record["cases"] = [
                {
                    "id": c.get("classname", "") + "::" + c.get("name", ""),
                    "status": "failed"
                    if c.find("failure") is not None
                    else "error"
                    if c.find("error") is not None
                    else "skipped"
                    if c.find("skipped") is not None
                    else "passed",
                }
                for c in cases
            ]
            record["counts"] = {
                s: sum(c["status"] == s for c in record["cases"])
                for s in ("passed", "failed", "error", "skipped")
            }
        record["after"] = bindings()
        record["unchanged"] = record["before"] == record["after"]
        assert record["unchanged"], "Test execution changed source/config/workbooks"
        # A clean child process must still resolve the production-default flag to OFF.
        clean_env = env.copy()
        clean_env.pop("POSTING_ENABLED", None)
        check = subprocess.run(
            [
                sys.executable,
                "-c",
                "from app.config import POSTING_ENABLED; assert POSTING_ENABLED is False; print('default OFF')",
            ],
            cwd=ROOT,
            env=clean_env,
            capture_output=True,
            check=False,
        )
        record["default_off_exit"] = check.returncode
        assert check.returncode == 0, "Default feature gate no longer OFF"
    except Exception as error:
        record["error"] = type(error).__name__
        code = 1
        raise
    finally:
        engine.dispose()
        if record["created"]:
            with admin.connect() as db:
                db.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
                record["removed"] = not bool(
                    db.execute(
                        text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": name}
                    ).scalar()
                )
        admin.dispose()
        record["artifacts"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.iterdir()
            if p.is_file()
        }
        (out / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    k: record.get(k)
                    for k in (
                        "database",
                        "exit_code",
                        "counts",
                        "unchanged",
                        "removed",
                        "default_off_exit",
                    )
                }
            )
        )
        assert record["removed"], "Disposable database cleanup failed"
    return code


if __name__ == "__main__":
    raise SystemExit(main())
