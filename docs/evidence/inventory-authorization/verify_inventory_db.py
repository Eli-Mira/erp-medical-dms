"""Exercise migrations only on a newly created, task-owned disposable database."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from app.db import DATABASE_URL

root = Path.cwd()
out = root / "docs/evidence/inventory-authorization/final-fresh-db-run"
out.mkdir(exist_ok=False)
url = create_engine(DATABASE_URL).url
name = "verify_inventory_" + uuid4().hex
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
target = url.set(database=name)
record = {"database": name, "steps": [], "removed": False}
created = False
try:
    with admin.connect() as connection:
        connection.exec_driver_sql('CREATE DATABASE "' + name + '"')
    created = True
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", target.render_as_string(hide_password=False).replace("%", "%%"))
    for action, revision in (("upgrade", "head"), ("downgrade", "0007_ar_ledger"), ("upgrade", "head")):
        getattr(command, action)(cfg, revision)
        engine = create_engine(target)
        with engine.connect() as connection:
            actual = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        engine.dispose()
        record["steps"].append({"action": action, "target": revision, "actual": actual})
    assert actual == "0008_branch_warehouse"
    paths = [p for folder in ("app", "tests", "alembic", "web") for p in (root / folder).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts]
    paths += list(root.glob("*.xlsx"))
    def hashes():
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    record["before"] = hashes()
    env = os.environ.copy()
    env["DATABASE_URL"] = target.render_as_string(hide_password=False)
    argv = [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short", "--junitxml=" + str(out / "pytest.xml")]
    result = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / "pytest.log").write_bytes(result.stdout)
    print(result.stdout.decode("utf-8", errors="replace"))
    record.update(argv=argv, cwd=str(root), exit_code=result.returncode, after=hashes())
    record["unchanged"] = record["before"] == record["after"]
    assert result.returncode == 0 and record["unchanged"]
finally:
    if created:
        with admin.connect() as connection:
            connection.exec_driver_sql('DROP DATABASE "' + name + '" WITH (FORCE)')
            record["removed"] = not connection.execute(text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": name}).scalar()
    record["artifacts"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    (out / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    admin.dispose()
print(json.dumps({k: record[k] for k in ("steps", "exit_code", "unchanged", "removed")}, indent=2))
assert record["removed"]
