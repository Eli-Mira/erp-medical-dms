"""Real-table C9 apply contract; source graph is synthetic, never buyer rows."""

from datetime import date
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from sqlalchemy import create_engine, text


def test_c9_loads_parents_openings_and_staff_grants_atomically_on_fresh_target(
    tmp_path,
):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "c9_apply_contract", root / "scripts/load_masked_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(getattr(module, "apply_packet", None)), (
        "C9 ERP-table application capability is missing"
    )
    structure = {
        "branches": [{"key": "synthetic-b"}],
        "territories": [{"key": "synthetic-t"}],
        "products": [{"key": "synthetic-p"}],
        "warehouses": [{"key": "synthetic-w", "branch": "synthetic-b"}],
        "customers": [
            {"key": "synthetic-c", "branch": "synthetic-b", "territory": "synthetic-t"}
        ],
        "routes": [{"branch": "synthetic-b", "warehouse": "synthetic-w"}],
        "users": [
            {
                "key": "synthetic-staff",
                "role": "warehouse_staff",
                "branches": ["synthetic-b"],
            }
        ],
        "opening_stock": [{"warehouse": "synthetic-w", "product": "synthetic-p"}],
        "opening_ar": [{"customer": "synthetic-c"}],
    }
    packet = module.masked_packet(structure, as_of=date(2026, 1, 1))
    local_map = tmp_path / "synthetic-structure.json"
    local_map.write_text(json.dumps(structure), encoding="utf-8")
    password = secrets.token_urlsafe(24)
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/load_masked_demo.py"),
            "--structure",
            str(local_map),
            "--as-of",
            "2026-01-01",
            "--apply",
        ],
        cwd=root,
        env={**os.environ, "C9_DEMO_OWNER_PASSWORD": password},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "C9 CLI application failed"
    assert result.stdout.strip(), "C9 counts-only CLI is missing"
    report = json.loads(result.stdout)
    assert report["applied"] is True
    counts = report["counts"]
    assert all(type(value) is int for value in counts.values())
    leaked = password in result.stdout + result.stderr
    assert not leaked, "Credentials must not appear in CLI output"
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as db:
            assert (
                counts["customers"] == counts["products"] == counts["warehouses"] == 1
            )
            assert (
                db.scalar(text("SELECT count(*) FROM master_data.master_customer")) == 1
            )
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM finance.ar_entry WHERE entry_type='opening'"
                    )
                )
                == 1
            )
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM inventory.stock_movement WHERE movement_type='opening'"
                    )
                )
                == 1
            )
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM platform.platform_user u WHERE NOT u.is_owner AND NOT EXISTS(SELECT 1 FROM platform.user_branch g WHERE g.user_id=u.id)"
                    )
                )
                == 0
            )
            movement = db.scalar(
                text("SELECT sum(quantity) FROM inventory.stock_movement")
            )
            balance = db.scalar(
                text("SELECT sum(quantity) FROM inventory.stock_balance")
            )
            assert movement == balance == packet["opening_stock"][0]["quantity"]
            assert (
                db.scalar(text("SELECT sum(debit-credit) FROM finance.ar_entry"))
                == packet["opening_ar"][0]["debit"]
            )
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM audit.audit_log WHERE action='C9_DEMO_LOAD'"
                    )
                )
                == 1
            )
            from app.auth.security import verify_password

            stored = db.scalar(
                text("SELECT password_hash FROM platform.platform_user WHERE is_owner")
            )
            matches = verify_password(password, stored)
            assert matches, "Owner credential must be provisioned without exposing it"
    finally:
        engine.dispose()
