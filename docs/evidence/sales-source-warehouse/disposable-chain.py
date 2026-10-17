"""Exercise migrations only on a newly created, task-owned disposable database.

Proves the sales-routing prerequisite:
  - after 0009, an invoice whose warehouse is owned by another branch is
    ACCEPTED (fk_invoice_warehouse_source anchors warehouse only);
  - after 0008, the same cross-branch invoice is REJECTED (fk_invoice_warehouse_branch
    couples warehouse_id + branch_id -> master_warehouse(id, branch_id));
  - the full suite passes against the disposable DB without changing sources.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

# The script lives in docs/evidence/sales-source-warehouse/; the package (app/) sits
# at the repo root, which is not on sys.path for a run from there, so add it explicitly.
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

root = _root
from app.db import DATABASE_URL
out = root / "docs/evidence/sales-source-warehouse/final-verified"
out.mkdir(exist_ok=True)
url = create_engine(DATABASE_URL).url
name = "verify_sales_routing_" + uuid4().hex
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
target = url.set(database=name)
record = {"database": name, "steps": [], "removed": False}
created = False
PASS = "\u2713"
FAIL = "\u2717"


def seed(db, xb, yb):
    """Branches, routed warehouse, customer in branch X; no FKs on invoice yet."""
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id, code, name_ar, name_en) VALUES (:id, :c, :n_ar, :n)"
        ),
        {"id": xb, "c": "X", "n_ar": "فرع الفواتير", "n": "Invoice branch"},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id, code, name_ar, name_en) VALUES (:id, :c, :n_ar, :n)"
        ),
        {"id": yb, "c": "Y", "n_ar": "فرع المخازن", "n": "Warehouse branch"},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id, branch_id, code, name_ar) VALUES (:id, :b, :c, :n)"
        ),
        {"id": uuid4(), "b": yb, "c": "Dakahlia shared", "n": "Dakahlia shared"},
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_customer(id, branch_id, code, name_ar, name_en) VALUES (:id, :b, :c, :n_ar, :n)"
        ),
        {"id": uuid4(), "b": xb, "c": "X customer", "n_ar": "عميل الفرع", "n": "Customer"},
    )
    terr = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_territory(id, code, name_ar, name_en) VALUES (:id, :c, :n_ar, :n)"
        ),
        {"id": terr, "c": "INVOICE", "n_ar": "المرتب", "n": "Invoice territory"},
    )
    up = uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id, username, password_hash, role, is_owner, is_active) VALUES (:id, :u, :p, 'sales_manager', false, true)"
        ),
        {"id": up, "u": "test@" + uuid4().hex + ".com", "p": "x"},
    )
    return xb, yb, terr, up


def insert_cross_branch_invoice(db, xb, yb, label, actor, terr):
    """Cross-branch invoice: invoice X, warehouse owned by Y (fulfillment routed)."""
    w = db.execute(
        text("SELECT id FROM master_data.master_warehouse WHERE branch_id=:b"),
        {"b": yb}).scalar_one()
    c = db.execute(
        text("SELECT id FROM master_data.master_customer WHERE branch_id=:b"),
        {"b": xb}).scalar_one()
    db.execute(
        text("""INSERT INTO sales.sales_invoice
            (invoice_no, invoice_date, posting_status, total_before_discount, total_discount,
             total_net, vat_amount, grand_total, branch_id, warehouse_id, customer_id, territory_id,
             created_by, updated_by)
            VALUES (:no, CURRENT_DATE, 'Draft', '0.00', '0.00', '0.00', '0.00', '0.00',
                    :b, :w, :c, :t, :actor, :actor)"""),
        {"no": "FK-CHECK-1-" + label, "b": xb, "w": w, "c": c, "t": terr, "actor": actor})


try:
    with admin.connect() as connection:
        connection.exec_driver_sql('CREATE DATABASE "' + name + '"')
    created = True
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", target.render_as_string(hide_password=False).replace("%", "%%"))
    engine = create_engine(target)

    # 1) 0001 -> head (0009): cross-branch invoice must be ACCEPTED.
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        actual = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    record["steps"].append({"action": "upgrade-0009", "target": "head", "actual": actual})
    engine.dispose()

    engine = create_engine(target)
    with engine.connect() as connection:
        xb = uuid4()
        yb = uuid4()
        xb, yb, terr, actor = seed(connection, xb, yb)
        insert_cross_branch_invoice(connection, xb, yb, "0009", actor, terr)
    record["steps"].append({"action": "insert-cross-branch-0009", "ok": True})
    print(f"[{PASS}] 0009: cross-branch invoice (invoice X, warehouse owned by Y) accepted")

    # 2) downgrade to 0008: composite FK must REJECT the cross-branch invoice.
    command.downgrade(cfg, "0008")
    engine.dispose()
    engine = create_engine(target)
    with engine.connect() as connection:
        xb = uuid4()
        yb = uuid4()
        xb, yb, terr, actor = seed(connection, xb, yb)
        try:
            insert_cross_branch_invoice(connection, xb, yb, "0008", actor, terr)
            record["steps"].append({"action": "insert-cross-branch-0008", "ok": False})
            print(f"[{FAIL}] 0008: cross-branch invoice was ACCEPTED (composite FK missing)")
        except Exception as exc:  # noqa: BLE001
            record["steps"].append({"action": "insert-cross-branch-0008", "error": type(exc).__name__})
            print(f"[{PASS}] 0008: cross-branch invoice rejected ({type(exc).__name__})")

    # 3) upgrade back to 0009: ACCEPTED again.
    command.upgrade(cfg, "head")
    engine.dispose()
    engine = create_engine(target)
    with engine.connect() as connection:
        xb = uuid4()
        yb = uuid4()
        xb, yb, terr, actor = seed(connection, xb, yb)
        insert_cross_branch_invoice(connection, xb, yb, "back-0009", actor, terr)
    record["steps"].append({"action": "insert-back-0009", "ok": True})
    print(f"[{PASS}] 0009 re-applied: cross-branch invoice accepted again")

    # 4) full suite against the disposable DB.
    paths = [p for folder in ("app", "tests", "alembic", "web") for p in (root / folder).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts]
    paths += list(root.glob("*.xlsx"))
    record["before"] = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(paths)}
    env = os.environ.copy()
    env["DATABASE_URL"] = target.render_as_string(hide_password=False)
    argv = [sys.executable, "-m", "pytest", "tests/", "-q",
            "--tb=short", "--junitxml=" + str(out / "pytest.xml")]
    result = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / "pytest.log").write_bytes(result.stdout)
    print(result.stdout.decode("utf-8", errors="replace"))
    record.update(argv=" ".join(argv), cwd=str(root), exit_code=result.returncode)
    record["unchanged"] = record["before"] == {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                             for p in sorted(paths)}
    record["steps"].append({"action": "full-suite-on-disposable-db", "exit_code": result.returncode})
    print(f"[{'PASS' if result.returncode == 0 and record['unchanged'] else 'FAIL'}] "
          f"full suite on disposable DB exit={result.returncode}, source files unchanged={record['unchanged']}")
    assert result.returncode == 0 and record["unchanged"]
finally:
    if created:
        with admin.connect() as connection:
            connection.exec_driver_sql('DROP DATABASE "' + name + '" WITH (FORCE)')
            removed = not connection.execute(text("SELECT 1 FROM pg_database WHERE datname=:n"),
                                             {"n": name}).scalar()
        record["removed"] = removed
        print(f"[{'PASS' if removed else 'FAIL'}] disposable database dropped")
    record["artifacts"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(out.iterdir())}
    (out / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    admin.dispose()
print(json.dumps({k: record[k] for k in ("steps", "exit_code", "unchanged", "removed")}, indent=2))
assert record["removed"]
