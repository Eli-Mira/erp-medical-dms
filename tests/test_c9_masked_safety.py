"""Mask/import trust-boundary controls using synthetic structures only."""

from datetime import date
import importlib.util
import os
from pathlib import Path
import json
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text


def scenario():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "c9_safety_contract", root / "scripts/load_masked_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
    return module, structure


def test_private_financial_fields_are_not_accepted_as_structural_input():
    module, structure = scenario()
    structure["products"][0]["base_price"] = "SYNTHETIC_RAW_MONEY_CANARY"
    with pytest.raises(ValueError):
        module.masked_packet(structure, as_of=date(2026, 1, 1))


def test_canonical_medical_rep_keeps_explicit_branch_and_territory_grants():
    module, structure = scenario()
    structure["users"][0]["role"] = "medical_rep"
    structure["users"][0]["territories"] = ["synthetic-t"]
    packet = module.masked_packet(structure, as_of=date(2026, 1, 1))
    staff = next(user for user in packet["users"] if not user["is_owner"])
    assert staff["role"] == "medical_rep"
    assert {"user_id": staff["id"], "branch_id": packet["branches"][0]["id"]} in packet[
        "grants"
    ]
    assert {
        "user_id": staff["id"],
        "territory_id": packet["territories"][0]["id"],
    } in packet["territory_grants"]


def test_unknown_packet_columns_are_rejected_before_any_insert():
    module, structure = scenario()
    packet = module.masked_packet(structure, as_of=date(2026, 1, 1))
    packet["branches"][0]["unexpected_column"] = "synthetic-only"
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        failure = None
        try:
            with engine.begin() as db:
                module.apply_packet(db, packet)
        except Exception as error:
            failure = type(error).__name__
        assert failure == "ValueError", (
            "Unknown fields must fail validation, not reach SQL"
        )
        with engine.connect() as db:
            assert (
                db.scalar(text("SELECT count(*) FROM master_data.master_branch")) == 0
            )
            assert db.scalar(text("SELECT count(*) FROM audit.audit_log")) == 0
    finally:
        engine.dispose()


def test_cli_plan_without_target_exposes_only_counts(tmp_path):
    _, structure = scenario()
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "synthetic-structure.json"
    source.write_text(json.dumps(structure), encoding="utf-8")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABASE_URL", "C9_DEMO_OWNER_PASSWORD"}
    }
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/load_masked_demo.py"),
            "--structure",
            str(source),
            "--as-of",
            "2026-01-01",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["applied"] is False
    assert report["counts"]["customers"] == 1
    assert all(type(value) is int for value in report["counts"].values())
    assert "synthetic-" not in result.stdout


@pytest.mark.parametrize(
    "uri",
    [
        "postgresql+psycopg://fixture@127.0.0.1:5432/medical_dms",
        "postgresql+psycopg://fixture@127.0.0.1:5432/medical_demo",
        "postgresql+psycopg://fixture@127.0.0.1/dms_cycle_test_0123456789abcdef0123456789abcdef",
        "postgresql+psycopg://fixture@example.invalid:5432/dms_cycle_test_0123456789abcdef0123456789abcdef",
        "postgresql+psycopg://fixture@127.0.0.1:5432/dms_cycle_test_0123456789abcdef0123456789abcdef?host=example.invalid",
        "sqlite:///dms_cycle_test_0123456789abcdef0123456789abcdef",
    ],
)
def test_target_guard_refuses_protected_or_redirected_urls_before_connect(uri):
    from sqlalchemy.engine.url import make_url

    module, _ = scenario()
    with pytest.raises(ValueError):
        module.owned_target(make_url(uri))


def test_late_opening_failure_rolls_back_masters_grants_stock_and_audit(monkeypatch):
    import app.finance.ar as ar

    module, structure = scenario()
    packet = module.masked_packet(structure, as_of=date(2026, 1, 1))

    def fail_opening(*args, **kwargs):
        raise RuntimeError("synthetic late failure")

    monkeypatch.setattr(ar, "record_entry", fail_opening)
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with pytest.raises(RuntimeError, match="synthetic late failure"):
            with engine.begin() as db:
                module.apply_packet(db, packet)
        with engine.connect() as db:
            for table in [
                "master_data.master_branch",
                "platform.platform_user",
                "platform.user_branch",
                "inventory.stock_movement",
                "inventory.stock_balance",
                "finance.ar_entry",
                "audit.audit_log",
            ]:
                assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    finally:
        engine.dispose()


def test_cli_apply_without_target_configuration_fails_closed(tmp_path):
    _, structure = scenario()
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "synthetic-structure.json"
    source.write_text(json.dumps(structure), encoding="utf-8")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABASE_URL", "C9_DEMO_OWNER_PASSWORD"}
    }
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/load_masked_demo.py"),
            "--structure",
            str(source),
            "--as-of",
            "2026-01-01",
            "--apply",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1 and not result.stdout
    report = json.loads(result.stderr)
    assert report == {"applied": False, "failed": 1, "category": "ValueError"}


def test_medical_rep_without_explicit_territory_is_not_silently_seeded():
    module, structure = scenario()
    structure["users"][0]["role"] = "medical_rep"
    with pytest.raises(ValueError, match="explicit territory grants"):
        module.masked_packet(structure, as_of=date(2026, 1, 1))
